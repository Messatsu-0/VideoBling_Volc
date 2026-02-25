"""Validation for generated hook script JSON."""

from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = {
    "hook_title",
    "visual_prompt",
    "shot_list",
    "narration",
    "style_tags",
    "safety_notes",
}


class ScriptSchemaError(ValueError):
    pass


def validate_script_payload(payload: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS - set(payload.keys()))
    if missing:
        raise ScriptSchemaError(f"missing fields: {', '.join(missing)}")

    if not isinstance(payload.get("shot_list"), list):
        raise ScriptSchemaError("shot_list must be an array")
    if not isinstance(payload.get("style_tags"), list):
        raise ScriptSchemaError("style_tags must be an array")

    for key in ("hook_title", "visual_prompt", "narration", "safety_notes"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ScriptSchemaError(f"{key} must be non-empty string")

    return payload
