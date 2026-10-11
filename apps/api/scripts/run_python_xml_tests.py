"""Build-only matching-source XML compatibility gate, without test exclusions."""
import json
import unittest
import _elementtree
import pyexpat
import xml.etree.ElementTree as etree

assert pyexpat.version_info == (2, 9, 0), pyexpat.EXPAT_VERSION
assert etree.Element is _elementtree.Element, "C accelerator must work, not become skipped"
suite = unittest.defaultTestLoader.loadTestsFromNames([
    "test.test_pyexpat", "test.test_xml_etree", "test.test_xml_etree_c",
    "test.test_sax", "test.test_minidom",
])
result = unittest.TextTestRunner(verbosity=1).run(suite)
report = {"total": result.testsRun, "passed": result.testsRun - len(result.errors)
          - len(result.failures) - len(result.skipped),
          "failed": len(result.errors) + len(result.failures), "skipped": len(result.skipped),
          "skip_reasons": [{"test": str(test), "reason": reason} for test, reason in result.skipped]}
with open("/build/python-xml-tests.json", "w", encoding="utf-8") as output:
    json.dump(report, output, indent=2)
print(json.dumps({key: report[key] for key in ("total", "passed", "failed", "skipped")}), flush=True)
if any("requires _elementtree" in reason for _, reason in result.skipped):
    raise SystemExit("Missing C accelerator is a build failure, not a permitted skip")
raise SystemExit(0 if result.wasSuccessful() else 1)
