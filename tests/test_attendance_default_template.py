import os
import unittest

import attendancegen


class AttendanceTemplatePathTests(unittest.TestCase):
    def test_uses_bundled_attendance_template_when_repo_root_template_is_missing(self):
        expected = os.path.join(
            os.path.dirname(os.path.abspath(attendancegen.__file__)),
            "attendance",
            "template.docx",
        )
        self.assertEqual(attendancegen.get_default_template_path(), expected)


if __name__ == "__main__":
    unittest.main()
