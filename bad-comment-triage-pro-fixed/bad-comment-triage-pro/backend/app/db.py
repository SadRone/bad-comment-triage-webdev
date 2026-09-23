import time
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def init_db(retries: int = 20, delay: float = 1.0) -> None:
    from . import models  # noqa: F401
    last = None
    for _ in range(retries):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception as exc:  # DB may still be starting
            last = exc
            time.sleep(delay)
    if last:
        raise last


@contextmanager
def db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
