"""Linux libstdc++ aligned-new overflow probe (not a scanner waiver).

Calls the actual runtime library's non-throwing C++ ABI entry point. Never
dereferences a large allocation. The nine overflow cases come from GCC's
upstream CVE-2026-95619 regression; a tenth case checks valid allocation.
Mount read-only into an isolated API/encoder container and run with Python.
"""
import ctypes
import json
import sys

if not sys.platform.startswith("linux") or ctypes.sizeof(ctypes.c_void_p) != 8:
    raise SystemExit("This probe requires the tested Linux 64-bit C++ ABI")
lib = ctypes.CDLL("libstdc++.so.6")
allocate = getattr(lib, "_ZnwmSt11align_val_tRKSt9nothrow_t")
allocate.argtypes = [ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p]
allocate.restype = ctypes.c_void_p
release = getattr(lib, "_ZdlPvSt11align_val_t")
release.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
release.restype = None
nothrow = ctypes.c_char.in_dll(lib, "_ZSt7nothrow")
maximum = (1 << 64) - 1
cases = [(maximum - 8, 32), (maximum, 8), (maximum, 32),
         (maximum, 1024), (maximum, 65536), (maximum - 1, 16),
         (maximum - 1025, 1024), (maximum - 1024, 1024),
         (maximum - 65536, 65536), (64, 32)]
results = []
for size, alignment in cases:
    pointer = allocate(size, alignment, ctypes.addressof(nothrow))
    expected_valid = size == 64
    passed = bool(pointer and pointer % alignment == 0) if expected_valid else pointer is None
    if pointer:
        release(pointer, alignment)
    results.append({"size": size, "alignment": alignment,
                    "expected_valid": expected_valid, "passed": passed})
report = {"library": "libstdc++.so.6", "results": results,
          "passed": sum(r["passed"] for r in results),
          "failed": sum(not r["passed"] for r in results), "skipped": 0,
          "scope": "nothrow aligned-new on this Linux ABI only; not PBDS or every C++ path"}
print(json.dumps(report))
raise SystemExit(bool(report["failed"]))
