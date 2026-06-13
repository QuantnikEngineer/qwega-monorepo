import re
import time
import pytest


pytestmark = [pytest.mark.testcase, pytest.mark.regression]


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
def test_02_click_test_case(shared_state) -> None:
    """Verify user can navigate to Test Case section."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Test Case$")).first.click()


@pytest.mark.smoke
@pytest.mark.order(3)
def test_03_click_create_test_cases(shared_state) -> None:
    """Verify Create Test Cases option is clickable."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Create Test Cases$")).nth(2).click()
    send_btn = page.locator("button.embedded-action-btn.glossy-analyze-button.bg-\\[\\#3498B3\\]")
    if send_btn.count() > 0:
        send_btn.first.click()
    else:
        # Fallback: try to click the button with SVG send icon
        page.locator("button:has(svg.lucide-send)").first.click()


@pytest.mark.order(4)
def test_04_click_send_button(shared_state):
    """Verify send button is clickable."""
    page = shared_state.page
    page.get_by_role("button", name="Greenfield").click()


@pytest.mark.order(5)
def test_05_expand_jira_section(shared_state) -> None:
    """Expand the Jira section to show Epics & User Stories."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Jira\d+ Stories?$")).first.wait_for(
        state="visible", timeout=30000
    )
    page.locator("div").filter(has_text=re.compile(r"^Jira\d+ Stories?$")).first.click()


@pytest.mark.order(6)
def test_06_expand_first_epic(shared_state) -> None:
    """Click the chevron on the first epic to expand and reveal user stories."""
    page = shared_state.page
    chevron = page.locator(".themed-scroll > div > div:nth-child(3) > div:nth-child(2) > .flex.items-center.space-x-2 > .lucide.lucide-chevron-right")
    chevron.wait_for(state="visible", timeout=15000)
    chevron.click()


@pytest.mark.order(7)
def test_07_select_first_user_story_checkbox(shared_state) -> None:
    """Select the first user story checkbox inside the expanded epic."""
    page = shared_state.page
    first_story_cb = page.locator("div:nth-child(2) > .pl-3 > div > .flex.items-center.space-x-2 > .w-4").first
    first_story_cb.wait_for(state="visible", timeout=15000)
    first_story_cb.click()


@pytest.mark.order(8)
def test_08_select_functional_only(shared_state) -> None:
    """Select only the 'Functional' scenario type checkbox."""
    page = shared_state.page
    functional_row = page.get_by_text("Functional", exact=True).locator('..')
    checkbox = functional_row.locator('.w-4').first
    checkbox.wait_for(state="visible", timeout=120000)
    checkbox.click()


@pytest.mark.order(9)
def test_09_click_proceed(shared_state) -> None:
    """Click Proceed to start test case generation."""
    page = shared_state.page
    proceed_btn = page.get_by_role("button", name="Proceed")
    proceed_btn.wait_for(state="visible", timeout=30000)
    for _ in range(120):
        if proceed_btn.is_enabled():
            break
    proceed_btn.click()


@pytest.mark.order(10)
def test_09_wait_for_cron_job_success(shared_state) -> None:
    """Wait for the Cron Job Status to show success by refreshing repeatedly."""
    page = shared_state.page

    page.locator("div").filter(has_text=re.compile(r"^Cron Job Status\d+ Jobs?$")).first.wait_for(
        state="visible", timeout=60000
    )
    page.locator("div").filter(has_text=re.compile(r"^Cron Job Status\d+ Jobs?$")).first.click()

    max_attempts = 60
    wait_between = 60
    success_found = False

    for attempt in range(max_attempts):
        refresh_btn = page.get_by_role("button", name="Refresh status")
        refresh_btn.wait_for(state="visible", timeout=15000)
        refresh_btn.click()

        try:
            completed_locator = page.locator("text=COMPLETED")
            if completed_locator.count() > 0 and completed_locator.first.is_visible():
                success_found = True
                print(f"Cron job completed with success after {attempt + 1} refresh(es)")
                break
        except Exception:
            pass

        print(f"Refresh attempt {attempt + 1}/{max_attempts} - still waiting...")
        time.sleep(wait_between)

    assert success_found, f"Cron job did not show success after {max_attempts} refresh attempts"


@pytest.mark.order(11)
def test_11_click_generate_test_scripts(shared_state) -> None:
    """Click Generate Test Scripts button."""
    page = shared_state.page
    try:
        page.get_by_role("button", name="Generate test scripts").click(timeout=30000)
        print("Test case agent is working fine")
    except Exception:
        pytest.fail("Test case agent is not working")
