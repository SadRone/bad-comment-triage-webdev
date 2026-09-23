from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title='Public Comment Triage Pro',
    version='2.0.0',
    description='Public-source collection and review-priority triage. Not a legal determination.',
    lifespan=lifespan,
)
app.include_router(router)

frontend = Path('/app/frontend')
if frontend.exists():
    app.mount('/', StaticFiles(directory=str(frontend), html=True), name='frontend')
