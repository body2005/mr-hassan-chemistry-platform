from .live_helpers import container, isolated


def test_api_is_nonroot_without_capabilities_and_can_use_storage():
    isolated()
    api = container('api')
    result = api.exec_run(['python', '-m', 'scripts.verify_runtime_permissions'])
    assert result.exit_code == 0, 'API runtime permission probe failed'
    assert b'uid=10001 gid=10001 cap_eff=0' in result.output
