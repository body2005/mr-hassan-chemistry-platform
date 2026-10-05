from scripts.verify_native_expat import verify


def test_native_expat_rejects_malformed_utf16_and_accepts_valid_pairs():
    report = verify()
    assert report["passed"] == 4
    assert report["failed"] == report["skipped"] == 0
