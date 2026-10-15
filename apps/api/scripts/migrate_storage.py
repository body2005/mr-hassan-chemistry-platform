"""Compatibility entry point for the current private-storage migration.

Knowledge Center was removed. No legacy models are imported and no original
files are deleted. See scripts.migrate_private_storage for explicit arguments.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.migrate_private_storage import main

if __name__ == '__main__':
    main()
