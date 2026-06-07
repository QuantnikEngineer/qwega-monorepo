import re
import uuid
import pytest


PROJECT_NAME = f"PRJ-{uuid.uuid4().hex[:6].upper()}"

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
def test_02_open_user_stories_validator(shared_state):
    """Verify user can navigate to User Stories Validator."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^User Stories Validator$")).click()


@pytest.mark.order(3)
def test_03_click_send_button(shared_state):
    """Verify send button is clickable."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Validate User Story$")).nth(2).click()
    send_btn = page.locator("button.embedded-action-btn.glossy-analyze-button.bg-\\[\\#3498B3\\]")
    if send_btn.count() > 0:
        send_btn.first.click()
    else:
        # Fallback: try to click the button with SVG send icon
        page.locator("button:has(svg.lucide-send)").first.click()


@pytest.mark.order(4)
def test_04_expand_confluence(shared_state):
    """Expand the Confluence section."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Confluence")).first.wait_for(state="visible", timeout=15000)
    page.locator("div").filter(has_text=re.compile(r"^Confluence")).first.click(force=True)


@pytest.mark.order(5)
def test_05_select_first_available_file(shared_state):
    """Dynamically select the first available file under Confluence."""
    page = shared_state.page
    page.locator(".w-4.h-4.rounded-full").first.wait_for(state="visible", timeout=15000)
    page.locator(".w-4.h-4.rounded-full").first.click(force=True)


@pytest.mark.order(6)
def test_06_click_jira_stories(shared_state):
    """Verify Jira stories section is clickable."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Jira0 Stories$")).first.click()


@pytest.mark.order(7)
def test_07_select_first_jira_file(shared_state):
    """Select the first available file under the Jira folder."""
    page = shared_state.page
    page.locator(".w-4.h-4.rounded").first.click()
    page.get_by_role("button", name="Proceed").click()


@pytest.mark.order(8)
def test_08_wait_for_stories(shared_state):
    """Wait for user stories to appear after proceeding (up to 10 minutes)."""
    page = shared_state.page
    page.locator("text=/WEGAAIDEMO-\\d+/").first.wait_for(state="visible", timeout=600000)


@pytest.mark.order(9)
def test_09_select_and_update_first_story(shared_state):
    """Dynamically select the first available user story under Jira and update it."""
    page = shared_state.page
    first_story = page.locator("text=/WEGAAIDEMO-\\d+/").first
    first_story.click()
    # Wait up to 10 minutes for the pencil icon to appear, click as soon as it is visible
    pencil_icon = page.locator(".lucide.lucide-pencil").first
    pencil_icon.wait_for(state="visible", timeout=600000)
    pencil_icon.click()
    page.get_by_role("button", name="Copy to Jira").click()
    page.get_by_role("button", name="Save").click()


@pytest.mark.order(10)
def test_10_select_and_update_second_story(shared_state):
    """Dynamically select the second available user story under Jira and update it."""
    page = shared_state.page
    stories = page.locator("text=/WEGAAIDEMO-\\d+/")
    if stories.count() > 1:
        stories.nth(1).click()
        page.locator(".lucide.lucide-pencil").first.click()
        page.get_by_role("button", name="Copy to Jira").click()
        page.get_by_role("button", name="Save").click()


@pytest.mark.order(11)
def test_11_checkboxes_and_save(shared_state):
    page = shared_state.page
    story_001_group = page.get_by_role("group").filter(has_text=re.compile(r"New_Story_001NEW"))
    story_001_group.get_by_role("checkbox").check()
    story_001_desc = story_001_group.locator("span, div, p").filter(has_text=re.compile(r"^- .+")).first
    story_001_desc.click()
    page.get_by_role("button", name="Save validated User Story").click(force=True)


@pytest.mark.order(12)
def test_12_create_testcases_for_stories(shared_state):
    """Click the Create Testcases for button."""
    page = shared_state.page
    page.get_by_role("button", name="Create Testcases for").click()
