"""Reject overflow before remote work; compensate only possible stored bytes."""
import asyncio
import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, UploadFile
from app.services import lesson_materials


@pytest.mark.parametrize('known_size', [True, False])
def test_material_overflow_needs_no_remote_upload_or_compensation(tmp_path, monkeypatch, known_size):
    monkeypatch.setenv('STORAGE_DIR', str(tmp_path))
    monkeypatch.setattr(lesson_materials, 'MAX_MATERIAL_BYTES', 16)
    lesson, course = SimpleNamespace(), SimpleNamespace()
    monkeypatch.setattr(lesson_materials, '_lesson_course', lambda *_args: (lesson, course))
    monkeypatch.setattr(lesson_materials, 'ensure_course_manager', lambda *_args: None)
    storage = Mock()
    provider = Mock(return_value=storage)
    monkeypatch.setattr('app.core.storage.get_storage_provider', provider)
    compensation = Mock(side_effect=RuntimeError('No remote bytes exist to compensate'))
    monkeypatch.setattr(lesson_materials, 'compensate_upload', compensation)
    body = b'%PDF-1.7\n' + b'x' * 20
    upload = UploadFile(io.BytesIO(body), filename='boundary.pdf', size=len(body) if known_size else None)
    try:
        with pytest.raises(HTTPException) as failure:
            asyncio.run(lesson_materials.upload_material(Mock(), Mock(), Mock(), upload))
        assert failure.value.status_code == 413
        storage.save_file.assert_not_called()
        compensation.assert_not_called()
        if known_size:
            provider.assert_not_called()
        assert not list(tmp_path.rglob('mat_*'))
    finally:
        asyncio.run(upload.close())
