from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    database_url: str = 'postgresql+psycopg://triage:triage_local_password@db:5432/triage'
    redis_url: str = 'redis://redis:6379/0'

    youtube_api_key: str = ''
    brave_search_api_key: str = ''
    google_cse_api_key: str = ''
    google_cse_cx: str = ''

    allow_robots_aware_fetch: bool = True
    max_web_pages_per_query: int = 5
    max_youtube_videos: int = 20
    max_youtube_comment_pages_per_video: int = 2

    request_timeout_seconds: float = 10.0
    user_agent: str = 'BadCommentTriageBot/2.0 (+local research tool)'


@lru_cache
def get_settings() -> Settings:
    return Settings()
