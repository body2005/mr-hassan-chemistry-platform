# Docker Desktop recovery — 5 October 2026

The local engine could not start. Docker Desktop 4.93.0 logged:
`initializing Secrets Engine ... rename engine.sock ... engine.sock.stale:
The file cannot be accessed by the system`.

Read-only checks found no Docker/backend/vpnkit processes. The exact directory
`C:\Users\body\AppData\Local\docker-secrets-engine` was an ordinary directory,
containing only `engine.sock`, 0 bytes, Archive + ReparsePoint. This is outside
the Docker container/image/volume data directory. No factory reset, volume
deletion, reinstallation, WSL shutdown or machine restart was performed.

A [matching user report in Docker's issue tracker](https://github.com/docker/for-win/issues/15064)
describes preserving the parent directory under another name because operating
on the orphan socket itself fails. This is a reported workaround, not an
official guarantee for every host.

After rechecking the exact resolved source, absence of Docker processes, the
single zero-byte entry and absence of the destination, native PowerShell
`Rename-Item -LiteralPath` preserved that directory as
`docker-secrets-engine.stale-20261005-1316`. Docker Desktop was launched with
`Start-Process -WindowStyle Hidden`. Both commands returned Exit 0. The old
directory was NOT deleted; no application secrets or user documents were moved.

Verification on this machine:

- `docker version --format '{{.Server.Version}}'`: Exit 0, Engine 29.8.1.
- Existing `chemistryaudit2` and `chemistryprodlocal` containers reappeared;
  no replacement volumes were created for this repair.
- `verify-runtime-source.ps1`: Exit 0; API72, encoder72, web89 files/config,
  zero mismatches. Current web/API/encoder image IDs remain those in the role
  closure report.
- `git diff --check`: Exit 0. No test result from 4 October was relabeled as a
  new 5 October run. New experiments are reported separately.

Do not blindly rename directories with additional entries, active Docker
processes or different ownership. Diagnose those cases before mutation.
