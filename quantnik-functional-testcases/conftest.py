import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.config_loader import load_config  # noqa: E402

_CFG = load_config()
BASE_URL = _CFG["BASE_URL"]
HEADLESS = _CFG["HEADLESS"]
TEST_EMAIL = _CFG["TEST_EMAIL"]
TEST_PASSWORD = _CFG["TEST_PASSWORD"]

SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
REPORTS_DIR = PROJECT_ROOT / "reports"


class SharedState:
    """Shared state container for Playwright page object."""
    def __init__(self, page):
        self.page = page


@pytest.fixture(scope="module")
def shared_state():
    """Shared browser fixture that reads config from data/config.json."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--start-maximized"],
        )
        context = browser.new_context(no_viewport=True)
        page = context.new_page()

        print(f"Navigating to: {BASE_URL}/login")
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.wait_for_timeout(2000)

        print("Filling login form...")
        email_field = page.get_by_role("textbox", name="Email")
        email_field.wait_for(state="visible", timeout=30000)
        email_field.fill(TEST_EMAIL)

        password_field = page.get_by_role("textbox", name="Password")
        password_field.fill(TEST_PASSWORD)

        print("Clicking Sign in...")
        page.get_by_role("button", name="Sign in").click()

        print("Waiting for login redirect...")
        try:
            page.wait_for_url("**/execute**", timeout=60000)
            print("Successfully logged in and redirected to /execute")
        except Exception as e:
            print(f"Login redirect failed: {e}")
            page.wait_for_load_state("networkidle")
            page.goto(f"{BASE_URL}/execute", wait_until="networkidle")

        page.wait_for_timeout(3000)
        print(f"Current URL: {page.url}")

        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        except Exception:
            pass

        try:
            page.mouse.click(960, 400)
            page.wait_for_timeout(500)
        except Exception:
            pass

        print("Login successful, ready to run tests")

        try:
            page.evaluate("window.scrollTo(0, 0)")
        except Exception as e:
            print(f"Scroll reset failed: {e}")

        state = SharedState(page)
        yield state

        context.close()
        browser.close()


def _infer_report_basename(config) -> str:
    """Pick a sensible HTML report filename when one wasn't passed on the CLI.

    Priority order:
      1. CURRENT_AGENT env var (set by run_test.py).
      2. Stem of the first .py file in pytest's positional args.
      3. "pytest_run" as a generic fallback.
    """
    env_name = os.environ.get("CURRENT_AGENT")
    if env_name:
        return env_name

    for arg in getattr(config, "args", []) or []:
        if not isinstance(arg, str):
            continue
        # Strip "::test_name" suffix if user pointed at a specific test.
        path_part = arg.split("::", 1)[0]
        if path_part.endswith(".py"):
            return Path(path_part).stem

    return "pytest_run"


def pytest_configure(config):
    """Register custom markers and auto-create an HTML report when none is set."""
    config.addinivalue_line("markers", "smoke: Quick smoke tests for basic functionality")
    config.addinivalue_line("markers", "regression: Full regression test suite")
    config.addinivalue_line("markers", "brd: BRD Generator related tests")
    config.addinivalue_line("markers", "userstory: User Story related tests")
    config.addinivalue_line("markers", "testcase: Test Case generation tests")
    config.addinivalue_line("markers", "testscript: Test Script generation tests")
    config.addinivalue_line("markers", "testdata: Test Data generation tests")
    config.addinivalue_line("markers", "codeassistant: Code Assistant tests")
    config.addinivalue_line("markers", "usermanual: User Manual tests")

    # Auto-inject an HTML report path when the user runs pytest directly
    # (e.g. `pytest tests/brd_generator/brd_generator.py`) and didn't pass
    # `--html` themselves. run_test.py passes its own --html, so this is a no-op there.
    if config.pluginmanager.hasplugin("html"):
        htmlpath = config.getoption("htmlpath", default=None)
        if not htmlpath:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            basename = _infer_report_basename(config)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            auto_path = REPORTS_DIR / f"{basename}_{timestamp}.html"
            config.option.htmlpath = str(auto_path)
            if not getattr(config.option, "self_contained_html", False):
                config.option.self_contained_html = True
            print(f"[pytest-html] Auto report -> {auto_path}")


def _agent_name_for(item):
    """Return the agent name for a given test item.

    Priority order:
      1. CURRENT_AGENT env var (set by run_test.py per agent).
      2. The parent folder name under tests/ (e.g. tests/brd_generator -> brd_generator).
      3. The test module file stem.
    """
    env_name = os.environ.get("CURRENT_AGENT")
    if env_name:
        return env_name

    test_path = Path(str(item.fspath)).resolve()
    try:
        rel = test_path.relative_to(PROJECT_ROOT / "tests")
        if len(rel.parts) > 1:
            return rel.parts[0]
    except ValueError:
        pass

    return test_path.stem


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture a screenshot when a test fails, organized under screenshots/<agent>/."""
    outcome = yield
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return

    # Skip screenshot on the first attempt - the test will be retried by run_test.py.
    # Only capture screenshots on the retry (attempt 2) or when no attempt env var is set
    # (e.g. when pytest is invoked directly without run_test.py).
    attempt = os.environ.get("CURRENT_ATTEMPT")
    if attempt == "1":
        return

    shared = item.funcargs.get("shared_state") if hasattr(item, "funcargs") else None
    if shared is None or getattr(shared, "page", None) is None:
        return

    page = shared.page
    agent_name = _agent_name_for(item)
    folder = SCREENSHOTS_DIR / agent_name
    try:
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        attempt_tag = f"_attempt{attempt}" if attempt else ""
        screenshot_path = folder / f"{item.name}{attempt_tag}_{timestamp}.png"
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass
        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"\n[screenshot] Failure captured: {screenshot_path}")
        if hasattr(report, "extra"):
            try:
                from pytest_html import extras  # type: ignore

                report.extra = list(getattr(report, "extra", []) or []) + [
                    extras.image(str(screenshot_path)),
                    extras.url(str(screenshot_path)),
                ]
            except Exception:
                pass
    except Exception as exc:
        print(f"\n[screenshot] Failed to capture screenshot for {item.name}: {exc}")
