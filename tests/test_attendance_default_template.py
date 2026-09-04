import os
import unittest

import attendancegen


class AttendanceTemplatePathTests(unittest.TestCase):
    def test_uses_bundled_attendance_template_when_repo_root_template_is_missing(self):
        expected_lec = os.path.join(
            os.path.dirname(os.path.abspath(attendancegen.__file__)),
            "attendance",
            "template lec.docx",
        )
        self.assertEqual(attendancegen.get_default_template_path(has_lab=False), expected_lec)
        
        expected_lab = os.path.join(
            os.path.dirname(os.path.abspath(attendancegen.__file__)),
            "attendance",
            "template lab and lec.docx",
        )
        self.assertEqual(attendancegen.get_default_template_path(has_lab=True), expected_lab)

if __name__ == "__main__":
    unittest.main()
