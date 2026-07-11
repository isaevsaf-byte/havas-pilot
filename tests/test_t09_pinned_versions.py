"""Test suite for T-09: Pin versions in requirements.txt"""
import re
from pathlib import Path


def test_requirements_all_pinned():
    """All packages in requirements.txt should have pinned versions (==)."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    with open(req_path) as f:
        lines = f.readlines()

    unpinned = []
    for line in lines:
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue
        # Package line must have == operator
        if line and not "==" in line:
            unpinned.append(line)

    assert len(unpinned) == 0, f"Unpinned packages found:\n{chr(10).join(unpinned)}"


def test_requirements_has_sections():
    """requirements.txt should have organized sections."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    with open(req_path) as f:
        content = f.read()

    required_sections = [
        "# === CORE",
        "# === CLOUD",
        "# === UI",
        "# === UTILITIES",
    ]

    for section in required_sections:
        assert section in content, f"Missing section: {section}"


def test_requirements_core_packages_present():
    """Core ML packages should be present with versions."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    with open(req_path) as f:
        content = f.read()

    core_packages = [
        "torch==",
        "torchvision==",
        "ultralytics==",
        "supervision==",
        "opencv-python==",
        "torchreid==",
        "numpy==",
    ]

    for pkg in core_packages:
        assert pkg in content, f"Core package missing: {pkg}"


def test_requirements_cloud_packages_present():
    """Cloud/Supabase packages should be present with versions."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    with open(req_path) as f:
        content = f.read()

    cloud_packages = [
        "supabase==",
        "postgrest==",
        "storage3==",
        "realtime==",
    ]

    for pkg in cloud_packages:
        assert pkg in content, f"Cloud package missing: {pkg}"


def test_requirements_ui_packages_present():
    """UI packages should be present with versions."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    with open(req_path) as f:
        content = f.read()

    ui_packages = [
        "streamlit==",
        "plotly==",
        "pandas==",
    ]

    for pkg in ui_packages:
        assert pkg in content, f"UI package missing: {pkg}"


def test_requirements_version_format():
    """All versions should follow semantic versioning format."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    with open(req_path) as f:
        lines = f.readlines()

    version_pattern = re.compile(r"^[a-zA-Z0-9\-_.]+==[\d.]+.*$")

    bad_versions = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not version_pattern.match(line):
            bad_versions.append(line)

    assert len(bad_versions) == 0, f"Bad version format:\n{chr(10).join(bad_versions)}"


def test_requirements_no_duplicates():
    """requirements.txt should not have duplicate packages."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    with open(req_path) as f:
        lines = f.readlines()

    packages = []
    duplicates = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg_name = line.split("==")[0].lower()
        if pkg_name in packages:
            duplicates.append(pkg_name)
        packages.append(pkg_name)

    assert len(duplicates) == 0, f"Duplicate packages found: {duplicates}"


def test_requirements_file_exists():
    """requirements.txt must exist."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    assert req_path.exists(), f"requirements.txt not found at {req_path}"
    assert req_path.stat().st_size > 0, "requirements.txt is empty"
