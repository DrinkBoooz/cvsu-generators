import unittest

import attendancegen


class AttendanceScheduleParsingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()