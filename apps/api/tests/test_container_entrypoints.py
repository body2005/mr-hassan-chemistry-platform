from pathlib import Path
import os
import subprocess


def test_ocr_launcher_keeps_posix_line_endings_in_clean_checkout():
    source = Path(os.environ.get('QA_REPO_ROOT') or Path(__file__).resolve().parents[3])
    launcher = source / 'apps/api/scripts/tesseract_limited.py'
    assert b'\r\n' not in launcher.read_bytes(), 'Linux shebang must survive Windows checkout'
    # The actual Docker entrypoint must also execute, not just exist. Host
    # Windows runs validate source bytes; Linux validates interpreter lookup.
    if os.name == 'posix' and Path('/srv').is_dir():
        installed = Path('/srv/scripts/tesseract_limited.py')
        result = subprocess.run([str(installed), '--version'], capture_output=True, timeout=10)
        assert result.returncode == 0
        assert b'tesseract' in result.stdout
