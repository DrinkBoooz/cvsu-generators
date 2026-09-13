import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"

def test_playwright_roster_mapping_modal_and_ceit_help():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)

        # 1. Verify modal is initially hidden
        modal = page.locator("#modalRosterMappingBackdrop")
        assert modal.is_hidden(), "Mapping modal must be hidden initially"

        # 2. Verify Help Drawer Tab switching & CEIT Directory
        page.click("#btnOpenHelp")
        help_drawer = page.locator("#helpDrawer")
        assert help_drawer.is_visible(), "Help drawer should open"

        # Switch to Naming tab
        page.click("#helpTabNaming")
        naming_content = page.locator("#helpContentNaming")
        assert naming_content.is_visible(), "Naming guidelines should be visible"

        # Verify CEIT Directory Table is rendered
        ceit_table = page.locator("#ceitPrefixTable")
        assert ceit_table.is_visible(), "CEIT directory table must be visible"

        # Check for key prefixes in the table
        assert "COSC" in ceit_table.inner_text()
        assert "CPEN" in ceit_table.inner_text()
        assert "AGEN" in ceit_table.inner_text()
        assert "ITEC" in ceit_table.inner_text()
        assert "DCIT" in ceit_table.inner_text()

        # Test filterHelpContent search
        search_input = page.locator("#helpSearchInput")
        search_input.fill("DCEE")
        page.wait_for_timeout(200)
        assert "DCEE" in ceit_table.inner_text()

        # Close help drawer
        page.click("#btnCloseHelp")

        # 3. Simulate client-side roster rendering with CEIT metadata and custom mapping
        mock_js = """
        () => {
            window.pywebview = {
                api: {
                    inspect_roster: async (fn, cfg) => ({
                        status: "ok",
                        filename: fn,
                        format: "csv",
                        detected_header_row: 0,
                        detected_name_column: 0,
                        detected_id_column: 1,
                        raw_rows: [
                            ["Name", "Student number", "Email", "Remarks"],
                            ["Ortega, Dan", "20261001", "dan@cvsu.edu.ph", "Regular"],
                            ["Santos, Maria", "20261002", "maria@cvsu.edu.ph", "Regular"]
                        ],
                        available_columns: [
                            {index: 0, name: "Col A: Name"},
                            {index: 1, name: "Col B: Student number"},
                            {index: 2, name: "Col C: Email"},
                            {index: 3, name: "Col D: Remarks"}
                        ],
                        parsed_students: [
                            {name: "Ortega, Dan", student_number: "20261001"},
                            {name: "Santos, Maria", student_number: "20261002"}
                        ],
                        student_count: 2,
                        ceit_metadata: {
                            prefix: "COSC",
                            department_code: "DIT",
                            department_name: "Department of Information Technology"
                        }
                    }),
                    validate_rosters: async (cfg) => state.rosterReports,
                    detect_classes: async (cfg) => state.detectedClasses
                }
            };

            state.rosters = ["mock_students_COSC.csv"];
            state.detectedClasses = [{
                id: "cls_1",
                course_sec: "BSCS 3-1",
                schedule_code: "202612040",
                subject_name: "COSC 70 - SOFTWARE ENGINEERING",
                schedule_desc: "Mon 7:00AM - 10:00AM",
                detected_type: "lecture_lab",
                ceit_metadata: {
                    prefix: "COSC",
                    department_code: "DIT",
                    department_name: "Department of Information Technology",
                    badge: "COSC · DIT"
                }
            }];
            state.rosterReports = [{
                filename: "mock_students_COSC.csv",
                status: "valid",
                student_count: 2,
                column_count: 2,
                ceit_metadata: {
                    prefix: "COSC",
                    department_code: "DIT",
                    department_name: "Department of Information Technology",
                    badge: "COSC · DIT"
                }
            }];
            renderRosterStatus();
            renderClassesSection();
        }
        """
        page.evaluate(mock_js)

        # Verify CEIT pill badge in roster row
        ceit_pill = page.locator(".roster-row .badge-ceit-pill")
        assert ceit_pill.is_visible(), "CEIT badge must be visible in roster row"
        assert "COSC · DIT" in ceit_pill.inner_text()

        # Verify ⚙️ Map button is present
        btn_map = page.locator(".btn-map-columns")
        assert btn_map.is_visible(), "Map Columns button must be visible"

        # 4. Open Column Mapping Modal
        btn_map.click()
        page.wait_for_timeout(300)
        assert modal.is_visible(), "Mapping modal must open upon clicking Map button"

        # Check spreadsheet table rendering
        table = page.locator("#mapSpreadsheetTableContainer table")
        assert table.is_visible(), "Raw spreadsheet preview table must be rendered"
        assert "Col A" in table.inner_text()
        assert "Col B" in table.inner_text()

        # Check parsed preview students
        parsed_preview = page.locator("#mapParsedStudentsPreview")
        assert "Ortega, Dan" in parsed_preview.inner_text()
        assert "20261001" in parsed_preview.inner_text()

        # Check class card in Step 3 has CEIT badge
        class_pill = page.locator("#classesListContainer .badge-ceit-pill")
        assert class_pill.is_visible(), "Class card in Step 3 must display CEIT badge"
        assert "COSC · DIT" in class_pill.inner_text()

        # Close the modal
        page.click("#btnCloseMappingModal")
        page.wait_for_timeout(200)
        assert modal.is_hidden(), "Modal should close"

        browser.close()

def test_playwright_incomplete_filename_fallback_and_recommendation():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)

        # Simulate roster with incomplete filename (e.g. CS1-4 DCIT21.xlsx)
        mock_js = """
        () => {
            window.pywebview = {
                api: {
                    inspect_roster: async (fn, cfg) => ({
                        status: "ok",
                        filename: fn,
                        format: "xlsx",
                        detected_header_row: 0,
                        detected_name_column: 0,
                        detected_id_column: 1,
                        raw_rows: [
                            ["Name", "Student number"],
                            ["Ortega, Dan", "20261001"]
                        ],
                        available_columns: [
                            {index: 0, name: "Col A: Name"},
                            {index: 1, name: "Col B: Student number"}
                        ],
                        parsed_students: [
                            {name: "Ortega, Dan", student_number: "20261001"}
                        ],
                        student_count: 1,
                        filename_hints: {
                            course_sec: "BSCS 1-4",
                            schedule_code: "",
                            subject_prefix: "DCIT",
                            subject_code: "DCIT 21",
                            subject_name: "DCIT 21",
                            recommended_filename: "BSCS1-4 List of Students for 202612040-DCIT 21 - COMPUTER PROGRAMMING I.xlsx"
                        },
                        recommended_filename: "BSCS1-4 List of Students for 202612040-DCIT 21 - COMPUTER PROGRAMMING I.xlsx",
                        ceit_metadata: {
                            prefix: "DCIT",
                            department_code: "DIT",
                            department_name: "Department of Information Technology"
                        }
                    }),
                    validate_rosters: async (cfg) => state.rosterReports,
                    detect_classes: async (cfg) => state.detectedClasses
                }
            };

            state.rosters = ["CS1-4 DCIT21.xlsx"];
            state.detectedClasses = [{
                id: "cls_101",
                course_sec: "BSCS 1-4",
                schedule_code: "202612040",
                subject_name: "DCIT 21 - COMPUTER PROGRAMMING I",
                schedule_desc: "Mon 7:00AM - 10:00AM",
                detected_type: "lecture_lab",
                ceit_metadata: {
                    prefix: "DCIT",
                    department_code: "DIT",
                    department_name: "Department of Information Technology"
                }
            }];
            state.rosterReports = [{
                filename: "CS1-4 DCIT21.xlsx",
                status: "warning",
                issue: "incomplete_filename",
                student_count: 1,
                column_count: 2,
                course_sec: "BSCS 1-4",
                schedule_code: "",
                subject_name: "DCIT 21",
                can_link: True,
                recommended_filename: "BSCS1-4 List of Students for 202612040-DCIT 21 - COMPUTER PROGRAMMING I.xlsx",
                suggested_matches: [{
                    schedule_code: "202612040",
                    course_sec: "BSCS 1-4",
                    subject_name: "DCIT 21 - COMPUTER PROGRAMMING I",
                    score: 7
                }],
                ceit_metadata: {
                    prefix: "DCIT",
                    department_code: "DIT",
                    department_name: "Department of Information Technology"
                }
            }];
            renderRosterStatus();
            renderClassesSection();
        }
        """.replace("True", "true")
        page.evaluate(mock_js)

        # 1. Verify warning badge for incomplete filename
        status_badge = page.locator(".roster-row .badge-warning")
        assert status_badge.is_visible()
        assert "Incomplete Details" in status_badge.inner_text()

        # 2. Verify quick match button
        btn_match = page.locator(".btn-use-match")
        assert btn_match.is_visible()
        assert "Match: BSCS 1-4" in btn_match.inner_text()

        # 3. Verify naming recommendation notice underneath roster row
        rec_notice = page.locator(".roster-item-recommendation")
        assert rec_notice.is_visible()
        assert "BSCS1-4 List of Students for 202612040-DCIT 21 - COMPUTER PROGRAMMING I.xlsx" in rec_notice.inner_text()
        btn_copy_inline = rec_notice.locator(".btn-copy-rec-sm")
        assert btn_copy_inline.is_visible()
        assert "Copy Name" in btn_copy_inline.inner_text()

        # 4. Open ⚙️ Map modal
        page.click(".btn-map-columns")
        modal = page.locator("#modalRosterMappingBackdrop")
        page.wait_for_timeout(200)
        assert modal.is_visible()

        # 5. Check official recommendation banner in modal
        modal_rec_banner = page.locator("#mapNamingRecommendationBanner")
        assert modal_rec_banner.is_visible()
        assert "Recommended Best Practice" in modal_rec_banner.inner_text()
        modal_rec_code = page.locator("#mapModalRecommendedFilename")
        assert "BSCS1-4 List of Students for 202612040-DCIT 21 - COMPUTER PROGRAMMING I.xlsx" in modal_rec_code.inner_text()

        btn_copy_modal = page.locator("#btnCopyRecommendedFilename")
        assert btn_copy_modal.is_visible()

        # 6. Check manual metadata input fields
        in_sec = page.locator("#mapInputCourseSec")
        in_code = page.locator("#mapInputScheduleCode")
        in_subj = page.locator("#mapInputSubjectName")
        assert in_sec.is_visible()
        assert in_code.is_visible()
        assert in_subj.is_visible()

        # Verify pre-populated values from hints
        assert in_sec.input_value() == "BSCS 1-4"
        assert in_subj.input_value() == "DCIT 21"

        # 7. Select Timetable Class link from dropdown
        page.select_option("#mapSelectClassLink", "202612040")
        page.wait_for_timeout(100)
        assert in_code.input_value() == "202612040"
        assert "COMPUTER PROGRAMMING" in in_subj.input_value()

        # 8. Apply mapping
        page.click("button:has-text('Apply & Save')")
        page.wait_for_timeout(200)
        assert modal.is_hidden()

        browser.close()

if __name__ == "__main__":
    pytest.main(["-s", __file__])
