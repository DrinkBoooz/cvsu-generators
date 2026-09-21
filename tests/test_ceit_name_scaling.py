import os
import unittest
import zipfile
import tempfile
from lxml import etree

from modules.models.schedule import ClassInfo
from modules.generators.ceit_gen import SyllabusGenerator, ExamReturnsGenerator, TOSGenerator
from modules.services.template_recipe_service import recipe_resolver

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class CEITNameScalingTests(unittest.TestCase):
    def test_ceit_student_name_font_scaling(self):
        test_names = [
            ("ACBANG, JOHN LESTER A.", "16"),  # 22 chars -> <= 30 chars -> 8pt (sz=16)
            ("ALCANTARA, CHRISTINE ANNE C.", "16"),  # 28 chars -> <= 30 chars -> 8pt (sz=16)
            ("DE RUEDA, ALELHY ALLESSANDRA M.", "14"),  # 31 chars -> 31-35 chars -> 7pt (sz=14)
            ("CRISOSTOMO, NEIL ANGELO MARQUEZ JR.", "14"),  # 35 chars -> 31-35 chars -> 7pt (sz=14)
            ("DE LOS REYES, MA. CONCEPCION DELA CRUZ", "12"),  # 39 chars -> > 35 chars -> 6pt (sz=12)
        ]

        students = [(name, f"20201234{i}") for i, (name, _) in enumerate(test_names)]
        info = ClassInfo(
            instructor="DAN JOSEPH A. ORTEGA",
            course_section="BSCS 4-2",
            schedule_code="202612736",
            subject="COSC 111 - INTERNET OF THINGS",
            students=students,
        )

        template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "templates",
            "template_syllabus.docx",
        )
        self.assertTrue(os.path.exists(template_path), f"Template not found: {template_path}")

        recipe = recipe_resolver.resolve(template_path)
        gen = SyllabusGenerator(template_path, recipe)

        with tempfile.TemporaryDirectory() as td:
            out_docx = os.path.join(td, "test_syllabus_out.docx")
            gen.generate(info, out_docx)

            with zipfile.ZipFile(out_docx) as z:
                tree = etree.fromstring(z.read("word/document.xml"))
                for name, exp_sz in test_names:
                    found = False
                    for t in tree.iter(f"{{{W}}}t"):
                        if name in (t.text or ""):
                            r_node = t.getparent()
                            sz_el = r_node.find(f".//{{{W}}}sz")
                            actual_sz = sz_el.attrib.get(f"{{{W}}}val") if sz_el is not None else "16"

                            self.assertEqual(
                                actual_sz,
                                exp_sz,
                                f"Expected sz='{exp_sz}' for '{name}', got '{actual_sz}'",
                            )
                            self.assertNotEqual(
                                actual_sz,
                                "18",
                                f"Name '{name}' must not be blown up to sz='18'",
                            )
                            found = True
                            break
                    self.assertTrue(found, f"Student '{name}' not found in generated syllabus docx")


if __name__ == "__main__":
    unittest.main()
