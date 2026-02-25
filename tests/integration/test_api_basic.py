from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.settings import PATHS
from app.db.base import Base
from app.db.session import SessionLocal
from app.db.session import engine
from app.main import app
from app.services import repository

Base.metadata.create_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_config_roundtrip(client: TestClient) -> None:
    backup = PATHS.config_path.read_text(encoding="utf-8") if PATHS.config_path.exists() else None

    try:
        current = client.get("/api/config")
        assert current.status_code == 200
        payload = current.json()
        payload["pipeline"]["default_asr_clip_seconds"] = 21
        payload["pipeline"]["enable_asr_polish"] = False

        saved = client.put("/api/config", json=payload)
        assert saved.status_code == 200
        assert saved.json()["pipeline"]["default_asr_clip_seconds"] == 21
        assert saved.json()["pipeline"]["enable_asr_polish"] is False
    finally:
        if backup is None:
            PATHS.config_path.unlink(missing_ok=True)
        else:
            PATHS.config_path.write_text(backup, encoding="utf-8")


def test_config_preset_crud(client: TestClient) -> None:
    backup = PATHS.config_presets_path.read_text(encoding="utf-8") if PATHS.config_presets_path.exists() else None

    try:
        config_resp = client.get("/api/config")
        assert config_resp.status_code == 200
        config = config_resp.json()
        config["llm"]["model"] = "seed-2.0-pro"

        save_resp = client.put("/api/config/presets/demo", json=config)
        assert save_resp.status_code == 200
        assert save_resp.json()["name"] == "demo"

        list_resp = client.get("/api/config/presets")
        assert list_resp.status_code == 200
        assert any(item["name"] == "demo" for item in list_resp.json())

        detail_resp = client.get("/api/config/presets/demo")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["config"]["llm"]["model"] == "seed-2.0-pro"

        delete_resp = client.delete("/api/config/presets/demo")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] is True
    finally:
        if backup is None:
            PATHS.config_presets_path.unlink(missing_ok=True)
        else:
            PATHS.config_presets_path.write_text(backup, encoding="utf-8")


def test_create_job_without_worker(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr("app.api.routes.enqueue_job", lambda job_id: None)

    response = client.post(
        "/api/jobs",
        data={
            "project_name": "itest",
            "asr_clip_seconds": "15",
            "hook_clip_seconds": "5",
        },
        files={"video_file": ("sample.mp4", b"fake-video-bytes", "video/mp4")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "queued"

    job_id = payload["job_id"]

    list_resp = client.get("/api/jobs")
    assert list_resp.status_code == 200
    assert any(job["id"] == job_id for job in list_resp.json())

    delete_resp = client.delete(f"/api/jobs/{job_id}?force=true")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True

    check_resp = client.get(f"/api/jobs/{job_id}")
    assert check_resp.status_code == 404

    with SessionLocal() as db:
        job = repository.get_job(db, job_id)
        if job:
            db.delete(job)
            db.commit()

    shutil.rmtree(PATHS.jobs_root / job_id, ignore_errors=True)


def test_rerun_job_create_without_worker(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr("app.api.routes.enqueue_job", lambda job_id: None)

    create_resp = client.post(
        "/api/jobs",
        data={
            "project_name": "parent-job",
            "asr_clip_seconds": "15",
            "hook_clip_seconds": "5",
        },
        files={"video_file": ("sample.mp4", b"fake-video-bytes-for-rerun", "video/mp4")},
    )
    assert create_resp.status_code == 200, create_resp.text
    parent_id = create_resp.json()["job_id"]

    rerun_resp = client.post(
        f"/api/jobs/{parent_id}/rerun",
        json={"start_stage": "script_gen", "project_name": "child-rerun"},
    )
    assert rerun_resp.status_code == 200, rerun_resp.text
    payload = rerun_resp.json()
    assert payload["status"] == "queued"
    child_id = payload["job_id"]
    assert child_id != parent_id

    with SessionLocal() as db:
        parent = repository.get_job(db, parent_id)
        child = repository.get_job(db, child_id)
        assert parent is not None
        assert child is not None
        child_out = repository.to_job_out(child)
        assert child_out.meta.get("rerun_of_job_id") == parent_id
        assert child_out.meta.get("rerun_start_stage") == "script_gen"
        assert child.project_name == "child-rerun"
        assert Path(child.source_path).exists()
        assert Path(parent.source_path).read_bytes() == Path(child.source_path).read_bytes()

    delete_parent_resp = client.delete(f"/api/jobs/{parent_id}?force=true")
    assert delete_parent_resp.status_code == 200
    delete_child_resp = client.delete(f"/api/jobs/{child_id}?force=true")
    assert delete_child_resp.status_code == 200
