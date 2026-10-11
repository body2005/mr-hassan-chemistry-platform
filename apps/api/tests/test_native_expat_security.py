from scripts.verify_native_expat import verify


def test_native_and_python_expat_cover_utf16_and_buffer_capacity_regressions():
    report = verify()
    expected = {
        (kind, codec, valid, None)
        for kind in ("native-utf16", "pyexpat-utf16", "elementtree-utf16")
        for codec in ("utf-16-le", "utf-16-be")
        for valid in (False, True)
    } | {
        (kind, None, None, final)
        for kind in ("no-buffer", "initial-buffer-capacity", "valid-after-rejection", "parsing-buffer-capacity")
        for final in (0, 1)
    }
    results = report["results"]
    assert len(results) == len(expected) == 20
    assert {(case["case"], case.get("codec"), case.get("valid_input"), case.get("final"))
            for case in results} == expected
    assert all(case["passed"] for case in results)
    assert report["passed"] == 20
    assert report["failed"] == report["skipped"] == 0
    assert report["python_version"] == report["native_version"]
    assert report["elementtree_accelerator"] is True
