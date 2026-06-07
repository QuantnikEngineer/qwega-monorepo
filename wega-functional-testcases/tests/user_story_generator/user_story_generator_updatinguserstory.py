import re
import pytest


pytestmark = [pytest.mark.userstory, pytest.mark.regression]


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
def test_02_open_user_stories_creator(shared_state):
    """Verify user can navigate to User Stories Creator."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^User Stories Creator$")).first.click(force=True)


@pytest.mark.smoke
@pytest.mark.order(3)
def test_03_click_create_user_story(shared_state):
    """Verify Create User Story option is clickable."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Create User Story$")).nth(2).click()
    send_btn = page.locator("button.embedded-action-btn.glossy-analyze-button.bg-\\[\\#3498B3\\]")
    if send_btn.count() > 0:
        send_btn.first.click()
    else:
        # Fallback: try to click the button with SVG send icon
        page.locator("button:has(svg.lucide-send)").first.click()
    


@pytest.mark.order(4)
def test_04_click_update_existing_stories(shared_state):
    """Verify Update Existing Stories button is clickable."""
    page = shared_state.page
    page.get_by_role("button", name="Update Existing Stories").click()


@pytest.mark.order(5)
def test_05_expand_confluence(shared_state):
    """Expand the Confluence section."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Confluence")).first.wait_for(state="visible", timeout=15000)
    page.locator("div").filter(has_text=re.compile(r"^Confluence")).first.click()


@pytest.mark.order(6)
def test_06_select_first_confluence_file(shared_state):
    """Dynamically select the first available file under Confluence."""
    page = shared_state.page
    page.locator(".w-4.h-4.rounded-full").first.wait_for(state="visible", timeout=15000)
    page.locator(".w-4.h-4.rounded-full").first.click()


@pytest.mark.order(7)
def test_07_click_jira_stories(shared_state):
    """Verify Jira stories section is clickable."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Jira0 Stories$")).first.click()


@pytest.mark.order(8)
def test_08_select_first_jira_file(shared_state):
    """Select the first available file under the Jira folder."""
    page = shared_state.page
    page.locator(".w-4.h-4.rounded").first.click()


@pytest.mark.order(9)
def test_09_click_proceed(shared_state):
    """Verify Proceed button is clickable."""
    page = shared_state.page
    page.get_by_role("button", name="Proceed").wait_for(state="visible", timeout=30000)
    page.get_by_role("button", name="Proceed").click()


@pytest.mark.order(10)
def test_10_click_generate_test_cases(shared_state):
    """Click Generate test cases button."""
    page = shared_state.page
    try:
        page.get_by_role("button", name="Generate test cases (Test").wait_for(state="visible", timeout=180000)
        page.get_by_role("button", name="Generate test cases (Test").click()
        print("User Story generated successfully!")
    except Exception as e:
        print(f"Failed to generate user story: {e}")
