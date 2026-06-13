import re
import uuid
import pytest 
from pathlib import Path

PROJECT_NAME = f"PRJ-{uuid.uuid4().hex[:6].upper()}"
# Repo root is two levels up: tests/brd_generator/brd_generator.py -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
BRD_V2_DOC = DATA_DIR / "YOU_BANK_BRD_V2.docx"
BRD_V3_DOC = DATA_DIR / "YOU_BANK_BRD_V3_Updated.docx"


pytestmark = [pytest.mark.brd, pytest.mark.regression]


@pytest.mark.smoke
@pytest.mark.order(1)
def test_01_open_sidebar_menu(shared_state) -> None:
    """Verify sidebar menu expands."""
    page = shared_state.page
    page.wait_for_load_state("networkidle")
    # Try multiple selectors to find and click the sidebar expand toggle
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
def test_02_navigate_to_brd_generator(shared_state) -> None:
    """Verify user can navigate to BRD Generator."""
    page = shared_state.page
    # Dismiss any overlay by pressing Escape and clicking
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception:
        pass
    brd_gen = page.locator("div").filter(has_text=re.compile(r"^BRD Generator$"))
    brd_gen.wait_for(state="visible", timeout=10000)
    brd_gen.click(force=True)


@pytest.mark.smoke
@pytest.mark.order(3)
def test_03_click_create_brd(shared_state) -> None:
    """Verify Create BRD option is available and clickable."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Create BRD$")).nth(2).click()
    # Click the correct send/arrow button using a robust selector
    send_btn = page.locator("button.embedded-action-btn.glossy-analyze-button.bg-\\[\\#3498B3\\]")
    if send_btn.count() > 0:
        send_btn.first.click()
    else:
        # Fallback: try to click the button with SVG send icon
        page.locator("button:has(svg.lucide-send)").first.click()


@pytest.mark.order(4)
def test_04_click_create_new_brd(shared_state) -> None:
    """Verify Create New BRD button is clickable."""
    page = shared_state.page
    page.get_by_role("button", name="Create New BRD").click()


@pytest.mark.order(5)
def test_05_select_project(shared_state) -> None:
    """Select the QUANTNIK SDLC - Dev project."""
    page = shared_state.page
    project_div = page.locator("div").filter(has_text=re.compile(r"^QUANTNIK SDLC - Dev$"))
    project_div.wait_for(state="visible", timeout=10000)
    project_div.click()


@pytest.mark.order(6)
def test_06_edit_project_name(shared_state) -> None:
    """Edit the project name."""
    page = shared_state.page
    page.get_by_role("button", name="Edit project name for this").click()
    page.get_by_role("textbox").nth(4).fill("")
    page.get_by_role("textbox").nth(4).fill(PROJECT_NAME)
    page.get_by_role("button", name="Confirm").click()


@pytest.mark.order(7)
def test_07_upload_brd_document(shared_state) -> None:
    """Upload a BRD document via the dropzone."""
    page = shared_state.page
    with page.expect_file_chooser() as fc_info:
        page.locator("div").filter(has_text=re.compile(r"^Drag & drop files here or click to browse$")).nth(1).click()
    file_chooser = fc_info.value
    if not BRD_V2_DOC.exists():
        pytest.fail(f"BRD source file not found: {BRD_V2_DOC}")
    file_chooser.set_files(str(BRD_V2_DOC))


@pytest.mark.order(8)
def test_08_proceed_after_upload(shared_state) -> None:
    """Click Proceed after file upload."""
    page = shared_state.page
    page.get_by_role("button", name="Proceed").click()


@pytest.mark.order(9)
def test_09_get_brd_summary(shared_state) -> None:
    """Wait for BRD generation and click Get a summary of the BRD."""
    page = shared_state.page
    summary_button_visible = False
    try:
        page.get_by_role("button", name="Get a summary of the BRD").wait_for(state="visible", timeout=300000)
        page.get_by_role("button", name="Get a summary of the BRD").click()
        summary_button_visible = True
    except Exception as e:
        print(f"BRD Generation failed or button not visible: {e}")
        summary_button_visible = False
    # Wait for 2 minutes to allow UI processing before next step if summary button was visible
    if summary_button_visible:
        page.wait_for_timeout(120000)
    # Store result in shared_state for step 10
    shared_state.summary_button_visible = summary_button_visible


@pytest.mark.order(10)
def test_10_open_prompt_library(shared_state) -> None:
    """Open Prompt Library and select Create BRD."""
    page = shared_state.page
    # If summary button was not visible in step 9, skip Prompt Library click and go directly to Create BRD
    if hasattr(shared_state, 'summary_button_visible') and not shared_state.summary_button_visible:
        page.locator("span").filter(has_text=re.compile(r"^Create BRD$")).click(force=True)
    else:
        # Click the Prompt Library using a robust selector
        prompt_library_div = page.locator(
            "div.flex.items-center.justify-between.px-3.cursor-pointer.transition-all.py-2_5"
        ).filter(
            has=page.locator("h3", has_text="Prompt Library")
        )
        if prompt_library_div.count() > 0:
            prompt_library_div.first.click()
        else:
            # Fallback: click by text
            page.locator("h3", has_text="Prompt Library").first.click()
        page.wait_for_timeout(1000)
        page.locator("span").filter(has_text=re.compile(r"^Create BRD$")).click(force=True)


@pytest.mark.order(11)
def test_11_click_action_button(shared_state) -> None:
    """Click the embedded action button."""
    page = shared_state.page
    btn = page.locator(".embedded-action-btn").first
    btn.wait_for(state="visible", timeout=120000)
    btn.click(timeout=120000)


@pytest.mark.order(12)
def test_12_click_update_existing_brd(shared_state) -> None:
    """Click Update Existing BRD button."""
    page = shared_state.page
    page.get_by_role("button", name="Update Existing BRD").click()


@pytest.mark.order(13)
def test_13_select_confluence_space(shared_state) -> None:
    """Select Confluence space and project."""
    page = shared_state.page
    page.locator("div").filter(has_text=re.compile(r"^Confluence1 Space$")).first.click()
    page.get_by_role("paragraph").filter(has_text=PROJECT_NAME).first.click()


@pytest.mark.order(14)
def test_14_upload_updated_document(shared_state) -> None:
    """Upload updated BRD document."""
    page = shared_state.page
    page.get_by_role("button", name="Upload Document").click()
    with page.expect_file_chooser() as fc_info:
        page.locator("div").filter(has_text=re.compile(r"^Drag & drop files here or click to browse$")).nth(1).click()
    file_chooser = fc_info.value
    if not BRD_V3_DOC.exists():
        pytest.fail(f"Updated BRD source file not found: {BRD_V3_DOC}")
    file_chooser.set_files(str(BRD_V3_DOC))


@pytest.mark.order(15)
def test_15_proceed_update(shared_state) -> None:
    """Click Proceed to update the BRD."""
    page = shared_state.page
    page.get_by_role("button", name="Proceed").click()


@pytest.mark.order(16)
def test_16_verify_confluence_link(shared_state) -> None:
    """Verify the updated BRD link opens in Confluence."""
    page = shared_state.page
    try:
        # Wait up to 30 seconds for the link to be visible
        link_locator = page.get_by_role("link", name=PROJECT_NAME).nth(1)
        link_locator.wait_for(state="visible", timeout=30000)
        with page.expect_popup() as page1_info:
            link_locator.click()
        page1 = page1_info.value
        page1.close()
        print("BRD updated successfully")
    except Exception as e:
        # Try to provide more info if the link is not found
        if not page.get_by_role("link", name=PROJECT_NAME).count():
            raise AssertionError(f"BRD updation failed: Link with name {PROJECT_NAME} not found. {e}") from e
        raise AssertionError(f"BRD updation failed: {e}") from e
