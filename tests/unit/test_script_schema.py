import pytest

from app.services.script_schema import ScriptSchemaError, validate_script_payload


def test_validate_script_payload_success() -> None:
    payload = {
        "hook_title": "荒诞开场",
        "visual_prompt": "城市上空飘着巨大橘子",
        "shot_list": ["镜头一", "镜头二"],
        "narration": "今天发生了不可能的事",
        "style_tags": ["夸张", "赛博"],
        "safety_notes": "不包含血腥暴力",
    }

    validated = validate_script_payload(payload)
    assert validated["hook_title"] == "荒诞开场"


def test_validate_script_payload_missing_fields() -> None:
    with pytest.raises(ScriptSchemaError):
        validate_script_payload({
            "hook_title": "x",
            "visual_prompt": "y",
        })
