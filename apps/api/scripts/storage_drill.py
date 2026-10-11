"""Live upload/access/byte-range and post-recreation assertions. QA only."""
from __future__ import annotations
import base64
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urljoin

import requests
from tests.integration.live_helpers import BASE, clear_auth, lesson, session
from scripts import s3_snapshot

ARTIFACT = Path("/qa/storage-checkpoint.json")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checkpoint():
    clear_auth()
    with session() as teacher, session("student01@demo.com", "qa-student-pass") as student:
        course, video = lesson(teacher, "video")
        media = Path(os.environ["QA_MEDIA_DIR"]) / "video.webm"
        with media.open("rb") as source:
            response = teacher.post(f"{BASE}/lessons/{video['id']}/video", files={"file": ("video.webm", source, "video/webm")}, timeout=120)
        assert response.status_code == 200, response.text
        assert student.post(f"{BASE}/courses/{course['id']}/enroll", timeout=10).status_code == 200
        document = Path(os.environ["QA_MEDIA_DIR"]) / "large.pdf"
        with document.open("rb") as source:
            response = teacher.post(f"{BASE}/lessons/{video['id']}/materials", files={"file": ("large.pdf", source, "application/pdf")}, timeout=120)
        assert response.status_code == 201, response.text
        material = response.json()
        paid_course, paid = lesson(teacher, price=25)
        assert student.post(f"{BASE}/courses/{paid_course['id']}/enroll", timeout=10).status_code == 200
        order_response = student.post(f"{BASE}/payments/orders", json={"product_type": "lesson", "product_id": paid["id"],
                                           "payment_method": "instapay", "payer_reference": "QA storage drill"}, timeout=10)
        assert order_response.status_code == 201, order_response.text
        order = order_response.json()
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==")
        response = student.post(f"{BASE}/payments/orders/{order['id']}/receipt", files={"receipt": ("receipt.png", png, "image/png")}, timeout=15)
        assert response.status_code == 200, response.text
        data = {"video_lesson": video["id"], "material_id": material["id"], "order_id": order["id"],
                "video_sha256": digest(media.read_bytes()), "pdf_sha256": digest(document.read_bytes()),
                "receipt_sha256": digest(png), "video_bytes": media.stat().st_size, "pdf_bytes": document.stat().st_size}
        ARTIFACT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    verify()


def verify():
    clear_auth()
    data = json.loads(ARTIFACT.read_text())
    with ExitStack() as sessions:
        teacher = sessions.enter_context(session())
        student = sessions.enter_context(session("student01@demo.com", "qa-student-pass"))
        outsider = sessions.enter_context(session("student02@demo.com", "qa-student-pass"))
        other_teacher = sessions.enter_context(session("teacher2@example.com", "qa-teacher2-pass"))
        # Interrupted runs must revoke their devices through the real API;
        # never increase session limits or directly clear the video ledger.
        assert student.post(f"{BASE}/auth/revoke-all", timeout=15).status_code == 204
        student.close()
        student = sessions.enter_context(session("student01@demo.com", "qa-student-pass"))
        response = student.post(f"{BASE}/lessons/{data['video_lesson']}/video-token", timeout=15)
        assert response.status_code == 200, response.text
        path = response.json()["stream_url"]
        url = urljoin(BASE.removesuffix("/api/v1") + "/", path)
        response = student.get(url, timeout=45)
        assert response.status_code == 200 and digest(response.content) == data["video_sha256"]
        source = (Path(os.environ["QA_MEDIA_DIR"]) / "video.webm").read_bytes()
        for start in (0, len(source) // 2, len(source) - 1024):
            end = start + 1023
            response = student.get(url, headers={"Range": f"bytes={start}-{end}"}, timeout=15)
            assert response.status_code == 206 and response.content == source[start:end + 1]
            assert response.headers["Content-Range"] == f"bytes {start}-{end}/{len(source)}"
        assert requests.get(url, verify=os.environ["QA_CA_FILE"], timeout=15).status_code == 403
        assert outsider.post(f"{BASE}/lessons/{data['video_lesson']}/video-token", timeout=15).status_code == 403
        download = f"{BASE}/lessons/{data['video_lesson']}/materials/{data['material_id']}/download"
        response = student.get(download, timeout=45)
        assert response.status_code == 200 and digest(response.content) == data["pdf_sha256"]
        assert outsider.get(download, timeout=15).status_code == 403
        receipt = f"{BASE}/payments/orders/{data['order_id']}/receipt"
        response = teacher.get(receipt, timeout=15)
        assert response.status_code == 200 and digest(response.content) == data["receipt_sha256"]
        assert outsider.get(receipt, timeout=15).status_code == 404
        assert other_teacher.get(receipt, timeout=15).status_code == 404
    s3, bucket = s3_snapshot.client(), os.environ["S3_BUCKET"]
    keys = s3_snapshot.objects(s3, bucket)
    assert keys
    # Private default must survive recreation and restoring content, not just API auth.
    endpoint = os.environ["S3_ENDPOINT_URL"]
    for path in (f"/{bucket}?list-type=2", f"/{bucket}/{next(iter(keys))}"):
        response = requests.get(endpoint + path, timeout=10)
        assert response.status_code == 403, f"Anonymous object-store access returned {response.status_code}"
    print(json.dumps({"phase": "verified", "video_bytes": data["video_bytes"], "pdf_bytes": data["pdf_bytes"],
                      "range_checks": 3, "checksum_mismatches": 0, "permission_failures": 0, "bucket_objects": len(keys)}))
    student.close()


if __name__ == "__main__":
    {"checkpoint": checkpoint, "verify": verify}[sys.argv[1]]()
