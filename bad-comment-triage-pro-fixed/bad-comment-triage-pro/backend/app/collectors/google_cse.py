import requests
from .base import CollectorResult, EvidenceCandidate
from .web_fetch import PublicPageEnricher, TRIGGERS
from ..core.config import get_settings
from ..utils.text import contains_any, normalize_space


class GoogleCSECollector:
    name = 'google'

    def __init__(self):
        self.settings = get_settings()
        self.enricher = PublicPageEnricher()

    @property
    def configured(self) -> bool:
        return bool(self.settings.google_cse_api_key.strip() and self.settings.google_cse_cx.strip())

    def collect(self, queries: list[str], target_names: list[str], keywords: list[str], limit: int) -> CollectorResult:
        result = CollectorResult(stats={
            'queries': 0, 'search_results': 0, 'snippets_kept': 0, 'pages_attempted': 0,
            'robots_blocked': 0, 'http_failed': 0, 'candidates': 0,
        })
        if not self.configured:
            result.errors.append('GOOGLE_CSE_API_KEY 또는 GOOGLE_CSE_CX가 설정되지 않았습니다.')
            return result

        trigger_terms = list(dict.fromkeys((keywords or []) + TRIGGERS))
        seen_urls = set()
        for query in queries:
            if len(result.items) >= limit:
                break
            result.stats['queries'] += 1
            try:
                resp = requests.get(
                    'https://www.googleapis.com/customsearch/v1',
                    params={
                        'key': self.settings.google_cse_api_key,
                        'cx': self.settings.google_cse_cx,
                        'q': query,
                        'num': 10,
                    },
                    timeout=self.settings.request_timeout_seconds,
                )
                resp.raise_for_status()
                rows = resp.json().get('items') or []
            except Exception as exc:
                result.errors.append(f'Google CSE 검색 실패 ({query}): {type(exc).__name__}')
                continue

            result.stats['search_results'] += len(rows)
            for row in rows:
                if len(result.items) >= limit:
                    break
                url = row.get('link') or ''
                title = normalize_space(row.get('title') or '')
                snippet = normalize_space(row.get('snippet') or '')
                context_target = contains_any(title, target_names)
                if snippet and contains_any(snippet, trigger_terms) and (contains_any(snippet, target_names) or context_target):
                    result.items.append(EvidenceCandidate(
                        source='web_search_snippet', text=snippet, url=url, context=title, query=query,
                    ))
                    result.stats['snippets_kept'] += 1
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                if result.stats['pages_attempted'] >= self.settings.max_web_pages_per_query * result.stats['queries']:
                    continue
                page_items, page_stats = self.enricher.fetch_candidates(url, target_names, keywords, query, title)
                result.stats['pages_attempted'] += page_stats.get('attempted', 0)
                result.stats['robots_blocked'] += page_stats.get('robots_blocked', 0)
                result.stats['http_failed'] += page_stats.get('http_failed', 0)
                result.items.extend(page_items[:max(0, limit - len(result.items))])
        result.stats['candidates'] = len(result.items)
        return result
