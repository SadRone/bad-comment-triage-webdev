import urllib.robotparser
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

from .base import EvidenceCandidate
from ..analysis.rules import INSULTS, SEVERE_INSULTS, THREATS, CRIME_ALLEGATIONS, PRIVACY_EXPOSURE, SEXUAL_SLURS
from ..core.config import get_settings
from ..utils.net import is_safe_public_http_url
from ..utils.text import contains_any, normalize_space, split_sentences

TRIGGERS = list(dict.fromkeys(INSULTS + SEVERE_INSULTS + THREATS + CRIME_ALLEGATIONS + PRIVACY_EXPOSURE + SEXUAL_SLURS))


class PublicPageEnricher:
    def __init__(self):
        self.settings = get_settings()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.settings.user_agent})

    def _robots_allowed(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            robots_url = urljoin(f'{parsed.scheme}://{parsed.netloc}', '/robots.txt')
            if not is_safe_public_http_url(robots_url):
                return False
            resp = self.session.get(robots_url, timeout=self.settings.request_timeout_seconds, allow_redirects=True)
            if resp.status_code >= 400 or not is_safe_public_http_url(resp.url):
                return False
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.parse(resp.text.splitlines())
            return rp.can_fetch(self.settings.user_agent, url)
        except Exception:
            # Fail closed: do not crawl a site if robots status cannot be established.
            return False

    def fetch_candidates(
        self,
        url: str,
        target_names: list[str],
        keywords: list[str],
        query: str,
        fallback_context: str = '',
    ) -> tuple[list[EvidenceCandidate], dict]:
        stats = {'attempted': 1, 'robots_blocked': 0, 'unsafe_url': 0, 'http_failed': 0, 'sentences_scanned': 0}
        if not self.settings.allow_robots_aware_fetch:
            return [], stats
        if not is_safe_public_http_url(url):
            stats['unsafe_url'] = 1
            return [], stats
        if not self._robots_allowed(url):
            stats['robots_blocked'] = 1
            return [], stats
        try:
            with self.session.get(url, timeout=self.settings.request_timeout_seconds, stream=True, allow_redirects=True) as resp:
                if resp.status_code >= 400 or not is_safe_public_http_url(resp.url):
                    stats['http_failed'] = 1
                    return [], stats
                ctype = resp.headers.get('content-type', '')
                if 'text/html' not in ctype:
                    stats['http_failed'] = 1
                    return [], stats
                chunks = []
                total = 0
                max_bytes = 1_500_000
                for chunk in resp.iter_content(chunk_size=32768):
                    total += len(chunk)
                    if total > max_bytes:
                        break
                    chunks.append(chunk)
                html_bytes = b''.join(chunks)
        except requests.RequestException:
            stats['http_failed'] = 1
            return [], stats

        soup = BeautifulSoup(html_bytes, 'html.parser')
        for tag in soup(['script', 'style', 'noscript', 'svg', 'iframe']):
            tag.decompose()
        title = normalize_space(soup.title.get_text(' ', strip=True) if soup.title else '')
        context = title or fallback_context
        blocks = []
        for node in soup.find_all(['p', 'li', 'blockquote', 'article']):
            text = normalize_space(node.get_text(' ', strip=True))
            if 8 <= len(text) <= 8000:
                blocks.append(text)
        body = '\n'.join(blocks[:1200])
        sentences = split_sentences(body)
        stats['sentences_scanned'] = len(sentences)

        trigger_terms = list(dict.fromkeys((keywords or []) + TRIGGERS))
        context_has_target = contains_any(context, target_names)
        items: list[EvidenceCandidate] = []
        for sentence in sentences:
            direct_target = contains_any(sentence, target_names)
            trigger = contains_any(sentence, trigger_terms)
            if trigger and (direct_target or context_has_target):
                items.append(EvidenceCandidate(
                    source='public_web',
                    text=sentence,
                    url=url,
                    context=context,
                    query=query,
                ))
                if len(items) >= 30:
                    break
        return items, stats
