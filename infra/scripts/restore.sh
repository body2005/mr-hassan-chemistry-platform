#!/bin/sh
# Retired destructive restore entry point. Existing databases are never targets.
# Restore only into NEW stores and verify every row/object as in the runbook.
printf '%s\n' 'RETIRED: this legacy restore entry point is disabled; no database was dropped or restored. Follow docs/PRODUCTION_DOCKER_RUNBOOK.md; for synthetic local QA use scripts/qa/video-storage-drill.ps1.' >&2
exit 64
