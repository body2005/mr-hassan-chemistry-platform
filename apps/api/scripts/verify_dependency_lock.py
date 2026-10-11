"""Assert installed, editable and wheel runtime requirements match the lock.

Run in a clean Python 3.12 Linux venv after installing .[dev] and building
the wheel. Extra development tools are explicitly outside this runtime lock.
"""
import argparse
import email
import importlib.metadata as metadata
import json
from pathlib import Path
import zipfile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def runtime_requirements(lines):
    result = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        req = Requirement(line)
        if req.marker and not req.marker.evaluate({"extra": ""}):
            continue
        specs = list(req.specifier)
        assert len(specs) == 1 and specs[0].operator == "==", f"Unpinned requirement: {req.name}"
        name = canonicalize_name(req.name)
        assert name not in result, f"Duplicate runtime requirement: {name}"
        result[name] = specs[0].version
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    locked = runtime_requirements((root / "requirements.lock").read_text().splitlines())
    installed = {name: metadata.version(name) for name in locked}
    assert installed == locked, {"installed_lock_mismatches": {
        name: [locked[name], installed[name]] for name in locked if installed[name] != locked[name]}}
    editable = runtime_requirements(metadata.requires("learning-website-api") or [])
    assert editable == locked, "Editable runtime metadata diverges from requirements.lock"
    with zipfile.ZipFile(args.wheel) as wheel:
        paths = [p for p in wheel.namelist() if p.endswith(".dist-info/METADATA")]
        assert len(paths) == 1, "Expected one wheel metadata record"
        headers = email.message_from_bytes(wheel.read(paths[0]))
        built = runtime_requirements(headers.get_all("Requires-Dist", []))
    assert built == locked, "Wheel runtime metadata diverges from requirements.lock"
    print(json.dumps({"runtime_packages_verified": len(locked), "installed": "match",
                      "editable_metadata": "match", "wheel_metadata": "match",
                      "dev_transitives_fully_locked": False}))


if __name__ == "__main__":
    main()
