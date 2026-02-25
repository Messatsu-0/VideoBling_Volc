from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.constants import JobStatus
from app.db.base import Base
from app.models import Job, JobEvent
from app.services import repository


def test_job_status_flow_in_memory() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    LocalSession = sessionmaker(bind=engine, class_=Session)

    with LocalSession() as db:
        repository.create_job(
            db,
            job_id="job_1",
            project_name="demo",
            input_filename="a.mp4",
            source_path="/tmp/a.mp4",
            asr_clip_seconds=15,
            hook_clip_seconds=5,
        )
        db.commit()

        repository.set_job_status(db, "job_1", JobStatus.ASR, "进入ASR")
        repository.put_artifact(db, "job_1", "source_video", "/tmp/a.mp4")
        db.commit()

        job = repository.get_job(db, "job_1")
        assert job is not None
        assert job.status == JobStatus.ASR.value

        out = repository.to_job_out(job)
        assert out.artifacts["source_video"] == "/tmp/a.mp4"

        events = repository.list_events(db, "job_1")
        assert len(events) >= 2


# Keep explicit imports referenced for SQLAlchemy mapper configuration.
_ = (Job, JobEvent)
