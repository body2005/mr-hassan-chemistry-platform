import pytest

from tests.fixture_media import padded_webm


@pytest.mark.parametrize('unknown', [False, True])
def test_padding_preserves_segment_payload_and_declares_exact_new_size(tmp_path, unknown):
    payload = b'unchanged-media-payload'
    length = (1 << 56) - 1 if unknown else len(payload)
    original = b'\x1a\x45\xdf\xa3' + b'\x18\x53\x80\x67' + ((1 << 56) | length).to_bytes(8, 'big') + payload
    source, output = tmp_path / 'source.webm', tmp_path / 'boundary.webm'
    source.write_bytes(original)
    padded_webm(source, output, 4096)
    actual = output.read_bytes()
    assert len(actual) == 4096 and source.read_bytes() == original
    assert int.from_bytes(actual[8:16], 'big') & ((1 << 56) - 1) == 4096 - 16
    assert actual[16:16 + len(payload)] == payload
    assert actual[16 + len(payload)] == 0xec


@pytest.mark.parametrize('header', [b'not-webm', b'\x18\x53\x80\x67\x80',
    b'\x18\x53\x80\x67' + ((1 << 56) | 7).to_bytes(8, 'big') + b'wrong'])
def test_padding_rejects_invalid_segment_without_creating_output(tmp_path, header):
    source, output = tmp_path / 'source.webm', tmp_path / 'boundary.webm'
    source.write_bytes(header)
    with pytest.raises(ValueError):
        padded_webm(source, output, 4096)
    assert not output.exists() and source.read_bytes() == header
