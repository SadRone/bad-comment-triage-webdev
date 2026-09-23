import csv
import io
import json
import uuid
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from ..analysis.rules import analyze_text
from ..collectors.brave import BraveCollector
from ..collectors.google_cse import GoogleCSECollector
from ..collectors.youtube import YouTubeCollector
from ..db import SessionLocal
from ..models import EvidenceItem, SearchJob
from ..schemas import JobCreate, ManualAnalyzeRequest
from ..worker import run_search_job

router = APIRouter(prefix='/api')


def loads(value: str, default):
    try:
        return json.loads(value or '')
    except Exception:
        return default


def provider_statuses():
    return [
        {
            'name': 'youtube',
            'configured': YouTubeCollector().configured,
            'description': 'YouTube Data API v3로 관련 영상의 공개 댓글과 일부 답글을 수집합니다.',
            'requires': ['YOUTUBE_API_KEY'],
        },
        {
            'name': 'brave',
            'configured': BraveCollector().configured,
            'description': 'Brave Search API로 공개 웹 후보를 찾고 허용된 페이지를 robots.txt 준수 방식으로 보강합니다.',
            'requires': ['BRAVE_SEARCH_API_KEY'],
        },
        {
            'name': 'google',
            'configured': GoogleCSECollector().configured,
            'description': 'Google Programmable Search JSON API로 공개 웹 후보를 찾습니다.',
            'requires': ['GOOGLE_CSE_API_KEY', 'GOOGLE_CSE_CX'],
        },
    ]


@router.get('/health')
def health():
    return {'ok': True, 'service': 'bad-comment-triage-pro'}


@router.get('/providers')
def providers():
    return {'providers': provider_statuses()}


@router.post('/jobs')
def create_job(payload: JobCreate):
    status_map = {p['name']: p['configured'] for p in provider_statuses()}
    selected = payload.providers or [name for name, configured in status_map.items() if configured]
    unavailable = [p for p in selected if not status_map.get(p, False)]
    if unavailable:
        raise HTTPException(
            status_code=400,
            detail=f"API key가 설정되지 않은 수집기가 선택되었습니다: {', '.join(unavailable)}",
        )
    if not selected:
        raise HTTPException(
            status_code=400,
            detail='사용 가능한 수집기가 없습니다. .env에 YouTube, Brave 또는 Google CSE API 키를 설정하세요.',
        )

    job = SearchJob(
        id=str(uuid.uuid4()),
        target=payload.target,
        aliases_json=json.dumps(payload.aliases, ensure_ascii=False),
        keywords_json=json.dumps(payload.keywords, ensure_ascii=False),
        providers_json=json.dumps(selected, ensure_ascii=False),
        result_limit=payload.limit,
        status='queued',
        progress_json=json.dumps({'stage': 'queued', 'saved': 0}, ensure_ascii=False),
    )
    with SessionLocal() as session:
        session.add(job)
        session.commit()
        session.refresh(job)
    run_search_job.delay(job.id)
    return {'id': job.id, 'status': job.status, 'providers': selected}


@router.get('/jobs/{job_id}')
def get_job(job_id: str):
    with SessionLocal() as session:
        job = session.get(SearchJob, job_id)
        if not job:
            raise HTTPException(404, '작업을 찾을 수 없습니다.')
        counts = dict(session.execute(
            select(EvidenceItem.risk_band, func.count(EvidenceItem.id))
            .where(EvidenceItem.job_id == job_id)
            .group_by(EvidenceItem.risk_band)
        ).all())
        return {
            'id': job.id,
            'target': job.target,
            'aliases': loads(job.aliases_json, []),
            'keywords': loads(job.keywords_json, []),
            'providers': loads(job.providers_json, []),
            'status': job.status,
            'progress': loads(job.progress_json, {}),
            'diagnostics': loads(job.diagnostics_json, {}),
            'error': job.error,
            'counts': {
                'total': sum(counts.values()),
                'review_first': counts.get('review_first', 0),
                'context_needed': counts.get('context_needed', 0),
                'low_priority': counts.get('low_priority', 0),
            },
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'updated_at': job.updated_at.isoformat() if job.updated_at else None,
        }


@router.get('/jobs/{job_id}/results')
def get_results(
    job_id: str,
    band: str | None = Query(default=None),
    source: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    with SessionLocal() as session:
        job = session.get(SearchJob, job_id)
        if not job:
            raise HTTPException(404, '작업을 찾을 수 없습니다.')
        stmt = select(EvidenceItem).where(EvidenceItem.job_id == job_id)
        if band:
            stmt = stmt.where(EvidenceItem.risk_band == band)
        if source:
            stmt = stmt.where(EvidenceItem.source == source)
        stmt = stmt.order_by(EvidenceItem.risk_score.desc(), EvidenceItem.id.desc()).offset(offset).limit(limit)
        rows = session.scalars(stmt).all()
        return {
            'items': [
                {
                    'id': x.id,
                    'source': x.source,
                    'author': x.author,
                    'text': x.text,
                    'context': x.context,
                    'url': x.url,
                    'published_at': x.published_at,
                    'query': x.query,
                    'risk_band': x.risk_band,
                    'risk_score': x.risk_score,
                    'reasons': loads(x.reasons_json, []),
                    'signals': loads(x.signals_json, {}),
                    'analysis_version': x.analysis_version,
                }
                for x in rows
            ]
        }


@router.get('/jobs/{job_id}/export.csv')
def export_csv(job_id: str):
    with SessionLocal() as session:
        job = session.get(SearchJob, job_id)
        if not job:
            raise HTTPException(404, '작업을 찾을 수 없습니다.')
        rows = session.scalars(
            select(EvidenceItem)
            .where(EvidenceItem.job_id == job_id)
            .order_by(EvidenceItem.risk_score.desc(), EvidenceItem.id.asc())
        ).all()
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(['risk_band', 'risk_score', 'source', 'author', 'published_at', 'text', 'context', 'url', 'query', 'reasons'])
        for x in rows:
            writer.writerow([
                x.risk_band, x.risk_score, x.source, x.author, x.published_at,
                x.text, x.context, x.url, x.query, ' | '.join(loads(x.reasons_json, [])),
            ])
        data = out.getvalue().encode('utf-8-sig')
        filename = f'triage-{job.target}-{job_id[:8]}.csv'.replace(' ', '_')
        return StreamingResponse(
            iter([data]),
            media_type='text/csv; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )


@router.post('/analyze/manual')
def manual_analyze(payload: ManualAnalyzeRequest):
    result = analyze_text(payload.target, payload.text, payload.context)
    return {
        'risk_band': result.risk_band,
        'risk_score': result.risk_score,
        'reasons': result.reasons,
        'signals': result.signals,
        'analysis_version': result.analysis_version,
    }
