#!/usr/bin/env python3
"""
tests/test_template_set_model.py

Unit tests for the TemplateSet and TemplateEntry domain models:
  - Canonical roles and profiles
  - Serialization / deserialization (manifests)
  - Exclusion of structural coordinates
  - Path traversal and set_id security validations
  - Status and completeness reporting
"""

import os
import pytest

from modules.models.template_set import (
    CANONICAL_ROLES,
    ROLE_SYLLABUS,
    ROLE_ATTENDANCE_LECTURE,
    ROLE_GRADE_SHEET_LECTURE,
    TemplateEntry,
    TemplateSet,
    InvalidTemplateSetError,
    MissingTemplateRoleError,
)


def test_canonical_roles_integrity():
    assert len(CANONICAL_ROLES) == 11
    assert ROLE_SYLLABUS in CANONICAL_ROLES
    assert ROLE_ATTENDANCE_LECTURE in CANONICAL_ROLES
    assert ROLE_GRADE_SHEET_LECTURE in CANONICAL_ROLES


def test_template_entry_creation_and_dict(tmp_path):
    fpath = tmp_path / "test_syllabus.docx"
    fpath.write_text("dummy")

    entry = TemplateEntry(
        role=ROLE_SYLLABUS,
        file_path=str(fpath),
        file_type="docx",
        profile_id="syllabus",
        display_metadata={"title": "Custom Syllabus"},
    )
    d = entry.to_dict(relative_to=str(tmp_path))
    assert d["role"] == ROLE_SYLLABUS
    assert d["file_path"] == "test_syllabus.docx"
    assert d["file_type"] == "docx"
    assert d["profile_id"] == "syllabus"
    assert d["display_metadata"]["title"] == "Custom Syllabus"

    # Coordinates MUST NEVER exist in entry dict
    for forbidden in ("row", "col", "coordinate", "table_index", "cell", "geometry"):
        assert forbidden not in d


def test_template_entry_path_traversal_rejection():
    bad_data = {
        "role": ROLE_SYLLABUS,
        "file_path": "../../../etc/passwd",
        "file_type": "docx",
        "profile_id": "syllabus",
    }
    with pytest.raises(InvalidTemplateSetError, match="Path traversal detected"):
        TemplateEntry.from_dict(bad_data)


def test_template_entry_invalid_role():
    bad_data = {
        "role": "non_existent_role",
        "file_path": "templates/file.docx",
        "file_type": "docx",
        "profile_id": "syllabus",
    }
    with pytest.raises(InvalidTemplateSetError, match="Invalid or unrecognized template role"):
        TemplateEntry.from_dict(bad_data)


def test_template_set_id_validation():
    # Valid set IDs
    ts1 = TemplateSet(set_id="engineering_college", display_name="Engineering")
    assert ts1.set_id == "engineering_college"
    ts2 = TemplateSet(set_id="dept-cs-2026", display_name="CS Dept")
    assert ts2.set_id == "dept-cs-2026"

    # Invalid set IDs: path traversal or special chars
    with pytest.raises(InvalidTemplateSetError):
        TemplateSet(set_id="../bad_dir", display_name="Bad")

    with pytest.raises(InvalidTemplateSetError):
        TemplateSet(set_id="bad/dir", display_name="Bad")

    with pytest.raises(InvalidTemplateSetError):
        TemplateSet(set_id="", display_name="Bad")


def test_template_set_status_and_completeness(tmp_path):
    files = {}
    for role in CANONICAL_ROLES:
        p = tmp_path / f"{role}.docx"
        p.write_text("content")
        files[role] = str(p)

    ts = TemplateSet(
        set_id="complete_set",
        display_name="Complete College Set",
    )
    assert not ts.is_complete()
    assert ts.status() == "Incomplete"
    assert len(ts.missing_roles()) == 11

    # Add 10 templates (still incomplete)
    for role in CANONICAL_ROLES[:-1]:
        ftype = "xlsx" if "sheet" in role else "docx"
        ts.templates[role] = TemplateEntry(
            role=role,
            file_path=files[role],
            file_type=ftype,
            profile_id="test",
        )

    assert not ts.is_complete()
    assert ts.status() == "Incomplete"
    assert ts.missing_roles() == [CANONICAL_ROLES[-1]]

    # Add 11th template (now complete)
    last_role = CANONICAL_ROLES[-1]
    ftype = "xlsx" if "sheet" in last_role else "docx"
    ts.templates[last_role] = TemplateEntry(
        role=last_role,
        file_path=files[last_role],
        file_type=ftype,
        profile_id="test",
    )

    assert ts.is_complete()
    assert ts.status() == "Complete"
    assert ts.missing_roles() == []

    # If physical file is missing -> status is "Invalid"
    os.remove(files[last_role])
    assert ts.status() == "Invalid"


def test_template_set_manifest_serialization_no_coordinates(tmp_path):
    p = tmp_path / "syllabus.docx"
    p.write_text("test")

    ts = TemplateSet(
        set_id="manifest_test",
        display_name="Manifest Test",
        templates={
            ROLE_SYLLABUS: TemplateEntry(
                role=ROLE_SYLLABUS,
                file_path=str(p),
                file_type="docx",
                profile_id="syllabus",
            )
        },
    )

    serialized = ts.to_dict(base_dir=str(tmp_path))
    assert serialized["set_id"] == "manifest_test"
    assert ROLE_SYLLABUS in serialized["templates"]

    # Reconstruct from dict
    restored = TemplateSet.from_dict(serialized, base_dir=str(tmp_path))
    assert restored.set_id == "manifest_test"
    assert restored.templates[ROLE_SYLLABUS].file_path == os.path.normpath(str(p))

    # Verify no coordinates anywhere in manifest dict
    manifest_str = str(serialized).lower()
    for forbidden in ("coordinate", "row_index", "col_index", "table_index", "header_row"):
        assert forbidden not in manifest_str
