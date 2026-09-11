#!/usr/bin/env python3
"""
Production CLI for High-Accuracy Egyptian Arabic Speech-to-Text Pipeline.
Supports long videos (2-3 hours), intelligent chunking, fault-tolerant restartability,
repetition removal, Egyptian Arabic normalization, and multi-format exports (TXT, SRT, VTT, JSON).
"""
from __future__ import annotations
import argparse, os, sys, time, tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from asr_pipeline.audio import extract_16k_mono_audio, get_audio_duration_seconds
from asr_pipeline.chunker import create_intelligent_chunks
from asr_pipeline.deduplication import remove_consecutive_phrase_repetitions, stitch_overlapping_transcripts
from asr_pipeline.normalization import normalize_egyptian_arabic_transcript
from asr_pipeline.state_manager import JobStateManager
from asr_pipeline.exporter import export_all_formats
from asr_pipeline.engine import ASREngine

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Production Egyptian Arabic ASR Pipeline (QwenCleo / Faster-Whisper)"
    )
    parser.add_argument("video_path", help="Path to input video or audio file (MP4, MKV, WAV, etc.)")
    parser.add_argument("--model", default="qwencleo", choices=["qwencleo", "small", "medium", "base"],
                        help="ASR model engine to use (default: qwencleo)")
    parser.add_argument("--mode", default="balanced", choices=["accuracy", "balanced", "speed"],
                        help="Performance mode: accuracy, balanced, or speed (default: balanced)")
    parser.add_argument("--chunk-size", type=float, default=30.0,
                        help="Target chunk duration in seconds (default: 30.0)")
    parser.add_argument("--overlap", type=float, default=2.0,
                        help="Boundary overlap in seconds (default: 2.0)")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda:0"],
                        help="Inference device (default: auto)")
    parser.add_argument("--output", default="./output", help="Output directory for exported transcripts")
    parser.add_argument("--job-dir", default=None, help="Directory for checkpointing and resumption (default: ./job_<video_name>)")
    parser.add_argument("--cpu-threads", type=int, default=8, help="Number of CPU threads for inference (default: 8)")
    
    args = parser.parse_args()
    
    video_path = os.path.abspath(args.video_path)
    if not os.path.exists(video_path):
        print(f"Error: Input file not found: {video_path}")
        sys.exit(1)

    video_name = Path(video_path).stem
    job_dir = args.job_dir or os.path.join(".", f"job_{video_name}")
    output_dir = os.path.abspath(args.output)
    
    print("=" * 75)
    print(" 🎙️  HIGH-ACCURACY EGYPTIAN ARABIC ASR PIPELINE")
    print("=" * 75)
    print(f"Input Video   : {video_path}")
    print(f"Model Engine  : {args.model.upper()} (Mode: {args.mode})")
    print(f"Chunk Target  : {args.chunk_size}s (Overlap: {args.overlap}s)")
    print(f"Output Dir    : {output_dir}")
    print(f"Job State Dir : {job_dir}")
    print("-" * 75)
    
    t_start = time.time()
    
    # 1. Audio Extraction
    temp_wav = os.path.join(job_dir, "extracted_audio_16k.wav")
    if not os.path.exists(temp_wav):
        print("[1/5] Extracting 16kHz mono audio track via FFmpeg...")
        t_extract = time.time()
        extract_16k_mono_audio(video_path, temp_wav)
        print(f"      Audio extracted in {time.time() - t_extract:.2f}s")
    else:
        print("[1/5] Audio track already extracted (cached).")
        
    total_duration = get_audio_duration_seconds(temp_wav)
    print(f"      Total Audio Duration: {total_duration:.2f}s ({total_duration/60.0:.2f} mins / {total_duration/3600.0:.2f} hrs)")
    
    # 2. Intelligent VAD Chunking
    print("[2/5] Performing Voice Activity Detection and Pause-Aware Chunking...")
    chunks = create_intelligent_chunks(
        wav_path=temp_wav,
        target_chunk_duration_sec=args.chunk_size,
        overlap_sec=args.overlap,
        total_audio_duration=total_duration
    )
    print(f"      Generated {len(chunks)} intelligent chunks.")
    
    # 3. State Management & Resumption
    state_mgr = JobStateManager(
        job_dir=job_dir,
        video_path=video_path,
        total_chunks=len(chunks),
        config=vars(args)
    )
    
    completed_count = len(state_mgr.data["completed_chunks"])
    if completed_count > 0:
        print(f"      [RESUME] Found {completed_count}/{len(chunks)} completed chunks. Resuming...")
    
    # 4. Engine Initialization & Inference
    print(f"[3/5] Initializing {args.model.upper()} Engine (Device: {args.device})...")
    engine = ASREngine(
        model_name=args.model,
        device=args.device,
        mode=args.mode,
        cpu_threads=args.cpu_threads
    )
    
    chunk_temp_dir = os.path.join(job_dir, "temp_chunks")
    os.makedirs(chunk_temp_dir, exist_ok=True)
    
    processed_segments = []
    
    print("[4/5] Transcribing Audio Chunks with Checkpointing...")
    for idx, chunk in enumerate(chunks, 1):
        if state_mgr.is_chunk_completed(chunk.chunk_id):
            cached = state_mgr.get_completed_chunk(chunk.chunk_id)
            processed_segments.append(cached)
            continue
            
        chunk_wav = os.path.join(chunk_temp_dir, f"chunk_{chunk.chunk_id:06d}.wav")
        extract_16k_mono_audio(
            media_path=temp_wav,
            output_wav_path=chunk_wav,
            start_sec=chunk.full_start,
            duration_sec=chunk.full_duration
        )
        
        t_chunk = time.time()
        raw_text = engine.transcribe_chunk(chunk_wav)
        chunk_elapsed = time.time() - t_chunk
        
        # Clean text
        clean_text = normalize_egyptian_arabic_transcript(raw_text)
        dedup_text = remove_consecutive_phrase_repetitions(clean_text)
        
        chunk_payload = {
            "chunk_id": chunk.chunk_id,
            "start_time": chunk.start_sec,
            "end_time": chunk.end_sec,
            "time_formatted": f"{int(chunk.start_sec)//60:02d}:{int(chunk.start_sec)%60:02d}",
            "raw_text": raw_text,
            "text": dedup_text,
            "processing_time": round(chunk_elapsed, 2)
        }
        
        state_mgr.save_chunk_result(chunk.chunk_id, chunk_payload)
        processed_segments.append(chunk_payload)
        
        speedup = chunk.full_duration / max(chunk_elapsed, 0.001)
        print(f"      Chunk {idx}/{len(chunks)} [{chunk.start_sec:.1f}s -> {chunk.end_sec:.1f}s]: {dedup_text[:60]}... ({chunk_elapsed:.2f}s, {speedup:.2f}x)")
        
        # Clean temporary chunk wav
        if os.path.exists(chunk_wav):
            try:
                os.remove(chunk_wav)
            except OSError:
                pass

    state_mgr.mark_completed()
    
    # 5. Exporting Transcripts
    print("[5/5] Stitching and Exporting Multi-Format Transcripts...")
    export_metadata = {
        "video_path": video_path,
        "video_duration_seconds": total_duration,
        "model": args.model,
        "mode": args.mode,
        "total_chunks": len(chunks),
        "total_processing_time_seconds": round(time.time() - t_start, 2),
        "realtime_speedup": round(total_duration / max(time.time() - t_start, 0.001), 2)
    }
    
    exported = export_all_formats(
        segments=processed_segments,
        output_dir=output_dir,
        base_filename=video_name,
        metadata=export_metadata
    )
    
    total_time = time.time() - t_start
    overall_speedup = total_duration / max(total_time, 0.001)
    rtf = total_time / max(total_duration, 0.001)
    
    print("=" * 75)
    print(" ✅  TRANSCRIPTION COMPLETE!")
    print("=" * 75)
    print(f"Total Processing Time : {total_time:.2f}s ({total_time/60.0:.2f} mins)")
    print(f"Real-Time Speedup     : {overall_speedup:.2f}x (RTF: {rtf:.3f})")
    print(f"Exported TXT File     : {exported['txt']}")
    print(f"Exported SRT File     : {exported['srt']}")
    print(f"Exported VTT File     : {exported['vtt']}")
    print(f"Exported JSON File    : {exported['json']}")
    print("=" * 75)

if __name__ == "__main__":
    main()
