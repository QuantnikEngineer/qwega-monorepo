import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Each entry: test file path relative to PROJECT_ROOT.
# Agent name (used for reports + screenshot subfolder) = the test file stem.
TEST_FILES = [
    "tests/brd_generator/brd_generator.py",
    "tests/brd_summary/brd_summary.py",
    "tests/user_story_generator/user_story_generator_newuserstory.py",
    "tests/user_story_generator/user_story_generator_updatinguserstory.py",
    "tests/user_story_validator/user_story_validator.py",
    "tests/code_assistant/code_assistant.py",
    "tests/test_case/test_case.py",
    "tests/test_script/test_script.py",
    "tests/test_data/test_data.py",
    "tests/user_manual/user_manual.py",
]

try:
    import pytest_html  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pytest-html"])


def _load_config_defaults() -> dict:
    """Read defaults from data/config.json so we don't hard-code them here."""
    cfg_path = PROJECT_ROOT / "data" / "config.json"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[warn] Could not read {cfg_path}: {exc}")
        return {}


timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
reports_dir = PROJECT_ROOT / "reports"
reports_dir.mkdir(exist_ok=True)
screenshots_root = PROJECT_ROOT / "screenshots"
screenshots_root.mkdir(exist_ok=True)

cfg_defaults = _load_config_defaults()
base_url = (os.environ.get("BASE_URL") or cfg_defaults.get("BASE_URL") or "").rstrip("/")
headless = os.environ.get("HEADLESS", str(cfg_defaults.get("HEADLESS", "false")).lower())
marker = os.environ.get("TEST_MARKER", "")

print("\nConfiguration:")
print(f"  BASE_URL: {base_url}")
print(f"  HEADLESS: {headless}")
print(f"  TEST_MARKER: {marker or '(all tests)'}")
print("\nRunning each agent sequentially with its own HTML report (retries on failure)...")

summary = []

def _run_attempt(test_path, agent_name, attempt_num, report_path, marker):
    """Run pytest once for a given agent attempt with its own HTML report."""
    pytest_args = [
        "--disable-warnings",
        "--tb=short",
        f"--html={report_path}",
        "--self-contained-html",
    ]
    if marker:
        pytest_args.extend(["-m", marker])

    env = os.environ.copy()
    env["CURRENT_AGENT"] = agent_name
    env["CURRENT_ATTEMPT"] = str(attempt_num)

    return subprocess.run(
        [sys.executable, "-m", "pytest", test_path, *pytest_args],
        text=True,
        env=env,
        cwd=str(PROJECT_ROOT),
    )


for test_file in TEST_FILES:
    agent_name = Path(test_file).stem

    # Pre-create the per-agent screenshot folder so failure captures land in
    # screenshots/<agent_name>/<test>_attempt<N>_<timestamp>.png
    # (see conftest.py hook).
    agent_screenshot_dir = screenshots_root / agent_name
    agent_screenshot_dir.mkdir(parents=True, exist_ok=True)

    test_path = str(PROJECT_ROOT / test_file)

    report_file_attempt1 = reports_dir / f"{agent_name}_{timestamp}_attempt1.html"
    report_file_attempt2 = reports_dir / f"{agent_name}_{timestamp}_attempt2.html"

    print(f"\nRunning test file: {test_path} (first attempt)")
    print(f"  Screenshots on failure -> {agent_screenshot_dir}")
    print(f"  HTML report -> {report_file_attempt1}")
    result = _run_attempt(test_path, agent_name, 1, report_file_attempt1, marker)

    final_rc = result.returncode
    reports_for_agent = [str(report_file_attempt1)]

    if result.returncode != 0:
        print(f"Test file failed: {test_path} (retrying once)")
        print(f"  HTML report -> {report_file_attempt2}")
        result2 = _run_attempt(test_path, agent_name, 2, report_file_attempt2, marker)
        final_rc = result2.returncode
        reports_for_agent.append(str(report_file_attempt2))
        if result2.returncode != 0:
            print(f"Test file failed again: {test_path} (moving to next)")
        else:
            print(f"Test file passed on retry: {test_path}")
    else:
        print(f"Test file passed: {test_path}")

    summary.append(
        (agent_name, "PASSED" if final_rc == 0 else "FAILED", " | ".join(reports_for_agent))
    )

print("\n" + "=" * 70)
print("Test Suite Summary")
print("=" * 70)
for agent_name, status, report_file in summary:
    print(f"  {agent_name:55s} {status:7s}  {report_file}")
print("=" * 70)
print(f"\nIndividual HTML reports generated in: {reports_dir.resolve()}")
print(f"Failure screenshots (if any) saved in: {screenshots_root.resolve()}\\<agent_name>\\")
