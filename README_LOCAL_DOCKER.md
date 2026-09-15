# Local Production-Like Docker Environment

This environment provides an isolated, production-like multi-container environment for testing and verifying the Chemistry Platform on Windows using PowerShell.

## Architecture & Services
1. **`web`**: Production Frontend built with Vite, served by Nginx on `http://localhost:8080`.
2. **`api`**: FastAPI Web API running on `http://localhost:8000`. Heavy OCR and parsing are deferred to the Celery worker.
3. **`worker`**: Dedicated Celery worker for OCR, document ingestion, and assessment extraction.
4. **`postgres`**: PostgreSQL 16 with `pgvector` extension.
5. **`redis`**: Redis 7 broker & results with `maxmemory 256mb` and `noeviction`.
6. **`minio`**: S3-compatible local object storage (port 9000 S3 API, port 9001 console).
7. **`minio-init`**: Automatic one-shot bucket provisioner for `chemistry-storage`.

## Resource Limits
- **API**: 1 GB RAM, 1 CPU
- **Worker**: 2 GB RAM, 2 CPUs (concurrency=1, prefetch-multiplier=1, max-tasks-per-child=1)
- **PostgreSQL**: 1 GB RAM
- **Redis**: 256 MB RAM
- **MinIO**: 512 MB RAM
- **Frontend**: 512 MB RAM

## PowerShell Scripts
Run these scripts from the repository root in PowerShell:

### 1. Start Environment
```powershell
.\scripts\docker-up.ps1
```

### 2. View Logs
```powershell
.\scripts\docker-logs.ps1
# Or stream specific service logs:
.\scripts\docker-logs.ps1 -Service worker
```

### 3. Run Automated Tests Inside Docker
```powershell
.\scripts\docker-test.ps1
```

### 4. Stop Environment (Preserving Data Volumes)
```powershell
.\scripts\docker-down.ps1
```

> **Caution:** Do NOT use `docker compose down -v` unless you intentionally want to delete all database records and storage buckets.
