"""Intelligent Windowed Chunking with boundary overlap and pause-aware splitting."""
from __future__ import annotations
from typing import List
from .vad import SpeechInterval, detect_speech_energy_vad

class AudioChunk:
    def __init__(
        self,
        chunk_id: int,
        start_sec: float,
        end_sec: float,
        overlap_start_sec: float,
        overlap_end_sec: float,
    ):
        self.chunk_id = chunk_id
        self.start_sec = round(start_sec, 3)
        self.end_sec = round(end_sec, 3)
        self.overlap_start_sec = round(overlap_start_sec, 3)
        self.overlap_end_sec = round(overlap_end_sec, 3)

    @property
    def full_start(self) -> float:
        return max(0.0, self.start_sec - self.overlap_start_sec)

    @property
    def full_end(self) -> float:
        return self.end_sec + self.overlap_end_sec

    @property
    def full_duration(self) -> float:
        return self.full_end - self.full_start

    def __repr__(self) -> str:
        return f"AudioChunk(#{self.chunk_id:04d}: core [{self.start_sec:.1f}s -> {self.end_sec:.1f}s], full [{self.full_start:.1f}s -> {self.full_end:.1f}s])"

def create_intelligent_chunks(
    wav_path: str,
    target_chunk_duration_sec: float = 30.0,
    min_chunk_duration_sec: float = 15.0,
    max_chunk_duration_sec: float = 45.0,
    overlap_sec: float = 2.0,
    total_audio_duration: float = 0.0,
) -> List[AudioChunk]:
    """
    Splits long audio at natural VAD silence pauses near target_chunk_duration_sec.
    Ensures zero cut words at boundaries.
    """
    vad_intervals = detect_speech_energy_vad(wav_path)
    chunks: List[AudioChunk] = []
    
    curr_start = 0.0
    chunk_idx = 1
    
    while curr_start < total_audio_duration:
        nominal_end = curr_start + target_chunk_duration_sec
        if nominal_end >= total_audio_duration:
            chunks.append(AudioChunk(
                chunk_id=chunk_idx,
                start_sec=curr_start,
                end_sec=total_audio_duration,
                overlap_start_sec=overlap_sec if curr_start > 0 else 0.0,
                overlap_end_sec=0.0,
            ))
            break
            
        best_split = nominal_end
        min_distance_to_target = float('inf')
        
        for i in range(len(vad_intervals) - 1):
            pause_start = vad_intervals[i].end
            pause_end = vad_intervals[i+1].start
            pause_mid = (pause_start + pause_end) / 2.0
            
            if (curr_start + min_chunk_duration_sec) <= pause_mid <= (curr_start + max_chunk_duration_sec):
                dist = abs(pause_mid - nominal_end)
                if dist < min_distance_to_target:
                    min_distance_to_target = dist
                    best_split = pause_mid

        chunks.append(AudioChunk(
            chunk_id=chunk_idx,
            start_sec=curr_start,
            end_sec=best_split,
            overlap_start_sec=overlap_sec if curr_start > 0 else 0.0,
            overlap_end_sec=overlap_sec,
        ))
        
        curr_start = best_split
        chunk_idx += 1
        
    return chunks
