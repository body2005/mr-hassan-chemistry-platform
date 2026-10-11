from unittest.mock import Mock
import io
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from app.core.storage import S3StorageProvider


def test_missing_object_is_distinct_from_store_outage():
    storage = S3StorageProvider(bucket_name="private")
    storage._client = Mock()
    storage._client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
    assert storage.exists("missing") is False
    storage._client.head_object.side_effect = EndpointConnectionError(endpoint_url="http://s3:8333")
    with pytest.raises(EndpointConnectionError):
        storage.exists("present")


def test_storage_stream_closes_on_client_disconnect():
    storage = S3StorageProvider(bucket_name="private")
    storage._client = Mock()
    body = io.BytesIO(b"protected content")
    storage._client.get_object.return_value = {"Body": body}
    stream = storage.open_stream("video")
    assert next(stream) == b"protected content"
    stream.close()
    assert body.closed


def test_storage_timeouts_are_bounded():
    storage = S3StorageProvider(endpoint_url="http://s3:8333", bucket_name="private",
                                access_key_id="test", secret_access_key="test", region_name="us-east-1")
    config = storage._get_client().meta.config
    assert config.connect_timeout == 3 and config.read_timeout == 15
