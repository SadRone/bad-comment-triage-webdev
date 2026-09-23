import requests
from .base import CollectorResult, EvidenceCandidate
from ..core.config import get_settings
from ..utils.text import normalize_space


class YouTubeCollector:
    name = 'youtube'

    def __init__(self):
        self.settings = get_settings()
        self.base = 'https://www.googleapis.com/youtube/v3'

    @property
    def configured(self) -> bool:
        return bool(self.settings.youtube_api_key.strip())

    def _get(self, path: str, params: dict) -> dict:
        params = {**params, 'key': self.settings.youtube_api_key}
        resp = requests.get(f'{self.base}/{path}', params=params, timeout=self.settings.request_timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    def collect(self, queries: list[str], target_names: list[str], keywords: list[str], limit: int) -> CollectorResult:
        result = CollectorResult(stats={
            'queries': 0, 'videos_found': 0, 'videos_scanned': 0, 'comment_pages': 0,
            'comments_seen': 0, 'replies_seen': 0, 'candidates': 0,
        })
        if not self.configured:
            result.errors.append('YOUTUBE_API_KEY가 설정되지 않았습니다.')
            return result

        videos: dict[str, dict] = {}
        for query in queries:
            if len(videos) >= self.settings.max_youtube_videos:
                break
            result.stats['queries'] += 1
            try:
                data = self._get('search', {
                    'part': 'snippet', 'type': 'video', 'q': query,
                    'maxResults': min(25, self.settings.max_youtube_videos),
                    'safeSearch': 'none',
                })
            except Exception as exc:
                result.errors.append(f'YouTube 영상 검색 실패 ({query}): {type(exc).__name__}')
                continue
            for row in data.get('items') or []:
                vid = (row.get('id') or {}).get('videoId')
                if not vid:
                    continue
                sn = row.get('snippet') or {}
                videos.setdefault(vid, {
                    'title': normalize_space(sn.get('title') or ''),
                    'channel': normalize_space(sn.get('channelTitle') or ''),
                    'published_at': sn.get('publishedAt') or '',
                    'query': query,
                })
                if len(videos) >= self.settings.max_youtube_videos:
                    break
        result.stats['videos_found'] = len(videos)

        for video_id, meta in videos.items():
            if len(result.items) >= limit:
                break
            result.stats['videos_scanned'] += 1
            token = None
            for _ in range(self.settings.max_youtube_comment_pages_per_video):
                params = {
                    'part': 'snippet,replies',
                    'videoId': video_id,
                    'maxResults': 100,
                    'textFormat': 'plainText',
                    'order': 'relevance',
                }
                if token:
                    params['pageToken'] = token
                try:
                    data = self._get('commentThreads', params)
                except requests.HTTPError as exc:
                    # Comments can be disabled; record and continue.
                    code = exc.response.status_code if exc.response is not None else 'HTTP'
                    result.errors.append(f'YouTube 댓글 조회 실패 ({video_id}, {code})')
                    break
                except Exception as exc:
                    result.errors.append(f'YouTube 댓글 조회 실패 ({video_id}): {type(exc).__name__}')
                    break

                result.stats['comment_pages'] += 1
                for thread in data.get('items') or []:
                    top = ((thread.get('snippet') or {}).get('topLevelComment') or {})
                    top_sn = top.get('snippet') or {}
                    text = normalize_space(top_sn.get('textOriginal') or top_sn.get('textDisplay') or '')
                    if text:
                        result.stats['comments_seen'] += 1
                        cid = top.get('id') or ''
                        result.items.append(EvidenceCandidate(
                            source='youtube',
                            text=text,
                            url=f'https://www.youtube.com/watch?v={video_id}&lc={cid}' if cid else f'https://www.youtube.com/watch?v={video_id}',
                            author=normalize_space(top_sn.get('authorDisplayName') or ''),
                            external_id=cid,
                            context=f"YouTube 영상: {meta['title']}",
                            published_at=top_sn.get('publishedAt') or '',
                            query=meta['query'],
                        ))
                    for reply in ((thread.get('replies') or {}).get('comments') or []):
                        rs = reply.get('snippet') or {}
                        rtext = normalize_space(rs.get('textOriginal') or rs.get('textDisplay') or '')
                        if not rtext:
                            continue
                        result.stats['replies_seen'] += 1
                        rid = reply.get('id') or ''
                        result.items.append(EvidenceCandidate(
                            source='youtube_reply',
                            text=rtext,
                            url=f'https://www.youtube.com/watch?v={video_id}&lc={rid}' if rid else f'https://www.youtube.com/watch?v={video_id}',
                            author=normalize_space(rs.get('authorDisplayName') or ''),
                            external_id=rid,
                            context=f"YouTube 영상: {meta['title']}",
                            published_at=rs.get('publishedAt') or '',
                            query=meta['query'],
                        ))
                    if len(result.items) >= limit:
                        break
                token = data.get('nextPageToken')
                if not token or len(result.items) >= limit:
                    break

        result.items = result.items[:limit]
        result.stats['candidates'] = len(result.items)
        return result
