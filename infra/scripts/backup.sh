#!/bin/sh
# Retired MinIO/container-specific entry point. No data or Docker operations.
# Current backup/restore instructions require a reviewed target, ALL-writer
# quiescence and immutable images; never guess these from cwd/environment.
printf '%s\n' 'RETIRED: this legacy backup entry point is disabled; no backup ran and no archives were pruned. Follow docs/PRODUCTION_DOCKER_RUNBOOK.md; for synthetic local QA use scripts/qa/video-storage-drill.ps1.' >&2
exit 64
