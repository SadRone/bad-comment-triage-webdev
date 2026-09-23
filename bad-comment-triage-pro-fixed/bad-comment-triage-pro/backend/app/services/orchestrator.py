import json
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..analysis.rules import analyze_text
from ..collectors.brave import BraveCollector
from ..collectors.google_cse import GoogleCSECollector
from ..collectors.youtube import YouTubeCollector
from ..db import SessionLocal
from ..models import EvidenceItem, SearchJob
from ..utils.text import dedup_hash
from .query_expander import build_web_queries, build_youtube_queries


COLLECTORS = {
    'brave': BraveCollector,
    'google': GoogleCSECollector,
    'youtube': YouTubeCollector,
}


def _loads(value: str, default):
    try:
        return json.loads(value or '')
    except Exception:
        return default


def _update_job(session, job: SearchJob, **fields):
    for key, value in fields.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        setattr(job, key, value)
    session.add(job)
    session.commit()
    session.refresh(job)


def _count_bands(session, job_id: str) -> dict:
    rows = session.execute(
        select(EvidenceItem.risk_band, func.count(EvidenceItem.id))
        .where(EvidenceItem.job_id == job_id)
        .group_by(EvidenceItem.risk_band)
    ).all()
    out = {'review_first': 0, 'context_needed': 0, 'low_priority': 0}
    for band, count in rows:
        out[band] = count
    out['total'] = sum(out.values())
    return out


def run_job(job_id: str) -> None:
    session = SessionLocal()
    try:
        job = session.get(SearchJob, job_id)
        if not job:
            return
        aliases = _loads(job.aliases_json, [])
        keywords = _loads(job.keywords_json, [])
        providers = _loads(job.providers_json, [])
        target_names = [job.target] + aliases
        diagnostics: dict = {}
        _update_job(session, job, status='running', progress_json={'stage': 'starting', 'saved': 0})

        for provider in providers:
            if provider not in COLLECTORS:
                diagnostics[provider] = {'errors': ['지원하지 않는 provider입니다.']}
                continue

            collector = COLLECTORS[provider]()
            if provider == 'youtube':
                queries = build_youtube_queries(job.target, aliases, keywords)
            else:
                queries = build_web_queries(job.target, aliases, keywords)

            _update_job(
                session,
                job,
                progress_json={
                    'stage': f'collecting:{provider}',
                    'saved': _count_bands(session, job.id)['total'],
                    'provider': provider,
                },
            )

            result = collector.collect(queries, target_names, keywords, job.result_limit)
            diag = {'stats': result.stats, 'errors': result.errors, 'saved': 0, 'duplicates': 0}

            for candidate in result.items:
                if _count_bands(session, job.id)['total'] >= job.result_limit:
                    break
                analysis = analyze_text(job.target, candidate.text, candidate.context, aliases=aliases)

                # Keep all candidates from primary comment APIs; web snippets/pages need at least some relevance signal.
                if candidate.source.startswith('web') or candidate.source == 'public_web':
                    if not (analysis.signals['target_direct'] or analysis.signals['target_in_context']):
                        continue
                    if analysis.risk_score == 0:
                        continue

                item = EvidenceItem(
                    job_id=job.id,
                    source=candidate.source,
                    external_id=candidate.external_id,
                    author=candidate.author,
                    text=candidate.text,
                    context=candidate.context,
                    url=candidate.url,
                    published_at=candidate.published_at,
                    query=candidate.query,
                    dedup_hash=dedup_hash(candidate.text, candidate.url),
                    risk_band=analysis.risk_band,
                    risk_score=analysis.risk_score,
                    reasons_json=json.dumps(analysis.reasons, ensure_ascii=False),
                    signals_json=json.dumps(analysis.signals, ensure_ascii=False),
                    analysis_version=analysis.analysis_version,
                )
                session.add(item)
                try:
                    session.commit()
                    diag['saved'] += 1
                except IntegrityError:
                    session.rollback()
                    diag['duplicates'] += 1

            diagnostics[provider] = diag
            bands = _count_bands(session, job.id)
            _update_job(
                session,
                job,
                diagnostics_json=diagnostics,
                progress_json={'stage': f'completed:{provider}', 'saved': bands['total'], 'bands': bands},
            )
            if bands['total'] >= job.result_limit:
                break

        bands = _count_bands(session, job.id)
        _update_job(
            session,
            job,
            status='completed',
            diagnostics_json=diagnostics,
            progress_json={'stage': 'completed', 'saved': bands['total'], 'bands': bands},
        )
    except Exception as exc:
        try:
            job = session.get(SearchJob, job_id)
            if job:
                _update_job(session, job, status='failed', error=f'{type(exc).__name__}: {exc}')
        finally:
            raise
    finally:
        session.close()
