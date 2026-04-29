import json
import os
import subprocess
import sys
from pathlib import Path

from tests.e2e.support.env import LiveEnv

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"


def run_cli(live_env: LiveEnv, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{SRC_ROOT}{os.pathsep}{pythonpath}" if pythonpath else str(SRC_ROOT)
    command = [
        sys.executable,
        "-m",
        "atlassian_cli.main",
        "--config-file",
        str(live_env.config_file),
        *args,
    ]
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def run_json(live_env: LiveEnv, *args: str):
    result = run_cli(live_env, *args)
    if result.returncode != 0:
        raise AssertionError(
            "CLI command failed\n"
            f"command: {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return json.loads(result.stdout)


def run_failure(live_env: LiveEnv, *args: str, expected: str) -> str:
    result = run_cli(live_env, *args)
    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 0:
        raise AssertionError(f"command unexpectedly succeeded: {' '.join(args)}")
    assert expected in combined
    return combined
