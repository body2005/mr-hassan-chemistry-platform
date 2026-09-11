"""Job Checkpointing, Manifest Persistence, and Resumption Manager."""
from __future__ import annotations
import json, os, time
from typing import Dict, Any, Optional

class JobStateManager:
    """
    Guarantees fault-tolerant restartability.
    If processing fails after 80 minutes of a 2.5-hour lecture,
    resumes immediately from the last completed chunk without reprocessing.
    """
    def __init__(self, job_dir: str, video_path: str, total_chunks: int, config: Dict[str, Any]):
        self.job_dir = os.path.abspath(job_dir)
        self.chunks_dir = os.path.join(self.job_dir, "chunks")
        self.manifest_path = os.path.join(self.job_dir, "manifest.json")
        os.makedirs(self.chunks_dir, exist_ok=True)
        
        self.video_path = video_path
        self.total_chunks = total_chunks
        self.config = config
        
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "video_path": video_path,
                "total_chunks": total_chunks,
                "completed_chunks": [],
                "failed_chunks": [],
                "config": config,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "in_progress"
            }
            self._save()

    def _save(self) -> None:
        self.data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_chunk_completed(self, chunk_id: int) -> bool:
        chunk_file = os.path.join(self.chunks_dir, f"{chunk_id:06d}.json")
        return chunk_id in self.data["completed_chunks"] and os.path.exists(chunk_file)

    def save_chunk_result(self, chunk_id: int, chunk_payload: Dict[str, Any]) -> None:
        chunk_file = os.path.join(self.chunks_dir, f"{chunk_id:06d}.json")
        with open(chunk_file, "w", encoding="utf-8") as f:
            json.dump(chunk_payload, f, ensure_ascii=False, indent=2)
        if chunk_id not in self.data["completed_chunks"]:
            self.data["completed_chunks"].append(chunk_id)
            self.data["completed_chunks"].sort()
        self._save()

    def get_completed_chunk(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        chunk_file = os.path.join(self.chunks_dir, f"{chunk_id:06d}.json")
        if os.path.exists(chunk_file):
            with open(chunk_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def mark_completed(self) -> None:
        self.data["status"] = "completed"
        self._save()
