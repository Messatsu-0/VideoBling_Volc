from app.schemas.config import VideoConfig
from app.services.volc_clients import VideoClient


def test_submit_payload_candidates_prefer_content_schema() -> None:
    cfg = VideoConfig(model="demo-model")
    candidates = VideoClient._submit_payload_candidates(  # noqa: SLF001
        cfg,
        prompt="test prompt",
        duration_s=5,
        width=720,
        height=1280,
    )

    first = candidates[0]
    assert first["model"] == "demo-model"
    assert first["content"][0]["type"] == "text"
    assert first["content"][0]["text"] == "test prompt"
    assert first["width"] == 720
    assert first["height"] == 1280
    assert first["duration"] == 5
    assert "prompt" not in first


def test_submit_payload_candidates_keep_legacy_fallback_last() -> None:
    cfg = VideoConfig(model="demo-model")
    candidates = VideoClient._submit_payload_candidates(  # noqa: SLF001
        cfg,
        prompt="legacy test",
        duration_s=5,
        width=1080,
        height=1920,
    )

    last = candidates[-1]
    assert last["model"] == "demo-model"
    assert last["prompt"] == "legacy test"
    assert last["resolution"] == "1080x1920"
