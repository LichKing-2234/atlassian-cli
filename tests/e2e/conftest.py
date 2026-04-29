import pytest

from tests.e2e.support import LiveEnv, load_live_env


@pytest.fixture(scope="session")
def live_env() -> LiveEnv:
    try:
        return load_live_env()
    except RuntimeError as exc:
        pytest.skip(str(exc))
