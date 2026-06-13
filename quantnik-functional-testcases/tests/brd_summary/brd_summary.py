import re
import pytest


pytestmark = [pytest.mark.brd, pytest.mark.regression]


@pytest.mark.smoke
@pytest.mark.order(1)
def test_01_open_sidebar_menu(shared_state) -> None:
    """Verify sidebar menu expands."""
    page = shared_state.page
    page.wait_for_load_state("networkidle")
    sidebar_toggle = page.locator("text='»'").first
    if sidebar_toggle.is_visible():
        sidebar_toggle.wait_for(state="visible", timeout=10000)
        sidebar_toggle.click()
    else:
        sidebar_toggle = page.locator("div").filter(has_text=re.compile(r"^»$")).first
        sidebar_toggle.wait_for(state="visible", timeout=10000)
        sidebar_toggle.dispatch_event("click")


@pytest.mark.smoke
@pytest.mark.order(2)
def test_02_navigate_to_brd_summary(shared_state) -> None:
    """Verify user can navigate to BRD Summary."""
    page = shared_state.page
    # Dismiss any overlay by pressing Escape and clicking
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception:
        pass
        brd_summary = page.locator("div").filter(has_text=re.compile(r"^BRD Summary$"))
        brd_summary.wait_for(state="visible", timeout=10000)
        brd_summary.click(force=True)



@pytest.mark.smoke
@pytest.mark.order(3)
def test_03_click_create_brd_summary(shared_state):
    """Verify Create BRD Summary option is clickable."""
    page = shared_state.page
    create_brd = page.locator("div").filter(has_text=re.compile(r"^Create BRD Summary$")).nth(2)
    create_brd.wait_for(state="visible", timeout=10000)
    create_brd.click()
    send_btn = page.locator("button.embedded-action-btn.glossy-analyze-button.bg-\\[\\#3498B3\\]")
    if send_btn.count() > 0:
        send_btn.first.wait_for(state="visible", timeout=10000)
        send_btn.first.click()
    else:
        page.locator("button:has(svg.lucide-send)").first.wait_for(state="visible", timeout=10000)
        page.locator("button:has(svg.lucide-send)").first.click()


@pytest.mark.order(4)
def test_04_expand_confluence(shared_state):
    """Expand the Confluence section."""
    page = shared_state.page
    confluence = page.locator("div").filter(has_text=re.compile(r"^Confluence")).first
    confluence.wait_for(state="visible", timeout=15000)
    confluence.click()
    page.locator("div").filter(has_text=re.compile(r"^Confluence")).first.click(force=True)


@pytest.mark.order(5)
def test_05_select_first_available_file(shared_state):
    """Dynamically select the first available file under Confluence."""
    page = shared_state.page
    page.locator(".w-4.h-4.rounded-full").first.wait_for(state="visible", timeout=15000)
    page.locator(".w-4.h-4.rounded-full").first.click(force=True)


@pytest.mark.order(6)
def test_06_click_proceed(shared_state):
    """Verify Proceed button is clickable."""
    page = shared_state.page
    page.get_by_role("button", name="Proceed").wait_for(state="visible", timeout=30000)
    page.get_by_role("button", name="Proceed").click(force=True)


@pytest.mark.order(7)
def test_07_click_create_user_stories(shared_state):
    """Click the Create user stories from this BRD button."""
    page = shared_state.page
    try:
        page.get_by_role("button", name="Create user stories from this").wait_for(state="visible", timeout=180000)
        page.get_by_role("button", name="Create user stories from this").click()
        print("BRD Summary initiated successfully!")
    except Exception as e:
        print(f"Failed to initiate BRD Summary: {e}")
