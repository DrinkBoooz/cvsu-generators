import os
import tempfile
import unittest

import attendancegen
import process_schedule


class AttendanceScheduleParsingTests(unittest.TestCase):
    def test_find_schedule_file_ignores_student_rosters_and_prefers_schedule_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            roster = os.path.join(tmpdir, "BSCS 1-2 List of Students for 202612022-DCIT 21A - INTRODUCTION TO COMPUTING.xlsx")
            schedule = os.path.join(tmpdir, "ROSALES UPDATED.xls")
            with open(roster, "wb") as f:
                f.write(b"student roster")
            with open(schedule, "wb") as f:
                f.write(b"schedule")

            self.assertEqual(process_schedule.find_schedule_file(tmpdir), schedule)

    def test_parse_schedule_days_handles_multiple_days(self):
        self.assertEqual(
            attendancegen.parse_schedule_days("07:00AM-09:00AM, 01:00PM-03:00PM / Thurs, Fri"),
            [3, 4],
        )

    def test_parse_explicit_schedule_meetings_handles_day_slot_pairs(self):
        self.assertEqual(
            attendancegen.build_schedule_meetings(
                "Thu: 07:00AM-09:00AM; Fri: 01:00PM-03:00PM"
            ),
            [(3, "07:00AM-09:00AM"), (4, "01:00PM-03:00PM")],
        )

    def test_parse_schedule_slots_handles_multiple_time_blocks(self):
        self.assertEqual(
            attendancegen.parse_schedule_slots("07:00AM-09:00AM, 01:00PM-03:00PM / Thurs, Fri"),
            ["07:00AM-09:00AM", "01:00PM-03:00PM"],
        )

    def test_build_schedule_label_preserves_explicit_mapping(self):
        self.assertEqual(
            attendancegen.build_schedule_label("Thu: 07:00AM-09:00AM; Fri: 01:00PM-03:00PM"),
            "Thu: 07:00AM-09:00AM; Fri: 01:00PM-03:00PM",
        )

    def test_build_semester_label_uses_previous_year(self):
        self.assertEqual(
            attendancegen.build_semester_label("2nd", 2026),
            "2nd Semester / A.Y. 2025-2026",
        )

    def test_get_class_dates_for_weekdays_collects_all_requested_days(self):
        dates = attendancegen.get_class_dates_for_weekdays([2], 2026, [3, 4])
        self.assertTrue(dates)
        self.assertTrue(all(dt.weekday() in {3, 4} for dt in dates))

    def test_format_time_evening_with_pm_hint(self):
        # 7:00 in morning vs 7:00 in evening
        self.assertEqual(process_schedule.format_time("7:00", is_pm_hint=False), "07:00AM")
        self.assertEqual(process_schedule.format_time("7:00", is_pm_hint=True), "07:00PM")
        # Excel float for 7:00 PM (7/24) with PM hint
        self.assertEqual(process_schedule.format_time("0.2916666666666667", is_pm_hint=True), "07:00PM")
        # Noon is always PM
        self.assertEqual(process_schedule.format_time("12:00", is_pm_hint=False), "12:00PM")

    def test_set_cell_text_removes_hanging_indent_and_justification(self):
        from lxml import etree
        import ceit_generator
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        tc_xml = (
            '<w:tc xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '  <w:p>'
            '    <w:pPr>'
            '      <w:ind w:left="3600" w:hanging="3600"/>'
            '      <w:jc w:val="both"/>'
            '    </w:pPr>'
            '    <w:r><w:t>Old</w:t></w:r>'
            '  </w:p>'
            '</w:tc>'
        )
        tc = etree.fromstring(tc_xml)
        ceit_generator.set_cell_text(tc, "Wed: 09:00AM-11:00AM / LEC: ITC 501; Wed: 05:00PM-07:00PM / LAB: CCL 102")
        ppr = tc.find("w:p/w:pPr", ns)
        self.assertIsNone(ppr.find("w:ind", ns))
        self.assertEqual(ppr.find("w:jc", ns).attrib[f"{{{ns['w']}}}val"], "left")


if __name__ == "__main__":
    unittest.main()