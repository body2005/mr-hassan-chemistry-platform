"""Unified ASR Engine: QwenCleo-ASR with Faster-Whisper Fallback."""
from __future__ import annotations
import os, sys, time, torch
from typing import Dict, Any, List, Optional

class ASREngine:
    def __init__(
        self,
        model_name: str = "qwencleo",
        device: str = "auto",
        mode: str = "balanced",
        cpu_threads: int = 8
    ):
        self.model_name = model_name.lower()
        self.mode = mode
        self.cpu_threads = cpu_threads
        
        if device == "auto":
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        if self.device == "cpu":
            torch.set_num_threads(self.cpu_threads)

        if "qwencleo" in self.model_name:
            try:
                from qwencleo_asr import QwenCleoASR
                dtype = "bfloat16" if self.device.startswith("cuda") else "float32"
                self.model = QwenCleoASR(
                    device=self.device,
                    dtype=dtype,
                    quiet=True
                )
                self.engine_type = "qwencleo"
            except Exception as e:
                print(f"[ASREngine] Warning: QwenCleoASR init failed ({e}). Falling back to Faster-Whisper.")
                self._load_faster_whisper("small")
        else:
            self._load_faster_whisper(self.model_name)

    def _load_faster_whisper(self, model_size: str) -> None:
        from faster_whisper import WhisperModel
        compute_type = "float16" if self.device.startswith("cuda") else "int8"
        self.model = WhisperModel(
            model_size,
            device=self.device if self.device.startswith("cuda") else "cpu",
            compute_type=compute_type,
            cpu_threads=self.cpu_threads
        )
        self.engine_type = "faster_whisper"

    def transcribe_chunk(self, audio_chunk_path: str, prompt: Optional[str] = None) -> str:
        if self.engine_type == "qwencleo":
            res = self.model.transcribe(audio_chunk_path)
            return res.text.strip() if hasattr(res, "text") else str(res).strip()
        else:
            prompt_str = prompt or (
                "شرح منهج الجيولوجيا والجيوفيزياء، التراكيب الجيولوجية الأولية والتكتونية، "
                "الطيات والفوالق والصدوع، الفالق العادي والمعكوس، الحائط العلوي والسفلي، "
                "البترول والغاز الطبيعي والمياه الجوفية، أسطح عدم التوافق."
            )
            segs, _ = self.model.transcribe(
                audio_chunk_path,
                language="ar",
                initial_prompt=prompt_str,
                beam_size=5 if self.mode == "accuracy" else (3 if self.mode == "balanced" else 1),
                temperature=0.0
            )
            return " ".join(s.text.strip() for s in segs)
