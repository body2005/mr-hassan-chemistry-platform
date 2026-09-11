from __future__ import annotations

import json

from app.services import ai_service


def test_ollama_generate_runtime_path_has_required_imports(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"response": json.dumps({"ok": True})}).encode()

    monkeypatch.setenv("OLLAMA_TIMEOUT", "0.05")
    monkeypatch.setattr(ai_service.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    assert ai_service._ollama_generate("hello", "test-model") == {"ok": True}
