import re
import time
import pytest


JIRA_SEARCH_IDS = [
    "WEGAAIDEMO-59174", "WEGAAIDEMO-59173", "WEGAAIDEMO-59172", "WEGAAIDEMO-59171", 
    "WEGAAIDEMO-59169", "WEGAAIDEMO-59170", "WEGAAIDEMO-59168", "WEGAAIDEMO-59159", 
    "WEGAAIDEMO-59158", "WEGAAIDEMO-59157", "WEGAAIDEMO-59156", "WEGAAIDEMO-59155", 
    "WEGAAIDEMO-59149", "WEGAAIDEMO-59147", "WEGAAIDEMO-59148", "WEGAAIDEMO-59145", 
    "WEGAAIDEMO-59143", "WEGAAIDEMO-59144", "WEGAAIDEMO-59106", "WEGAAIDEMO-59105", 
    "WEGAAIDEMO-59103", "WEGAAIDEMO-59104", "WEGAAIDEMO-59101", "WEGAAIDEMO-59100", 
    "WEGAAIDEMO-59099", "WEGAAIDEMO-59098", "WEGAAIDEMO-59096", "WEGAAIDEMO-59095", 
    "WEGAAIDEMO-59094", "WEGAAIDEMO-59093", "WEGAAIDEMO-59084", "WEGAAIDEMO-59083", 
    "WEGAAIDEMO-59081", "WEGAAIDEMO-59082", "WEGAAIDEMO-59080", "WEGAAIDEMO-59079", 
    "WEGAAIDEMO-59077", "WEGAAIDEMO-59076", "WEGAAIDEMO-59074", "WEGAAIDEMO-59075", 
    "WEGAAIDEMO-59070", "WEGAAIDEMO-59071", "WEGAAIDEMO-59069", "WEGAAIDEMO-59068", 
    "WEGAAIDEMO-59067","WEGAAIDEMO-59164"]

pytestmark = [pytest.mark.testdata, pytest.mark.regression]


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
def test_02_click_test_data(shared_state) -> None:
    """Navigate to Test Data section."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Test Data$")).first.click()


@pytest.mark.smoke
@pytest.mark.order(3)
def test_03_click_create_test_data(shared_state) -> None:
    """Click Create Test Data option."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Create Test Data$")).nth(2).click()
    send_btn = page.locator("button.embedded-action-btn.glossy-analyze-button.bg-\\[\\#3498B3\\]")
    if send_btn.count() > 0:
        send_btn.first.click()
    else:
        # Fallback: try to click the button with SVG send icon
        page.locator("button:has(svg.lucide-send)").first.click()


@pytest.mark.order(4)
def test_04_expand_jira_section(shared_state) -> None:
    """Expand the Jira section and wait for epics to load."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Jira\d+ Stories?$")).first.wait_for(
        state="visible", timeout=30000
    )
    page.locator("div").filter(has_text=re.compile(r"^Jira\d+ Stories?$")).first.click()
    page.locator(".pl-3").first.wait_for(state="visible", timeout=30000)
    time.sleep(2)
    print("Jira section expanded and epics loaded")


@pytest.mark.order(5)
def test_05_search_and_select_user_story(shared_state) -> None:
    """Search for a Jira ID dynamically."""
    page = shared_state.page
    search_box = page.get_by_role("textbox", name="Search by Jira ID, epic, or")

    found = False
    for jira_id in JIRA_SEARCH_IDS:
        print(f"Searching for: {jira_id}")
        search_box.click()
        search_box.fill("")
        search_box.fill(jira_id)
        page.wait_for_load_state("networkidle")
        time.sleep(5)

        result_cb = page.locator(".pl-3 > div > .flex.items-center.space-x-2 > .w-4").first
        try:
            result_cb.wait_for(state="visible", timeout=15000)
            print(f"  Found result for {jira_id} - selecting")
            result_cb.click()
            time.sleep(1)
            found = True
            break
        except Exception:
            print(f"  No result for {jira_id} - trying next")
            search_box.fill("")
            time.sleep(2)

    assert found, f"None of the Jira IDs {JIRA_SEARCH_IDS} returned results"


@pytest.mark.order(6)
def test_06_expand_and_select_all_test_cases(shared_state) -> None:
    """Click the Test Cases button and select all test cases."""
    page = shared_state.page
    page.get_by_role("button", name="Test Cases").click()
    page.get_by_title("Select all test cases").click()
    time.sleep(1)


@pytest.mark.order(7)
def test_07_click_proceed(shared_state) -> None:
    """Click Proceed to start test data generation."""
    page = shared_state.page
    proceed_btn = page.get_by_role("button", name="Proceed")
    proceed_btn.wait_for(state="visible", timeout=30000)
    for _ in range(120):
        if proceed_btn.is_enabled():
            break
        time.sleep(0.5)
    proceed_btn.click()


@pytest.mark.order(8)
def test_08_view_generated_test_data(shared_state) -> None:
    """Click View Generated Test Data link."""
    page = shared_state.page
    link = page.get_by_role("link", name="View Generated Test Data")
    link.wait_for(state="visible", timeout=120000)
    with page.expect_popup() as page1_info:
        link.click()
    page1 = page1_info.value
    print(f"Popup opened: {page1.url}")
    page1.close()
    print("Test data generation completed successfully!")
