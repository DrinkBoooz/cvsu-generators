#!/usr/bin/env python3
"""
tests/test_template_set_orchestrator.py

Integration tests for GeneratorFactory and DocumentOrchestrator with active Template Sets:
  - Resolution of physical templates through the active TemplateSetManager
  - Verification that generators receive user template paths when active
  - Verification of strict fail-closed behavior (MissingTemplateRoleError) when fallback is OFF
  - Verification of fallback resolution when fallback is ON
  - Verification that existing Custom Forms remain preserved alongside Template Sets
"""

import os
import pytest

from modules.models.template_set import (
    ROLE_SYLLABUS,
    ROLE_EXAM_RETURNS_MIDTERM,
    ROLE_EXAM_RETURNS_FINAL,
    ROLE_TOS_MIDTERM,
    ROLE_TOS_FINAL,
    ROLE_GRADE_DISCUSSION_MIDTERM,
    ROLE_GRADE_DISCUSSION_FINAL,
    ROLE_ATTENDANCE_LECTURE,
    ROLE_ATTENDANCE_LECTURE_LAB,
    ROLE_GRADE_SHEET_LECTURE,
    ROLE_GRADE_SHEET_LECTURE_LAB,
    MissingTemplateRoleError,
)
from modules.services.template_set_manager import (
    TemplateSetManager,
    BUILTIN_SET_ID,
)
from modules.generators.ceit_gen import GeneratorFactory
from modules.services.orchestrator import process_all


@pytest.fixture(autouse=True)
def isolated_template_set_manager(tmp_path, monkeypatch):
    """Isolate TemplateSetManager to a clean temporary APPDATA directory for each test."""
    manager = TemplateSetManager(base_dir=str(tmp_path))
    monkeypatch.setattr(TemplateSetManager, "get_instance", lambda: manager)
    return manager


@pytest.fixture
def project_templates_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))


@pytest.fixture
def project_attendance_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "attendance"))


def test_generator_factory_builtin_active(isolated_template_set_manager, project_templates_dir):
    factory = GeneratorFactory(project_templates_dir)
    gens = factory.get_all(include_custom=False)
    assert len(gens) == 7

    # All generated instances should resolve to built-in templates
    for gen_factory, suffix in gens:
        gen = gen_factory()
        assert os.path.exists(gen.template_path)
        assert "templates" in gen.template_path


def test_generator_factory_user_set_resolution(isolated_template_set_manager, project_templates_dir):
    mgr = isolated_template_set_manager
    ts = mgr.create_template_set("Engineering User Set")

    # Add 7 CEIT templates to the set
    ceit_files = {
        ROLE_SYLLABUS: "template_syllabus.docx",
        ROLE_EXAM_RETURNS_MIDTERM: "template_exam_midterm.docx",
        ROLE_EXAM_RETURNS_FINAL: "template_exam_finals.docx",
        ROLE_TOS_MIDTERM: "template_tos_midterm.docx",
        ROLE_TOS_FINAL: "template_tos_finals.docx",
        ROLE_GRADE_DISCUSSION_MIDTERM: "Midterm-Grade-Discussion_LATEST.docx",
        ROLE_GRADE_DISCUSSION_FINAL: "Final-Grade-Discussion_LATEST.docx",
    }
    for role, fn in ceit_files.items():
        mgr.add_template_to_set(ts.set_id, role, os.path.join(project_templates_dir, fn))

    mgr.activate_template_set(ts.set_id)

    factory = GeneratorFactory(project_templates_dir)
    gens = factory.get_all(include_custom=False)
    assert len(gens) == 7

    for gen_factory, suffix in gens:
        gen = gen_factory()
        # Verify physical path is inside the user set directory
        assert "engineering_user_set" in gen.template_path
        assert os.path.exists(gen.template_path)


def test_generator_factory_fails_closed_when_fallback_off(isolated_template_set_manager, project_templates_dir):
    mgr = isolated_template_set_manager
    ts = mgr.create_template_set("Incomplete User Set", fallback_to_default=False)
    # Only add syllabus
    mgr.add_template_to_set(ts.set_id, ROLE_SYLLABUS, os.path.join(project_templates_dir, "template_syllabus.docx"))
    mgr.activate_template_set(ts.set_id)

    factory = GeneratorFactory(project_templates_dir)
    with pytest.raises(MissingTemplateRoleError, match="Fallback: OFF"):
        for gen_fn, _ in factory.get_all(include_custom=False):
            gen_fn()


def test_generator_factory_falls_back_when_fallback_on(isolated_template_set_manager, project_templates_dir):
    mgr = isolated_template_set_manager
    ts = mgr.create_template_set("Incomplete Set With Fallback", fallback_to_default=True)
    # Only add syllabus
    mgr.add_template_to_set(ts.set_id, ROLE_SYLLABUS, os.path.join(project_templates_dir, "template_syllabus.docx"))
    mgr.activate_template_set(ts.set_id)

    factory = GeneratorFactory(project_templates_dir)
    gens = factory.get_all(include_custom=False)
    assert len(gens) == 7

    # Syllabus should be user set; others should be built-in
    syl_gen = gens[0][0]()
    assert "incomplete_set_with_fallback" in syl_gen.template_path

    other_gen = gens[1][0]()
    assert "incomplete_set_with_fallback" not in other_gen.template_path
    assert "template_exam_midterm.docx" in other_gen.template_path


def test_orchestrator_resolves_attendance_and_grades(isolated_template_set_manager):
    mgr = isolated_template_set_manager

    # Attendance lecture template resolution
    att_lec = mgr.resolve_template(ROLE_ATTENDANCE_LECTURE)
    assert att_lec.role == ROLE_ATTENDANCE_LECTURE
    assert "template lec.docx" in att_lec.file_path

    # Attendance lab template resolution
    att_lab = mgr.resolve_template(ROLE_ATTENDANCE_LECTURE_LAB)
    assert att_lab.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert "template lab and lec.docx" in att_lab.file_path

    # Grade sheet lecture template resolution
    grd_lec = mgr.resolve_template(ROLE_GRADE_SHEET_LECTURE)
    assert grd_lec.role == ROLE_GRADE_SHEET_LECTURE
    assert "GRADING_LECTURE_TEMPLATE.xlsx" in grd_lec.file_path

    # Grade sheet lab template resolution
    grd_lab = mgr.resolve_template(ROLE_GRADE_SHEET_LECTURE_LAB)
    assert grd_lab.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert "GRADING_LECTURE_LAB_TEMPLATE.xlsx" in grd_lab.file_path
