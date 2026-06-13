import re
import uuid
import random
import pytest


pytestmark = [pytest.mark.codeassistant, pytest.mark.regression]


@pytest.mark.smoke
@pytest.mark.order(1)
def test_01_open_sidebar_menu(shared_state) -> None:
    """Verify sidebar menu expands."""
    page = shared_state.page
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    # Try multiple selectors to find and click the sidebar expand toggle
    sidebar_toggle = page.locator("text='»'").first
    if sidebar_toggle.is_visible():
        sidebar_toggle.click()
        page.wait_for_timeout(2000)
    else:
        # Fallback: look for the div containing only the » character
        sidebar_toggle = page.locator("div").filter(has_text=re.compile(r"^»$")).first
        sidebar_toggle.wait_for(state="visible", timeout=10000)
        sidebar_toggle.dispatch_event("click")
        page.wait_for_timeout(2000)


@pytest.mark.smoke
@pytest.mark.order(2)
def test_02_select_code_assistant(shared_state):
    """Verify user can navigate to Code Assistant."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Code Assistant$")).first.click(force=True)
    page.wait_for_timeout(2000)


@pytest.mark.smoke
@pytest.mark.order(3)
def test_03_click_code_generation_assistant(shared_state):
    """Verify Code Generation Assistant option is clickable."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Code Generation Assistant$")).nth(2).click()
    page.wait_for_timeout(2000)
    send_btn = page.locator("button.embedded-action-btn.glossy-analyze-button.bg-\\[\\#3498B3\\]")
    if send_btn.count() > 0:
        send_btn.first.click()
        page.wait_for_timeout(2000)
    else:
        # Fallback: try to click the button with SVG send icon
        page.locator("button:has(svg.lucide-send)").first.click()
        page.wait_for_timeout(2000)
        


@pytest.mark.order(4)
def test_04_configure_repo_and_branch(shared_state) -> None:
    """Verify repository name and branch can be configured."""
    page = shared_state.page
    repo_name = f"Repo_{uuid.uuid4().hex[:6].upper()}"
    branch_name = f"branch_{uuid.uuid4().hex[:6].lower()}"
    repo_field = page.get_by_role("textbox").nth(4)
    repo_field.wait_for(state="visible", timeout=300000)
    repo_field.click()
    repo_field.fill(repo_name)
    page.wait_for_timeout(2000)
    branch_field = page.get_by_role("textbox").nth(5)
    branch_field.click()
    branch_field.fill(branch_name)
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="Proceed").click()
    page.wait_for_timeout(10000)


@pytest.mark.order(5)
def test_05_submit_code_generation_query(shared_state) -> None:
    """Verify a code generation query can be submitted."""
    page = shared_state.page
    queries = [
        "Generate Hello World in Python",
        "Generate Hello World in Java",
        "Generate Fibonacci series in Python",
        "Generate a function to check if a number is prime in Python",
        "Generate a function to reverse a string in Java",
        "Write a Python Flask login page with form validation",
        "Create a responsive login page for a website using React",
        "Write a Node.js Express login endpoint with session handling",
    ]
    query_field = page.get_by_role("textbox", name="Enter your query here...")
    query_field.wait_for(state="visible", timeout=300000)
    query_field.click()
    query_field.fill(random.choice(queries))
    query_field.press("Enter")
    page.wait_for_timeout(120000)


@pytest.mark.order(6)
def test_06_verify_code_generation_and_push(shared_state) -> None:
    """Verify code is generated and can be pushed."""
    page = shared_state.page
    page.get_by_role("button", name="Push").wait_for(state="visible", timeout=300000)
    page.get_by_role("button", name="Push").click()
    page.wait_for_timeout(2000)


@pytest.mark.order(7)
def test_07_terminate_code_assistant(shared_state) -> None:
    """Verify Code Assistant can be terminated."""
    page = shared_state.page
    page.get_by_role("button", name="Terminate Code Assistant").wait_for(state="visible", timeout=300000)
    page.get_by_role("button", name="Terminate Code Assistant").click()
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="Yes").click()
