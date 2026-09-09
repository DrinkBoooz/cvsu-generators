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

if __name__ == "__main__":
    unittest.main()
