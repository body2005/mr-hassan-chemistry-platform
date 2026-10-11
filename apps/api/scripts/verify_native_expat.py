"""Exercise native Expat and both matching Python XML bindings.

Run in the API and encoder images. No inputs, credentials or network needed.
"""
import ctypes
import ctypes.util
import json
import pyexpat
import _elementtree
import xml.etree.ElementTree as etree


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
    expat.XML_GetBuffer.argtypes = [ctypes.c_void_p, ctypes.c_int]
    expat.XML_GetBuffer.restype = ctypes.c_void_p
    expat.XML_ParseBuffer.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    expat.XML_ParseBuffer.restype = ctypes.c_int
    expat.XML_GetErrorCode.argtypes = [ctypes.c_void_p]
    expat.XML_GetErrorCode.restype = ctypes.c_int
    version = expat.XML_ExpatVersion().decode("ascii")
    native_version = tuple(map(int, version.removeprefix("expat_").split(".")))
    if native_version < (2, 9, 0) or pyexpat.version_info < (2, 9, 0):
        raise RuntimeError(f"Expat2.9.0 required for both paths: native={version}, Python={pyexpat.EXPAT_VERSION}")
    if etree.Element is not _elementtree.Element:
        raise RuntimeError("Python XML C accelerator is unavailable")
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
            results.append({"case": "native-utf16", "codec": codec, "valid_input": bool(expected), "passed": actual == expected})
            for binding, parse in (("pyexpat", lambda value: pyexpat.ParserCreate().Parse(value, True)),
                                   ("elementtree", etree.fromstring)):
                try:
                    parse(payload)
                    valid = True
                except (pyexpat.ExpatError, etree.ParseError):
                    valid = False
                results.append({"case": f"{binding}-utf16", "codec": codec,
                                "valid_input": bool(expected), "passed": valid == bool(expected)})

    # The actual upstream1393 regression: both final/non-final requests,
    # initialized/parsing states and a valid parse after rejection. No handler
    # reads or prints heap data. Version preflight rejects old vulnerable libs.
    no_buffer = pyexpat.errors.codes[pyexpat.errors.XML_ERROR_NO_BUFFER]
    invalid_argument = pyexpat.errors.codes[pyexpat.errors.XML_ERROR_INVALID_ARGUMENT]
    for final in (0, 1):
        parser = expat.XML_ParserCreate(None)
        if not parser:
            raise RuntimeError("Native XML parser allocation failed")
        try:
            status = expat.XML_ParseBuffer(parser, 10, final)
            results.append({"case": "no-buffer", "final": final,
                            "passed": status == 0 and expat.XML_GetErrorCode(parser) == no_buffer})
            buffer = expat.XML_GetBuffer(parser, 10)
            if not buffer:
                raise RuntimeError("Native XML buffer allocation failed")
            status = expat.XML_ParseBuffer(parser, 10000, final)
            results.append({"case": "initial-buffer-capacity", "final": final,
                            "passed": status == 0 and expat.XML_GetErrorCode(parser) == invalid_argument})
            ctypes.memmove(buffer, b"<r></r>", 7)
            results.append({"case": "valid-after-rejection", "final": final,
                            "passed": expat.XML_ParseBuffer(parser, 7, 0) == 1})
            status = expat.XML_ParseBuffer(parser, 10000, final)
            results.append({"case": "parsing-buffer-capacity", "final": final,
                            "passed": status == 0 and expat.XML_GetErrorCode(parser) == invalid_argument})
        finally:
            expat.XML_ParserFree(parser)
    report = {"library": library, "native_version": version, "results": results,
              "python_version": pyexpat.EXPAT_VERSION, "elementtree_accelerator": True,
              "passed": sum(r["passed"] for r in results),
              "failed": sum(not r["passed"] for r in results), "skipped": 0}
    print(json.dumps(report))
    if report["failed"]:
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    verify()
