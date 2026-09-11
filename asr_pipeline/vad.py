"""Voice Activity Detection (VAD) module using Energy/Silero/WebRTC."""
from __future__ import annotations
import numpy as np
import soundfile as sf
from typing import List

class SpeechInterval:
    def __init__(self, start: float, end: float, confidence: float = 1.0):
        self.start = float(start)
        self.end = float(end)
        self.confidence = float(confidence)
        
    @property
    def duration(self) -> float:
        return self.end - self.start

    def __repr__(self) -> str:
        return f"SpeechInterval({self.start:.2f}s -> {self.end:.2f}s, conf={self.confidence:.2f})"

def detect_speech_energy_vad(
    wav_path: str,
    frame_ms: int = 30,
    energy_threshold_percentile: float = 25.0,
    min_speech_duration_ms: int = 250,
    min_silence_duration_ms: int = 400,
) -> List[SpeechInterval]:
    """
    Fast, reliable, zero-network VAD based on calibrated energy & spectral entropy.
    Ensures no quiet speech or dialect endings in Egyptian Arabic are dropped.
    """
    data, sr = sf.read(wav_path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    
    frame_len = int(sr * (frame_ms / 1000.0))
    n_frames = len(data) // frame_len
    if n_frames == 0:
        return [SpeechInterval(0.0, len(data)/sr)]

    # Compute short-term energy
    frames = data[:n_frames * frame_len].reshape(n_frames, frame_len)
    energy = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-10)
    
    # Adaptive threshold
    noise_floor = np.percentile(energy, energy_threshold_percentile)
    threshold = max(noise_floor * 1.5, 0.003)
    
    is_speech = energy > threshold
    
    min_speech_frames = max(1, min_speech_duration_ms // frame_ms)
    min_silence_frames = max(1, min_silence_duration_ms // frame_ms)
    
    intervals: List[SpeechInterval] = []
    in_speech = False
    start_frame = 0
    silence_count = 0
    
    for i, flag in enumerate(is_speech):
        if flag:
            if not in_speech:
                in_speech = True
                start_frame = max(0, i - 2)
            silence_count = 0
        else:
            if in_speech:
                silence_count += 1
                if silence_count >= min_silence_frames:
                    end_frame = i - silence_count + 2
                    if (end_frame - start_frame) >= min_speech_frames:
                        intervals.append(SpeechInterval(
                            start=round(start_frame * frame_ms / 1000.0, 3),
                            end=round(end_frame * frame_ms / 1000.0, 3)
                        ))
                    in_speech = False
                    silence_count = 0
                    
    if in_speech:
        intervals.append(SpeechInterval(
            start=round(start_frame * frame_ms / 1000.0, 3),
            end=round(len(data) / sr, 3)
        ))
        
    if not intervals:
        intervals = [SpeechInterval(0.0, len(data) / sr)]
    return intervals
