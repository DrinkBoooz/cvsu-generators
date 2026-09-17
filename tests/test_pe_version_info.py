import os
import re
import pytest
from PyInstaller.utils.win32.versioninfo import load_version_info_from_text_file

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXECUTABLE_DIR = os.path.join(WORKSPACE_DIR, "executable_test")
VERSION_INFO_PATH = os.path.join(EXECUTABLE_DIR, "file_version_info.txt")
SPEC_PATH = os.path.join(EXECUTABLE_DIR, "CvSU Gen.spec")
BUILD_BAT_PATH = os.path.join(EXECUTABLE_DIR, "build.bat")
UI_HTML_PATH = os.path.join(EXECUTABLE_DIR, "ui.html")
SIGN_EXE_PATH = os.path.join(EXECUTABLE_DIR, "sign_exe.ps1")
CREATE_CERT_PATH = os.path.join(EXECUTABLE_DIR, "create_code_signing_cert.ps1")
INSTALL_PUBLISHER_PATH = os.path.join(EXECUTABLE_DIR, "install_trusted_publisher.bat")


def get_ui_version():
    """Extract active version from executable_test/ui.html (e.g. '1.0.0' from 'Release v1.0.0')."""
    assert os.path.exists(UI_HTML_PATH), "ui.html must exist"
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'<span class="badge-version">(?:Release\s+)?v?(\d+\.\d+(?:\.\d+)?)(?:\s+Beta)?</span>', content)
    assert match, "Version badge not found in ui.html"
    return match.group(1)


def test_file_version_info_exists_and_loads():
    """Verify that file_version_info.txt exists and can be parsed by PyInstaller."""
    assert os.path.exists(VERSION_INFO_PATH), "file_version_info.txt must exist"
    vi = load_version_info_from_text_file(VERSION_INFO_PATH)
    assert vi is not None, "load_version_info_from_text_file must parse version structure successfully"


def test_version_info_metadata_and_synchronization():
    """Verify that metadata strings and version tuples match project standards."""
    vi = load_version_info_from_text_file(VERSION_INFO_PATH)
    ui_version = get_ui_version()  # e.g. "1.0.0"
    parts = [int(x) for x in ui_version.split(".")]
    if len(parts) == 2:
        major, minor = parts
        patch = 0
    else:
        major, minor, patch = parts[:3]
    expected_tuple = (major, minor, patch, 0)
    expected_str = f"{major}.{minor}.{patch}.0"

    # Verify fixed file info tuples (MS >> 16, MS & 0xffff, LS >> 16, LS & 0xffff)
    actual_filevers = (
        vi.ffi.fileVersionMS >> 16,
        vi.ffi.fileVersionMS & 0xFFFF,
        vi.ffi.fileVersionLS >> 16,
        vi.ffi.fileVersionLS & 0xFFFF,
    )
    actual_prodvers = (
        vi.ffi.productVersionMS >> 16,
        vi.ffi.productVersionMS & 0xFFFF,
        vi.ffi.productVersionLS >> 16,
        vi.ffi.productVersionLS & 0xFFFF,
    )
    assert actual_filevers == expected_tuple, f"filevers must be {expected_tuple}, got {actual_filevers}"
    assert actual_prodvers == expected_tuple, f"prodvers must be {expected_tuple}, got {actual_prodvers}"

    # Extract StringFileInfo entries
    string_table = vi.kids[0].kids[0]
    metadata = {item.name: item.val for item in string_table.kids}

    assert "Dan Joseph Ortega" in metadata.get("CompanyName", ""), "CompanyName must contain Dan Joseph Ortega"
    assert "Dan Joseph Ortega" in metadata.get("LegalCopyright", ""), "LegalCopyright must contain Dan Joseph Ortega"
    assert "Copyright" in metadata.get("LegalCopyright", ""), "LegalCopyright must contain 'Copyright'"
    assert metadata.get("FileVersion") == expected_str, f"FileVersion must match {expected_str}"
    assert metadata.get("ProductVersion") == expected_str, f"ProductVersion must match {expected_str}"
    assert metadata.get("ProductName") == "CvSU Document Generator"
    assert metadata.get("OriginalFilename") == "CvSU Gen.exe"
    assert "danjoseph.ortega@cvsu.edu.ph" in metadata.get("Comments", "")


def test_spec_and_build_bat_integration():
    """Ensure both PyInstaller .spec and build.bat wire file_version_info.txt."""
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        spec_content = f.read()
    assert "version='file_version_info.txt'" in spec_content or 'version="file_version_info.txt"' in spec_content, (
        "CvSU Gen.spec must specify version='file_version_info.txt'"
    )

    with open(BUILD_BAT_PATH, "r", encoding="utf-8") as f:
        bat_content = f.read()
    assert '--version-file "file_version_info.txt"' in bat_content, (
        "build.bat must pass --version-file 'file_version_info.txt'"
    )
    assert "sign_exe.ps1" in bat_content, "build.bat must invoke sign_exe.ps1 for digital signing"


def test_code_signing_scripts_exist():
    """Ensure PowerShell and batch scripts for certificate creation and signing exist."""
    assert os.path.exists(CREATE_CERT_PATH), "create_code_signing_cert.ps1 must exist"
    assert os.path.exists(SIGN_EXE_PATH), "sign_exe.ps1 must exist"
    assert os.path.exists(INSTALL_PUBLISHER_PATH), "install_trusted_publisher.bat must exist"

    with open(CREATE_CERT_PATH, "r", encoding="utf-8") as f:
        cert_content = f.read()
    assert "Dan Joseph Ortega" in cert_content
    assert "CvSU Main - Indang Campus" in cert_content
    assert "New-SelfSignedCertificate" in cert_content

    with open(SIGN_EXE_PATH, "r", encoding="utf-8") as f:
        sign_content = f.read()
    assert "signtool" in sign_content.lower()
    assert "Dan Joseph Ortega" in sign_content


def test_dist_exe_properties_and_signature_if_built():
    """If CvSU Gen.exe has been compiled in dist, verify its version info and signature."""
    exe_path = os.path.join(EXECUTABLE_DIR, "dist", "CvSU Gen.exe")
    if not os.path.exists(exe_path):
        exe_path = os.path.join(EXECUTABLE_DIR, "dist", "CvSU Gen (Beta).exe")
    if not os.path.exists(exe_path):
        pytest.skip("dist executable has not been built yet")

    import subprocess
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"$item = (Get-Item '{exe_path}').VersionInfo; "
        f"$sig = Get-AuthenticodeSignature '{exe_path}'; "
        f"Write-Output \"COPYRIGHT:$($item.LegalCopyright)\"; "
        f"Write-Output \"COMPANY:$($item.CompanyName)\"; "
        f"Write-Output \"PRODUCT:$($item.ProductName)\"; "
        f"Write-Output \"STATUS:$($sig.Status)\"; "
        f"Write-Output \"SIGNER:$($sig.SignerCertificate.Subject)\""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = res.stdout

    assert "COPYRIGHT:" in output and "Dan Joseph Ortega" in output
    assert "COMPANY:Dan Joseph Ortega" in output
    assert "PRODUCT:CvSU Document Generator" in output
    assert "STATUS:Valid" in output or "STATUS:UnknownError" in output
    assert "Dan Joseph Ortega" in output
    assert "CvSU Main - Indang Campus" in output

