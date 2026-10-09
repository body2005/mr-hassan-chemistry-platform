"""Offline guards: CI must exercise the reviewed native runtime, not skip it."""
from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[3] / '.github/workflows/quality.yml'


class BackendEnvironment(unittest.TestCase):
    def setUp(self):
        self.backend = WORKFLOW.read_text(encoding='utf-8').split(
            '\n  backend:', 1)[1].split('\n  browser-and-images:', 1)[0]

    def test_builds_production_api_then_test_layer_from_recorded_image(self):
        self.assertIn('-f infra/Dockerfile.api ', self.backend)
        self.assertIn("--format '{{.Id}}' > artifacts/api-image-id.txt", self.backend)
        self.assertIn('-f infra/Dockerfile.qa ', self.backend)
        self.assertIn('API_TEST_IMAGE=qa-ci-api', self.backend)
        self.assertEqual(self.backend.count('= "$(cat artifacts/api-image-id.txt)"'), 2)
        self.assertNotIn('actions/setup-python', self.backend)

    def test_no_native_test_exclusion_or_failure_suppression(self):
        self.assertIn('-m pytest tests --ignore=tests/integration', self.backend)
        self.assertNotIn('--ignore=tests/test_native_expat_security.py', self.backend)
        self.assertNotIn('continue-on-error', self.backend)
        self.assertNotIn('|| true', self.backend)
        self.assertIn('--network none', self.backend)
        self.assertIn('--junitxml=/qa/backend.xml', self.backend)

    def test_migrations_and_package_audit_use_same_recorded_test_image(self):
        self.assertEqual(self.backend.count('"$(cat artifacts/backend-image-id.txt)"'), 3)
        self.assertIn('-m scripts.ci_migrations', self.backend)
        self.assertIn('-m pip_audit -r requirements.lock', self.backend)


if __name__ == '__main__':
    unittest.main(verbosity=2)
