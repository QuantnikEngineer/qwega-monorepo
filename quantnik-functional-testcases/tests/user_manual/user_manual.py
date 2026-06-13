import re
import uuid
import pytest


PROJECT_NAME = f"PRJ-{uuid.uuid4().hex[:6].upper()}"

pytestmark = [pytest.mark.usermanual, pytest.mark.regression]


@pytest.mark.smoke
@pytest.mark.order(1)
def test_01_open_sidebar_menu(shared_state) -> None:
    """Verify sidebar menu expands."""
    page = shared_state.page
    page.wait_for_load_state("networkidle")
    # Try multiple selectors to find and click the sidebar expand toggle
    sidebar_toggle = page.locator("text='»'").first
    if sidebar_toggle.is_visible():
        sidebar_toggle.click()
    else:
        # Fallback: look for the div containing only the » character
        sidebar_toggle = page.locator("div").filter(has_text=re.compile(r"^»$")).first
        sidebar_toggle.wait_for(state="visible", timeout=10000)
        sidebar_toggle.dispatch_event("click")



@pytest.mark.smoke
@pytest.mark.order(2)
def test_02_select_user_manual(shared_state):
    """Verify user can navigate to User Manual."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^User Manual$")).first.click(force=True)


@pytest.mark.smoke
@pytest.mark.order(3)
def test_03_click_create_user_manual(shared_state):
    """Verify Create User Manual option is clickable."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Create User Manual$")).nth(2).click()
    send_btn = page.locator("button.embedded-action-btn.glossy-analyze-button.bg-\\[\\#3498B3\\]")
    if send_btn.count() > 0:
        send_btn.first.click()
    else:
        # Fallback: try to click the button with SVG send icon
        page.locator("button:has(svg.lucide-send)").first.click()


@pytest.mark.order(4)
def test_04_fill_project_fields(shared_state):
    """Fill Project Name and Source URL fields."""
    page = shared_state.page
    page.get_by_role("textbox", name="Project Name *").click()
    page.get_by_role("textbox", name="Project Name *").fill(PROJECT_NAME)
    page.get_by_role("textbox", name="Source URL (SharePoint folder").click()
    page.get_by_role("textbox", name="Source URL (SharePoint folder").fill("https://quantnikbuildiq.atlassian.net/wiki/spaces/WAAD/pages/104464404/PRJ-Test1")


@pytest.mark.order(5)
def test_05_click_proceed(shared_state):
    """Click the Proceed button after filling fields."""
    page = shared_state.page
    page.get_by_role("button", name="Proceed").click()


@pytest.mark.order(6)
def test_06_handle_popup(shared_state):
    """Handle the popup window after clicking Proceed."""
    page = shared_state.page
    try:
        page.wait_for_timeout(180000)
        with page.expect_popup() as page1_info:
            page.get_by_role("link", name=PROJECT_NAME).click()
        page1 = page1_info.value
        page1.close()
        print("User manual agent is working fine")
    except Exception as e:
        pytest.fail(f"User manual agent is not working: {e}")
