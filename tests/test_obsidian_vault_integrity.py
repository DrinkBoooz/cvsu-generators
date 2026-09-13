import os
import re
import pytest

VAULT_DIR = r"c:\Users\danjo\Desktop\cvsu-generator_documentation"
REQUIRED_DIRS = [
    "00 - Index",
    "01 - Architecture",
    "02 - Generators",
    "03 - Templates",
    "04 - User Guides",
    "05 - Releases & Changelog",
    "06 - Development",
]

def get_all_notes(vault_dir):
    notes = {}
    for root, dirs, files in os.walk(vault_dir):
        if ".obsidian" in root:
            continue
        for file in files:
            if file.endswith(".md"):
                rel_path = os.path.relpath(os.path.join(root, file), vault_dir)
                note_name = os.path.splitext(file)[0]
                notes[note_name] = {
                    "rel_path": rel_path,
                    "full_path": os.path.join(root, file),
                    "filename": file
                }
    return notes

@pytest.mark.skipif(not os.path.isdir(VAULT_DIR), reason="Obsidian vault directory not found")
def test_obsidian_vault_structure_exists():
    """Verify that the Obsidian documentation vault and all standard directories exist."""
    assert os.path.isdir(VAULT_DIR), f"Vault path {VAULT_DIR} must exist"
    for d in REQUIRED_DIRS:
        folder_path = os.path.join(VAULT_DIR, d)
        assert os.path.isdir(folder_path), f"Required folder '{d}' must exist in vault"

@pytest.mark.skipif(not os.path.isdir(VAULT_DIR), reason="Obsidian vault directory not found")
def test_obsidian_vault_frontmatter_integrity():
    """Verify that all markdown notes contain valid YAML frontmatter and required metadata keys."""
    notes = get_all_notes(VAULT_DIR)
    assert len(notes) >= 7, "Vault must contain initial core documentation notes"

    frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

    for note_name, meta in notes.items():
        with open(meta["full_path"], "r", encoding="utf-8") as f:
            content = f.read()

        match = frontmatter_pattern.match(content)
        assert match, f"Note '{meta['rel_path']}' must begin with valid YAML frontmatter ('---')"
        fm_text = match.group(1)

        assert "title:" in fm_text, f"Note '{meta['rel_path']}' frontmatter missing 'title:'"
        assert "status:" in fm_text, f"Note '{meta['rel_path']}' frontmatter missing 'status:'"
        assert "last_modified:" in fm_text, f"Note '{meta['rel_path']}' frontmatter missing 'last_modified:'"

        # Verify status is one of valid values
        status_match = re.search(r"status:\s*([a-zA-Z]+)", fm_text)
        assert status_match, f"Note '{meta['rel_path']}' has invalid status"
        status = status_match.group(1).lower()
        assert status in {"active", "draft", "deprecated", "archived"}, (
            f"Note '{meta['rel_path']}' has unrecognized status: '{status}'"
        )

@pytest.mark.skipif(not os.path.isdir(VAULT_DIR), reason="Obsidian vault directory not found")
def test_obsidian_vault_wikilink_resolution():
    """Verify that every [[wikilink]] in the vault resolves to an actual note file with zero broken links."""
    notes = get_all_notes(VAULT_DIR)
    known_note_names = set(notes.keys())

    # Regex matches [[Target Note]] or [[Target Note|Display Text]] or escaped pipe \|
    wikilink_pattern = re.compile(r"\[\[([^\]|#\\]+)(?:(?:\\\||[|#])[^\]]*)?\]\]")

    broken_links = []

    for note_name, meta in notes.items():
        with open(meta["full_path"], "r", encoding="utf-8") as f:
            content = f.read()

        # Strip code blocks and inline code to prevent false positives in documentation examples
        clean_content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        clean_content = re.sub(r"`[^`\n]+`", "", clean_content)

        links = wikilink_pattern.findall(clean_content)
        for link in links:
            target = link.strip()
            # If target has a path like "01 - Architecture/System Architecture", check basename
            target_base = os.path.splitext(os.path.basename(target))[0]
            if target not in known_note_names and target_base not in known_note_names:
                broken_links.append((meta["rel_path"], target))

    assert not broken_links, f"Found {len(broken_links)} broken wikilink(s) in Obsidian vault: {broken_links}"

@pytest.mark.skipif(not os.path.isdir(VAULT_DIR), reason="Obsidian vault directory not found")
def test_obsidian_moc_exists_and_links_all_categories():
    """Verify that the primary Map of Content (MOC) exists and references key sections."""
    moc_path = os.path.join(VAULT_DIR, "00 - Index", "CvSU Document Generator MOC.md")
    assert os.path.isfile(moc_path), "CvSU Document Generator MOC.md must exist in 00 - Index"

    with open(moc_path, "r", encoding="utf-8") as f:
        moc_content = f.read()

    expected_links = [
        "System Architecture",
        "Generators Overview",
        "Template Guidelines",
        "User Manual",
        "v1.0.1",
        "Development Workflow",
    ]
    for expected in expected_links:
        assert f"[[{expected}]]" in moc_content or f"[[{expected}|" in moc_content, (
            f"MOC must link to [[{expected}]]"
        )
