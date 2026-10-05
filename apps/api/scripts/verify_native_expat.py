"""Exercise the dynamically linked Expat, not Python's bundled pyexpat.

Run in the API and encoder images. No inputs, credentials or network needed.
"""
import ctypes
import ctypes.util
import json


def verify():
    library = ctypes.util.find_library("expat")
    if not library:
        raise RuntimeError("Native Expat is missing")
    expat = ctypes.CDLL(library)
    expat.XML_ExpatVersion.restype = ctypes.c_char_p
    expat.XML_ParserCreate.argtypes = [ctypes.c_char_p]
    expat.XML_ParserCreate.restype = ctypes.c_void_p
    expat.XML_Parse.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    expat.XML_Parse.restype = ctypes.c_int
    expat.XML_ParserFree.argtypes = [ctypes.c_void_p]
    version = expat.XML_ExpatVersion().decode("ascii")
    results = []
    for codec, bom in (("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")):
        # A high surrogate followed by an ordinary letter must not consume the
        # letter and be accepted as a valid surrogate pair (CVE-2026-93990).
        for text, expected in (("<r>\ud800A</r>", 0), ("<r>\U0001f600A</r>", 1)):
            payload = bom + text.encode(codec, errors="surrogatepass")
            parser = expat.XML_ParserCreate(None)
            if not parser:
                raise RuntimeError("Native XML parser allocation failed")
            try:
                actual = expat.XML_Parse(parser, payload, len(payload), 1)
            finally:
                expat.XML_ParserFree(parser)
            results.append({"codec": codec, "valid_input": bool(expected), "passed": actual == expected})
    report = {"library": library, "native_version": version, "results": results,
              "passed": sum(r["passed"] for r in results),
              "failed": sum(not r["passed"] for r in results), "skipped": 0}
    print(json.dumps(report))
    if report["failed"] or tuple(map(int, version.removeprefix("expat_").split("."))) < (2, 8, 5):
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    verify()
