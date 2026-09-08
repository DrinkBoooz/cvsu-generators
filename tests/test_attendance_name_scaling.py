import os
import unittest
import zipfile
from lxml import etree
import attendancegen

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

class AttendanceNameScalingTests(unittest.TestCase):
    def test_auto_scale_attendance_name_thresholds(self):
        # Short name (<= 24 chars) - no scaling applied
        r1 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r1, "ACBANG, JOHN LESTER A.")
        self.assertIsNone(r1.find(f"{{{W}}}rPr"))

        # Medium name (25-28 chars) - scaled to 7pt (sz=14)
        r2 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r2, "ALCANTARA, CHRISTINE ANNE C.")
        sz2 = r2.find(f".//{{{W}}}sz")
        self.assertIsNotNone(sz2)
        self.assertEqual(sz2.attrib.get(f"{{{W}}}val"), "14")

        # Long name (29-33 chars) like DE RUEDA - scaled to 6.5pt (sz=13)
        r3 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r3, "DE RUEDA, ALELHY ALLESSANDRA M.")
        sz3 = r3.find(f".//{{{W}}}sz")
        self.assertIsNotNone(sz3)
        self.assertEqual(sz3.attrib.get(f"{{{W}}}val"), "13")

        # Extra long name (34-37 chars) - scaled to 5.5pt (sz=11)
        r4 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r4, "CRISOSTOMO, NEIL ANGELO MARQUEZ JR.")
        sz4 = r4.find(f".//{{{W}}}sz")
        self.assertIsNotNone(sz4)
        self.assertEqual(sz4.attrib.get(f"{{{W}}}val"), "11")

        # Very long name (>= 38 chars) - scaled to 5pt (sz=10)
        r5 = etree.Element(f"{{{W}}}r")
        attendancegen._auto_scale_attendance_name(r5, "DE LOS REYES, MA. CONCEPCION DELA CRUZ")
        sz5 = r5.find(f".//{{{W}}}sz")
        self.assertIsNotNone(sz5)
        self.assertEqual(sz5.attrib.get(f"{{{W}}}val"), "10")

if __name__ == "__main__":
    unittest.main()
