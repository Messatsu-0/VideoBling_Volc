"""Read/write persisted local configuration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.settings import PATHS
from app.schemas.config import AppConfig, ConfigPresetOut, ConfigPresetSummary


def load_config(path: Path = PATHS.config_path) -> AppConfig:
    if not path.exists():
        return AppConfig()
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)


def save_config(config: AppConfig, path: Path = PATHS.config_path) -> AppConfig:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return config


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_preset_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ValueError("preset name is required")
    if len(normalized) > 80:
        raise ValueError("preset name too long (max 80)")
    return normalized


def _load_presets_raw(path: Path = PATHS.config_presets_path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if isinstance(payload, dict):
        presets = payload.get("presets")
        if isinstance(presets, dict):
            return presets
        # Backward-compatible fallback if file directly stores mapping.
        return payload
    return {}


def _save_presets_raw(presets: dict[str, Any], path: Path = PATHS.config_presets_path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"presets": presets}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_config_presets(path: Path = PATHS.config_presets_path) -> list[ConfigPresetSummary]:
    presets = _load_presets_raw(path)
    items: list[ConfigPresetSummary] = []
    for name, value in presets.items():
        if not isinstance(value, dict):
            continue
        updated_at = str(value.get("updated_at") or "1970-01-01T00:00:00+00:00")
        items.append(ConfigPresetSummary(name=str(name), updated_at=updated_at))
    items.sort(key=lambda item: item.updated_at, reverse=True)
    return items


def get_config_preset(name: str, path: Path = PATHS.config_presets_path) -> ConfigPresetOut | None:
    normalized = _normalize_preset_name(name)
    presets = _load_presets_raw(path)
    record = presets.get(normalized)
    if not isinstance(record, dict):
        return None

    config_data = record.get("config", record)
    try:
        config = AppConfig.model_validate(config_data)
    except Exception:
        return None

    updated_at = str(record.get("updated_at") or _utc_now_iso())
    return ConfigPresetOut(name=normalized, updated_at=updated_at, config=config)


def save_config_preset(name: str, config: AppConfig, path: Path = PATHS.config_presets_path) -> ConfigPresetOut:
    normalized = _normalize_preset_name(name)
    presets = _load_presets_raw(path)
    updated_at = _utc_now_iso()
    presets[normalized] = {"updated_at": updated_at, "config": config.model_dump()}
    _save_presets_raw(presets, path)
    return ConfigPresetOut(name=normalized, updated_at=updated_at, config=config)


def delete_config_preset(name: str, path: Path = PATHS.config_presets_path) -> bool:
    normalized = _normalize_preset_name(name)
    presets = _load_presets_raw(path)
    if normalized not in presets:
        return False
    del presets[normalized]
    _save_presets_raw(presets, path)
    return True
