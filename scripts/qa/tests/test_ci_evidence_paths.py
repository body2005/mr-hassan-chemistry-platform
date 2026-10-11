"""Offline guard for retained browser results, excluding private trace/state files."""
import fnmatch
import os
from pathlib import Path
import re
import unittest


WORKFLOW = Path(os.environ.get('QA_WORKFLOW_FILE',
    Path(__file__).resolve().parents[3] / '.github/workflows/quality.yml'))


def browser_artifact_patterns():
    text = WORKFLOW.read_text(encoding='utf-8')
    block = text.split('name: local-browser-images', 1)[1].split('\n  secrets:', 1)[0]
    return re.findall(r'^ {12}(\S.*)$', block, re.MULTILINE)


class BrowserEvidencePaths(unittest.TestCase):
    def included(self, relative):
        # upload-artifact also recursively includes selected directories.
        return any(fnmatch.fnmatchcase(relative, pattern) or
                   fnmatch.fnmatchcase(relative, pattern.rstrip('/') + '/**')
                   for pattern in browser_artifact_patterns())

    def test_current_browser_junit_and_image_manifest_are_retained(self):
        for name in ('browser.xml', 'command.json'):
            self.assertTrue(self.included(
                '.qa/audit2/trusted-browser-20261009-055915/' + name), name)

    def test_current_browser_screenshot_is_retained(self):
        self.assertTrue(self.included(
            '.qa/audit2/trusted-browser-20261009-055915/artifacts/qa-example/mobile-dark.png'))

    def test_private_traces_session_state_inbox_and_keys_are_not_retained(self):
        for relative in (
            '.qa/audit2/trusted-browser-20261009-055915/artifacts/qa-example/trace.zip',
            '.qa/audit2/trusted-browser-20261009-055915/artifacts/qa-example/headers.json',
            '.qa/audit2/trusted-browser-20261009-055915/storage-state.json',
            '.qa/audit2/inbox/messages.json', '.qa/audit2/secrets/cert.key',
        ):
            self.assertFalse(self.included(relative), relative)


if __name__ == '__main__':
    unittest.main(verbosity=2)
