import os

import pytest


@pytest.mark.skipif(not os.getenv("ATLASSIAN_SMOKE"), reason="smoke env not configured")
def test_smoke_suite_has_required_env() -> None:
    assert os.getenv("ATLASSIAN_URL")
    assert os.getenv("ATLASSIAN_PRODUCT")
