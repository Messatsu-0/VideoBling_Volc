import os

import pytest


@pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="Set RUN_E2E=1 and prepare real Volcengine credentials + ffmpeg to run e2e.",
)
def test_pipeline_smoke_placeholder() -> None:
    # E2E is environment-dependent and is intentionally gated behind RUN_E2E.
    assert True
