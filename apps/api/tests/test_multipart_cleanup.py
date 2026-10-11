from unittest.mock import MagicMock

from botocore.exceptions import ClientError
import pytest
from app.core.storage import S3StorageProvider


def provider(monkeypatch, pages):
    store = S3StorageProvider.__new__(S3StorageProvider)
    store.bucket_name = "qa-bucket"
    client = MagicMock()
    client.get_paginator.return_value.paginate.return_value = iter(pages)
    monkeypatch.setattr(store, "_get_client", lambda: client)
    return store, client


def test_only_exact_retired_key_is_aborted_across_pages(monkeypatch):
    store, client = provider(monkeypatch, [{"Uploads": [{"Key": "asset-other", "UploadId": "live"}]},
        {"Uploads": [{"Key": "asset", "UploadId": "retired"}]}])
    assert store.abort_incomplete_uploads("s3://qa-bucket/asset") == 1
    client.abort_multipart_upload.assert_called_once_with(Bucket="qa-bucket", Key="asset", UploadId="retired")


@pytest.mark.parametrize("code,raises", [("NoSuchUpload", False), ("ServiceUnavailable", True), ("AccessDenied", True)])
def test_already_aborted_is_idempotent_but_storage_or_permission_failure_is_not_acknowledged(monkeypatch, code, raises):
    store, client = provider(monkeypatch, [{"Uploads": [{"Key": "asset", "UploadId": "retired"}]}])
    client.abort_multipart_upload.side_effect = ClientError({"Error": {"Code": code}}, "AbortMultipartUpload")
    if raises:
        with pytest.raises(ClientError):
            store.abort_incomplete_uploads("asset")
    else:
        assert store.abort_incomplete_uploads("asset") == 1


def test_cleanup_budget_leaves_more_allocations_for_a_durable_retry(monkeypatch):
    store, client = provider(monkeypatch, [{"Uploads": [{"Key": "asset", "UploadId": str(i)} for i in range(101)]}])
    with pytest.raises(RuntimeError, match="budget"):
        store.abort_incomplete_uploads("asset")
    assert client.abort_multipart_upload.call_count == 100
