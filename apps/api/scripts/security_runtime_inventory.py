"""Read-only evidence for OS CVE reachability; no exploitation or suppression."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
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
report["dpkg"] = subprocess.check_output(["dpkg-query", "-W", "-f=${Package} ${Version}\n",
                                          "libssl3t64", "openssl", "libxml2", "libexpat1", "zlib1g"], text=True)
report["library_links"] = {
    "python_expat": subprocess.check_output(["ldd", pyexpat.__file__], text=True),
    "pdftotext": subprocess.check_output(["ldd", "/usr/bin/pdftotext"], text=True),
    "tesseract": subprocess.check_output(["ldd", "/usr/bin/tesseract"], text=True),
}
print(json.dumps(report, indent=2))
