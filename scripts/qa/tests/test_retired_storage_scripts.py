"""Offline regressions: retired entry points must never touch data or Docker."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPTS = Path(os.environ.get("QA_LEGACY_SCRIPTS", "/legacy"))


class RetiredStorageScripts(unittest.TestCase):
    def assert_refused(self, name, arguments=()):
        with tempfile.TemporaryDirectory(prefix="qa-retired-storage-") as directory:
            root = Path(directory)
            sentinel = root / "existing.dump"
            sentinel.write_bytes(b"Synthetic existing backup; must remain unchanged")
            before = sentinel.read_bytes()
            secret = "synthetic-secret-must-not-appear"
            result = subprocess.run(
                ["/bin/sh", str(SCRIPTS / name), *arguments],
                cwd=root, input="RESTORE\n", capture_output=True, text=True, timeout=5,
                env={"PATH": "/nonexistent", "BACKUP_ROOT": str(root / "new-backups"),
                     "POSTGRES_DB": secret, "MINIO_ROOT_USER": secret,
                     "MINIO_ROOT_PASSWORD": secret},
            )
            self.assertEqual(result.returncode, 64)
            self.assertIn("RETIRED", result.stderr)
            self.assertIn("docs/PRODUCTION_DOCKER_RUNBOOK.md", result.stderr)
            self.assertNotIn(secret, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(sentinel.read_bytes(), before)
            self.assertEqual(list(root.iterdir()), [sentinel])

    def test_backup_refuses_without_creating_or_pruning_archives(self):
        self.assert_refused("backup.sh")

    def test_restore_refuses_even_with_confirmation_and_dump_argument(self):
        self.assert_refused("restore.sh", ("existing.dump",))

    def test_both_guards_use_only_literal_diagnostic_and_exit(self):
        for name in ("backup.sh", "restore.sh"):
            active = [line.strip() for line in (SCRIPTS / name).read_text().splitlines()
                      if line.strip() and not line.lstrip().startswith("#")]
            self.assertEqual(len(active), 2, name)
            self.assertTrue(active[0].startswith("printf '%s\\n' 'RETIRED:"), name)
            self.assertTrue(active[0].endswith(" >&2"), name)
            self.assertNotIn("$", active[0], name)
            self.assertNotIn("`", active[0], name)
            self.assertEqual(active[1], "exit 64", name)

    def test_both_guards_have_valid_posix_shell_syntax(self):
        for name in ("backup.sh", "restore.sh"):
            result = subprocess.run(["/bin/sh", "-n", str(SCRIPTS / name)],
                                    capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
