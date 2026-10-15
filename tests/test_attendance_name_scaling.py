import os
import unittest
import zipfile
from lxml import etree
import attendancegen

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

class AttendanceNameScalingTests(unittest.TestCase):
    def test_auto_scale_attendance_name_thresholds(self):
        # Name <= 24 chars -> keeps template default (8pt Arial bold)
        r1 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r1, "ACBANG, JOHN LESTER A.")  # 22 chars
        sz1 = r1.find(f".//{{{W}}}sz")
        self.assertIsNone(sz1)

        # Name 25-28 chars -> 7pt (sz="14")
        r2 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r2, "ALCANTARA, CHRISTINE ANNE C.")  # 28 chars
        sz2 = r2.find(f".//{{{W}}}sz")
        self.assertIsNotNone(sz2)
        self.assertEqual(sz2.attrib.get(f"{{{W}}}val"), "14")

        # Name 29-33 chars -> 6.5pt (sz="13")
        r3 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r3, "DE RUEDA, ALELHY ALLESSANDRA M.")  # 31 chars
        sz3 = r3.find(f".//{{{W}}}sz")
        self.assertIsNotNone(sz3)
        self.assertEqual(sz3.attrib.get(f"{{{W}}}val"), "13")

        # Name 34-37 chars -> 5.5pt (sz="11")
        r4 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r4, "CRISOSTOMO, NEIL ANGELO MARQUEZ JR.")  # 35 chars
        sz4 = r4.find(f".//{{{W}}}sz")
        self.assertIsNotNone(sz4)
        self.assertEqual(sz4.attrib.get(f"{{{W}}}val"), "11")

        # Name >= 38 chars -> 5pt (sz="10")
        r5 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r5, "DE LOS REYES, MA. CONCEPCION DELA CRUZ")  # 39 chars
        sz5 = r5.find(f".//{{{W}}}sz")
        self.assertIsNotNone(sz5)
        self.assertEqual(sz5.attrib.get(f"{{{W}}}val"), "10")

    def test_generated_attendance_student_name_scaling(self):
        import tempfile
        from modules.generators.attendance_gen import build_attendance_sheet, get_default_template_path

        test_names = [
            ("ACBANG, JOHN LESTER A.", "16", False),  # 22 chars -> template default 8pt
            ("ALCANTARA, CHRISTINE ANNE C.", "14", False),  # 28 chars -> 7pt
            ("DE RUEDA, ALELHY ALLESSANDRA M.", "13", False),  # 31 chars -> 6.5pt
            ("CRISOSTOMO, NEIL ANGELO MARQUEZ JR.", "11", False),  # 35 chars -> 5.5pt (unbold)
            ("DE LOS REYES, MA. CONCEPCION DELA CRUZ", "10", False),  # 39 chars -> 5pt (unbold)
        ]
        students = [(name, f"20201234{i}") for i, (name, _, _) in enumerate(test_names)]

        with tempfile.TemporaryDirectory() as td:
            out_docx = os.path.join(td, "test_attn_out.docx")
            build_attendance_sheet(
                template_path=get_default_template_path(False),
                output_path=out_docx,
                course_code_title="COSC 111 - IOT",
                class_schedule="Mon: 07:00AM-10:00AM",
                semester_ay="1st Semester AY 2026-2027",
                room_assignment="CCL 102",
                instructor="DAN JOSEPH A. ORTEGA",
                months=[9],
                year=2026,
                weekdays=[0],
                students=students,
            )

            with zipfile.ZipFile(out_docx) as z:
                tree = etree.fromstring(z.read("word/document.xml"))
                for name, exp_sz, exp_bold in test_names:
                    found = False
                    for t in tree.iter(f"{{{W}}}t"):
                        if name in (t.text or ""):
                            r_node = t.getparent()
                            sz_el = r_node.find(f".//{{{W}}}sz")
                            actual_sz = sz_el.attrib.get(f"{{{W}}}val") if sz_el is not None else "16"
                            b_el = r_node.find(f".//{{{W}}}b")
                            actual_bold = b_el is not None

                            self.assertEqual(
                                actual_sz,
                                exp_sz,
                                f"Expected sz='{exp_sz}' for '{name}', got '{actual_sz}'",
                            )
                            self.assertNotEqual(
                                actual_sz,
                                "18",
                                f"Name '{name}' should not be enlarged to sz='18'",
                            )
                            self.assertEqual(
                                actual_bold,
                                exp_bold,
                                f"Expected bold={exp_bold} for '{name}', got {actual_bold}",
                            )
                            found = True
                            break
                    self.assertTrue(found, f"Student '{name}' not found in generated attendance docx")

if __name__ == "__main__":
    unittest.main()
