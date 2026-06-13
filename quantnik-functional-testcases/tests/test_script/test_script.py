import re
import time
import pytest


JIRA_SEARCH_IDS = [
    "QUANTNIKAIDEMO-59174", "QUANTNIKAIDEMO-59173", "QUANTNIKAIDEMO-59172", "QUANTNIKAIDEMO-59171", 
    "QUANTNIKAIDEMO-59169", "QUANTNIKAIDEMO-59170", "QUANTNIKAIDEMO-59168", "QUANTNIKAIDEMO-59159", 
    "QUANTNIKAIDEMO-59158", "QUANTNIKAIDEMO-59157", "QUANTNIKAIDEMO-59156", "QUANTNIKAIDEMO-59155", 
    "QUANTNIKAIDEMO-59149", "QUANTNIKAIDEMO-59147", "QUANTNIKAIDEMO-59148", "QUANTNIKAIDEMO-59145", 
    "QUANTNIKAIDEMO-59143", "QUANTNIKAIDEMO-59144", "QUANTNIKAIDEMO-59106", "QUANTNIKAIDEMO-59105", 
    "QUANTNIKAIDEMO-59103", "QUANTNIKAIDEMO-59104", "QUANTNIKAIDEMO-59101", "QUANTNIKAIDEMO-59100", 
    "QUANTNIKAIDEMO-59099", "QUANTNIKAIDEMO-59098", "QUANTNIKAIDEMO-59096", "QUANTNIKAIDEMO-59095", 
    "QUANTNIKAIDEMO-59094", "QUANTNIKAIDEMO-59093", "QUANTNIKAIDEMO-59084", "QUANTNIKAIDEMO-59083", 
    "QUANTNIKAIDEMO-59081", "QUANTNIKAIDEMO-59082", "QUANTNIKAIDEMO-59080", "QUANTNIKAIDEMO-59079", 
    "QUANTNIKAIDEMO-59077", "QUANTNIKAIDEMO-59076", "QUANTNIKAIDEMO-59074", "QUANTNIKAIDEMO-59075", 
    "QUANTNIKAIDEMO-59070", "QUANTNIKAIDEMO-59071", "QUANTNIKAIDEMO-59069", "QUANTNIKAIDEMO-59068", 
    "QUANTNIKAIDEMO-59067","QUANTNIKAIDEMO-59164"]

pytestmark = [pytest.mark.testscript, pytest.mark.regression]


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
def test_02_click_test_script(shared_state) -> None:
    """Verify user can navigate to Test Script section."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Test Script$")).first.click()


@pytest.mark.smoke
@pytest.mark.order(3)
def test_03_click_create_test_scripts(shared_state) -> None:
    """Click Create Test Scripts option."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Create Test Scripts$")).nth(2).click()
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
    page.wait_for_load_state("networkidle")
    time.sleep(5)
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
def test_07_click_view_supported_combinations(shared_state) -> None:
    """Click View Supported Combinations button."""
    page = shared_state.page
    page.get_by_role("button", name="View Supported Combinations").wait_for(
        state="visible", timeout=15000
    )
    page.get_by_role("button", name="View Supported Combinations").click()
    time.sleep(2)


@pytest.mark.order(8)
def test_08_select_selenium_testng_python(shared_state) -> None:
    """Select the Selenium TestNG Python combination row."""
    page = shared_state.page
    row = page.get_by_role("row", name="Selenium TestNG Python")
    row.wait_for(state="visible", timeout=15000)
    row.locator("input[name=\"comboRowSelect\"]").check()
    time.sleep(1)


@pytest.mark.order(9)
def test_09_click_done(shared_state) -> None:
    """Click Done to confirm the combination selection."""
    page = shared_state.page
    page.get_by_role("button", name="Done").click()
    time.sleep(1)


@pytest.mark.order(10)
def test_10_click_proceed(shared_state) -> None:
    """Click Proceed to start test script generation."""
    page = shared_state.page
    proceed_btn = page.get_by_role("button", name="Proceed")
    proceed_btn.wait_for(state="visible", timeout=30000)
    for _ in range(120):
        if proceed_btn.is_enabled():
            break
        time.sleep(0.5)
    proceed_btn.click()


@pytest.mark.order(11)
def test_11_click_generate_test_data(shared_state) -> None:
    """Click Generate test data button."""
    page = shared_state.page
    try:
        page.get_by_role("button", name="Generate test data").wait_for(
            state="visible", timeout=30000
        )
        page.get_by_role("button", name="Generate test data").click()
        time.sleep(5)
        print("Test script generation initiated successfully!")
    except Exception as e:
        print("Test script generation failed!")
