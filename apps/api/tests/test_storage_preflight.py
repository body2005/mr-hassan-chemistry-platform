from botocore.exceptions import ClientError
import pytest
from app.core.storage import S3StorageProvider
from scripts.storage_preflight import main


@pytest.mark.parametrize('code, expected', [('404', FileNotFoundError), ('NoSuchKey', FileNotFoundError),
                                           ('AccessDenied', ClientError), ('503', ClientError)])
def test_object_missing_is_distinct_from_storage_outage(code, expected):
    class Client:
        def head_object(self, **kwargs):
            raise ClientError({'Error': {'Code': code}}, 'HeadObject')
    provider = S3StorageProvider()
    provider._client = Client()
    with pytest.raises(expected):
        provider.get_size('private/video.mp4')


def test_preflight_only_reports_missing_names_not_values(monkeypatch, capsys):
    monkeypatch.setenv('S3_ACCESS_KEY_ID', 'private-test-value')
    monkeypatch.delenv('S3_BUCKET_NAME', raising=False)
    monkeypatch.delenv('S3_SECRET_ACCESS_KEY', raising=False)
    assert main() == 1
    output = capsys.readouterr().out
    assert 'S3_BUCKET_NAME' in output
    assert 'private-test-value' not in output


def test_preflight_uses_configured_private_bucket(monkeypatch, capsys):
    for name, value in dict(STORAGE_BACKEND='s3', S3_ENDPOINT_URL='https://example.com',
            S3_BUCKET_NAME='bucket', S3_ACCESS_KEY_ID='private-id', S3_SECRET_ACCESS_KEY='private-key').items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(S3StorageProvider, 'check_readiness', lambda self: {'status': 'ok'})
    assert main() == 0
    assert capsys.readouterr().out == 'Private object storage read/write/delete: OK\n'
