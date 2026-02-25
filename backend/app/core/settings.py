"""Runtime paths and static app settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    backend_root: Path
    runtime_root: Path
    jobs_root: Path
    config_path: Path
    config_presets_path: Path
    db_path: Path
    queue_path: Path


def build_paths() -> AppPaths:
    backend_root = Path(__file__).resolve().parents[2]
    project_root = backend_root.parent
    runtime_root = project_root / "runtime"
    jobs_root = runtime_root / "jobs"
    config_path = runtime_root / "config.json"
    config_presets_path = runtime_root / "config_presets.json"
    db_path = runtime_root / "app.sqlite3"
    queue_path = runtime_root / "queue.sqlite"

    runtime_root.mkdir(parents=True, exist_ok=True)
    jobs_root.mkdir(parents=True, exist_ok=True)

    return AppPaths(
        project_root=project_root,
        backend_root=backend_root,
        runtime_root=runtime_root,
        jobs_root=jobs_root,
        config_path=config_path,
        config_presets_path=config_presets_path,
        db_path=db_path,
        queue_path=queue_path,
    )


APP_VERSION = "0.1.0"
PATHS = build_paths()
