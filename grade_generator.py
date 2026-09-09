"""
CvSU Grading Sheet Generator Facade
Re-exports GradeGenerator from modules.generators.grade_gen for 100% backward compatibility.
"""

from modules.generators.grade_gen import GradeGenerator

__all__ = ["GradeGenerator"]
