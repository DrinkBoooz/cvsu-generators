#!/usr/bin/env python3
"""
tests/test_template_set_manager.py

Unit and integration tests for TemplateSetManager:
  - CRUD operations (create, update, delete, duplicate)
  - Built-in default set read-only protection
  - Active set switching and automatic revert on deletion
  - Adding and removing templates with authoritative validation
  - Resolution mechanics: fail-closed with MissingTemplateRoleError when fallback is OFF,
    and safe fallback to built-in when fallback is ON
  - Export and import of .cvstemplateset.zip portable packages
  - Security checks (path traversal rejection, zip slip prevention)
"""

import json
import os
import shutil
import zipfile
import pytest

from modules.models.template_set import (
    CANONICAL_ROLES,
    ROLE_SYLLABUS,
    ROLE_ATTENDANCE_LECTURE,
    ROLE_GRADE_SHEET_LECTURE,
    TemplateSetError,
    InvalidTemplateSetError,
    MissingTemplateRoleError,
)
from modules.services.template_set_manager import (
    TemplateSetManager,
    BUILTIN_SET_ID,
)


@pytest.fixture
def manager(tmp_path):
    # Isolated manager instance pointing to temp directory
    return TemplateSetManager(base_dir=str(tmp_path))


@pytest.fixture
def project_templates_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))


def test_builtin_set_properties_and_immutability(manager):
    builtin = manager.get_builtin_set()
    assert builtin.set_id == BUILTIN_SET_ID
    assert builtin.source == "builtin"
    assert builtin.is_builtin is True
    assert builtin.is_complete() is True

    # Built-in is strictly read-only: modifications must be rejected
    with pytest.raises(TemplateSetError, match="Cannot delete read-only"):
        manager.delete_template_set(BUILTIN_SET_ID)

    with pytest.raises(TemplateSetError, match="Cannot modify read-only"):
        manager.update_template_set(BUILTIN_SET_ID, display_name="Modified")

    with pytest.raises(TemplateSetError, match="Cannot add templates to the built-in"):
        manager.add_template_to_set(BUILTIN_SET_ID, ROLE_SYLLABUS, "dummy.docx")

    with pytest.raises(TemplateSetError, match="Cannot remove templates from built-in"):
        manager.remove_template_from_set(BUILTIN_SET_ID, ROLE_SYLLABUS)

    with pytest.raises(InvalidTemplateSetError, match="reserved ID"):
        manager.create_template_set("New Builtin", set_id=BUILTIN_SET_ID)


def test_user_set_crud_and_atomic_manifest(manager):
    # 1. Create
    ts = manager.create_template_set("College of Engineering", description="COE 2026")
    assert ts.set_id == "college_of_engineering"
    assert ts.display_name == "College of Engineering"
    assert ts.source == "user"
    assert ts.is_active is False
    assert ts.fallback_to_default is False

    # Verify manifest on disk
    manifest_path = os.path.join(manager.template_sets_dir, ts.set_id, "manifest.json")
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["display_name"] == "College of Engineering"

    # 2. List
    sets = manager.list_template_sets()
    assert len(sets) == 2
    assert sets[0].set_id == BUILTIN_SET_ID
    assert sets[1].set_id == "college_of_engineering"

    # 3. Update
    updated = manager.update_template_set(
        "college_of_engineering",
        display_name="COE Department",
        description="Updated description",
        fallback_to_default=True,
    )
    assert updated.display_name == "COE Department"
    assert updated.fallback_to_default is True

    # 4. Duplicate
    dup = manager.duplicate_template_set("college_of_engineering", "COE Copy")
    assert dup.set_id.startswith("coe_copy")
    assert dup.display_name == "COE Copy"

    # 5. Delete
    res = manager.delete_template_set("college_of_engineering")
    assert res is True
    assert manager.get_template_set("college_of_engineering") is None


def test_activation_and_automatic_revert(manager):
    ts = manager.create_template_set("College of Science")
    assert manager.get_active_template_set_id() == BUILTIN_SET_ID

    # Activate user set
    manager.activate_template_set(ts.set_id)
    assert manager.get_active_template_set_id() == ts.set_id
    active_ts = manager.get_active_template_set()
    assert active_ts.set_id == ts.set_id
    assert active_ts.is_active is True

    # Delete active set -> must automatically revert to built-in set
    manager.delete_template_set(ts.set_id)
    assert manager.get_active_template_set_id() == BUILTIN_SET_ID
    assert manager.get_active_template_set().set_id == BUILTIN_SET_ID


def test_add_and_remove_template_to_user_set(manager, project_templates_dir):
    ts = manager.create_template_set("Custom Set")
    syl_path = os.path.join(project_templates_dir, "template_syllabus.docx")

    # Adding valid template validates and copies file
    updated_ts = manager.add_template_to_set(
        ts.set_id,
        ROLE_SYLLABUS,
        syl_path,
        display_metadata={"notes": "COE syllabus"},
    )
    assert ROLE_SYLLABUS in updated_ts.templates
    entry = updated_ts.templates[ROLE_SYLLABUS]
    assert os.path.exists(entry.file_path)
    assert entry.profile_id == "syllabus"
    assert entry.display_metadata["notes"] == "COE syllabus"

    # Adding invalid file or wrong role fails closed
    with pytest.raises(InvalidTemplateSetError):
        manager.add_template_to_set(ts.set_id, ROLE_GRADE_SHEET_LECTURE, syl_path)

    # Remove template
    removed_ts = manager.remove_template_from_set(ts.set_id, ROLE_SYLLABUS)
    assert ROLE_SYLLABUS not in removed_ts.templates
    assert not os.path.exists(entry.file_path)


def test_resolution_no_silent_fallback_when_off(manager, project_templates_dir):
    """
    When fallback_to_default is OFF (default), missing roles in the active set
    MUST raise MissingTemplateRoleError and never silently use CvSU defaults.
    """
    ts = manager.create_template_set("Incomplete Set", fallback_to_default=False)
    syl_path = os.path.join(project_templates_dir, "template_syllabus.docx")
    manager.add_template_to_set(ts.set_id, ROLE_SYLLABUS, syl_path)
    manager.activate_template_set(ts.set_id)

    # Syllabus exists -> resolves user template
    resolved_syl = manager.resolve_template(ROLE_SYLLABUS)
    assert resolved_syl.role == ROLE_SYLLABUS
    assert "incomplete_set" in resolved_syl.file_path

    # Attendance lecture is MISSING -> fails closed with MissingTemplateRoleError
    with pytest.raises(MissingTemplateRoleError, match="Fallback: OFF"):
        manager.resolve_template(ROLE_ATTENDANCE_LECTURE)


def test_resolution_safe_fallback_when_explicitly_enabled(manager, project_templates_dir):
    """
    When the user explicitly enables fallback_to_default = True,
    missing roles fall back to the built-in CvSU template.
    """
    ts = manager.create_template_set("Fallback Set", fallback_to_default=True)
    syl_path = os.path.join(project_templates_dir, "template_syllabus.docx")
    manager.add_template_to_set(ts.set_id, ROLE_SYLLABUS, syl_path)
    manager.activate_template_set(ts.set_id)

    # Provided role -> returns user template
    resolved_syl = manager.resolve_template(ROLE_SYLLABUS)
    assert "fallback_set" in resolved_syl.file_path

    # Missing role -> safely resolves built-in template
    resolved_att = manager.resolve_template(ROLE_ATTENDANCE_LECTURE)
    assert resolved_att.role == ROLE_ATTENDANCE_LECTURE
    assert "template lec.docx" in resolved_att.file_path


def test_export_and_import_portable_package(manager, project_templates_dir, tmp_path):
    # 1. Create a set with a syllabus template
    ts = manager.create_template_set("Exportable Set", description="Test portable export")
    syl_path = os.path.join(project_templates_dir, "template_syllabus.docx")
    manager.add_template_to_set(ts.set_id, ROLE_SYLLABUS, syl_path)

    # 2. Export package
    zip_dest = str(tmp_path / "test_package.cvstemplateset.zip")
    exported_path = manager.export_template_set(ts.set_id, zip_dest)
    assert os.path.exists(exported_path)

    # Verify contents of zip
    with zipfile.ZipFile(exported_path, "r") as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert any(n.startswith("templates/syllabus_") for n in names)
        # Ensure no coordinates in zip manifest
        manifest_text = zf.read("manifest.json").decode("utf-8")
        assert "row_index" not in manifest_text
        assert "col_index" not in manifest_text

    # 3. Import package in a fresh manager instance
    manager2 = TemplateSetManager(base_dir=str(tmp_path / "fresh_appdata"))
    imported_ts = manager2.import_template_set(exported_path)
    assert imported_ts.display_name == "Exportable Set"
    assert ROLE_SYLLABUS in imported_ts.templates

    # Verify physical file in imported set exists and is validated
    imp_entry = imported_ts.templates[ROLE_SYLLABUS]
    assert os.path.exists(imp_entry.file_path)
    assert imp_entry.profile_id == "syllabus"


def test_security_rejections(manager, tmp_path):
    # 1. Path traversal in set_id
    with pytest.raises(InvalidTemplateSetError):
        manager.create_template_set("Bad", set_id="../../evil")

    # 2. Path traversal in zip import (zip slip protection)
    slip_zip = tmp_path / "slip.zip"
    with zipfile.ZipFile(slip_zip, "w") as zf:
        zf.writestr("../../evil.txt", "evil")
        zf.writestr("manifest.json", json.dumps({"set_id": "slip_set"}))

    with pytest.raises(InvalidTemplateSetError, match="Path traversal detected"):
        manager.import_template_set(str(slip_zip))
