"""Read-only evidence for OS CVE reachability; no exploitation or suppression."""
import importlib.util
import json
import subprocess
import shutil
import pyexpat
import zlib
from lxml import etree
from docx.oxml.parser import oxml_parser

report = {
    "libxml2_python_sax_binding_installed": importlib.util.find_spec("libxml2") is not None,
    "lxml_bundled_libxml_version": etree.LIBXML_VERSION,
    "python_expat_version": pyexpat.EXPAT_VERSION,
    "python_zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
    "docx_parser_resolves_external_entity": None,
}
sample = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/hostname">]><x>&e;</x>'
root = etree.fromstring(sample, oxml_parser)
report["docx_parser_resolves_external_entity"] = root.text is not None
report["packages"] = {}
installed_lines = []
for package in ("libssl3t64", "openssl", "libxml2", "libexpat1", "zlib1g", "liblzma5",
                "tesseract-ocr", "libtesseract5", "poppler-utils", "curl", "libarchive13t64"):
    # Missing optional packages are reported explicitly, never silently treated
    # as patched. Unexpected query errors still fail this evidence tool.
    result = subprocess.run(["dpkg-query", "-W", "-f=${db:Status-Status}|${Version}", package],
                            text=True, capture_output=True, timeout=5)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"Package inventory failed: {package}")
    status_and_version = result.stdout.partition("|")
    installed = result.returncode == 0 and status_and_version[0] == "installed"
    version = status_and_version[2].strip() if installed else None
    report["packages"][package] = {"installed": installed, "version": version,
                                  "query_exit": result.returncode}
    if installed:
        installed_lines.append(f"{package} {version}")
report["dpkg"] = "\n".join(installed_lines)
report["library_links"] = {}
for name, executable in (("python_expat", pyexpat.__file__),
                         ("pdftotext", shutil.which("pdftotext")),
                         ("tesseract", shutil.which("tesseract"))):
    report["library_links"][name] = (subprocess.check_output(["ldd", executable], text=True, timeout=5)
                                     if executable else None)
report["tesseract_version"] = subprocess.check_output(["tesseract", "--version"], text=True, timeout=5)
print(json.dumps(report, indent=2))
