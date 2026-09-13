import os
import io
import zipfile
import pytest
from unittest.mock import patch

from modules.common.docx_utils import load_docx

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_TEMPLATE = os.path.join(WORKSPACE_DIR, "templates", "template_syllabus.docx")


def test_load_docx_success_first_attempt():
    """Verify that load_docx succeeds on the first attempt when file is unobstructed."""
    assert os.path.exists(SAMPLE_TEMPLATE), f"Template missing at {SAMPLE_TEMPLATE}"
    
    zin, root, body = load_docx(SAMPLE_TEMPLATE)
    assert isinstance(zin, zipfile.ZipFile)
    assert root is not None
    assert body is not None
    zin.close()


def test_load_docx_raises_filenotfound_immediately():
    """Verify that load_docx does not retry or delay when the file genuinely does not exist."""
    with patch("time.sleep") as mock_sleep:
        with pytest.raises(FileNotFoundError):
            load_docx(os.path.join(WORKSPACE_DIR, "templates", "non_existent_template.docx"))

        assert mock_sleep.call_count == 0, "FileNotFoundError must raise immediately without retry delay"


def test_load_docx_retry_on_transient_permission_error():
    """Verify that load_docx recovers from transient PermissionError / sharing violations."""
    assert os.path.exists(SAMPLE_TEMPLATE)

    with open(SAMPLE_TEMPLATE, "rb") as f:
        real_data = f.read()

    call_count = 0

    def mock_open_file(path, mode="rb", *args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Fail first 2 attempts with Windows sharing violation / Permission denied
        if call_count < 3:
            raise PermissionError(13, f"The process cannot access the file because it is being used by another process: '{path}'")
        return io.BytesIO(real_data)

    with patch("builtins.open", side_effect=mock_open_file):
        with patch("time.sleep") as mock_sleep:
            zin, root, body = load_docx(SAMPLE_TEMPLATE)
            
            assert call_count == 3, f"Expected 3 attempts before success, got {call_count}"
            assert mock_sleep.call_count == 2, f"Expected 2 sleep intervals, got {mock_sleep.call_count}"
            assert root is not None
            assert body is not None
            zin.close()


def test_load_docx_raises_after_max_retries_exhausted():
    """Verify that load_docx raises the underlying exception if persistent locks exceed max attempts (6 attempts, 5 sleeps)."""
    call_count = 0

    def persistent_failure(path, mode="rb", *args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise PermissionError(13, "Permanent lock")

    with patch("builtins.open", side_effect=persistent_failure):
        with patch("time.sleep") as mock_sleep:
            with pytest.raises(PermissionError) as exc_info:
                load_docx(SAMPLE_TEMPLATE)

            assert "Permanent lock" in str(exc_info.value)
            assert call_count == 6, f"Expected 6 attempts before giving up, got {call_count}"
            assert mock_sleep.call_count == 5, f"Expected 5 sleep backoffs (no sleep after final attempt), got {mock_sleep.call_count}"


def test_load_docx_backoff_durations():
    """Verify that retry backoff delays increase proportionally and stay bounded under 2.5 seconds total."""
    delays = []

    def mock_sleep_record(duration):
        delays.append(duration)

    with open(SAMPLE_TEMPLATE, "rb") as f:
        real_data = f.read()

    call_count = 0

    def fail_until_fourth(path, mode="rb", *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            raise OSError(32, "Sharing violation")
        return io.BytesIO(real_data)

    with patch("builtins.open", side_effect=fail_until_fourth):
        with patch("time.sleep", side_effect=mock_sleep_record):
            zin, root, body = load_docx(SAMPLE_TEMPLATE)
            assert len(delays) == 3
            # Delays should increase monotonically
            assert delays[0] < delays[1] < delays[2]
            # Total retry overhead should be < 1.5s for transient recovery
            assert sum(delays) < 1.5
            zin.close()
