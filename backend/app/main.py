"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.core.settings import PATHS
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Job, JobEvent  # noqa: F401
from app.services import repository
from app.services.config_store import load_config, save_config
from app.workers.queue import enqueue_job


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        PATHS.runtime_root.mkdir(parents=True, exist_ok=True)
        PATHS.jobs_root.mkdir(parents=True, exist_ok=True)

        Base.metadata.create_all(bind=engine)

        # Ensure config file exists with defaults.
        if not PATHS.config_path.exists():
            save_config(load_config())

        with SessionLocal() as db:
            repository.reset_running_jobs_to_queued(db)
            queued_ids = repository.list_queued_jobs(db)
            db.commit()

        for job_id in queued_ids:
            enqueue_job(job_id)

        yield

    app = FastAPI(title="VideoBling Local", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


app = create_app()
