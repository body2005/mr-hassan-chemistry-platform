"""
🚀 Google Colab / Kaggle One-Click QwenCleo-ASR GPU Transcription Script
Run this script on a free T4 / V100 / A100 GPU instance to transcribe 2.5-hour videos in ~25-30 minutes.

Prerequisites:
  !pip install -q qwencleo-asr ffmpeg-python soundfile jiwer tqdm
"""
import os, sys, time, json
import torch
from pathlib import Path

# Verify CUDA GPU acceleration
assert torch.cuda.is_available(), "CUDA GPU is required! Enable GPU accelerator in Colab: Runtime > Change runtime type > T4 GPU"
print(f"🔥 Active GPU: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB VRAM)")

from qwencleo_asr import QwenCleoASR

def transcribe_long_video_colab(
    video_path: str,
    chunk_size_sec: float = 30.0,
    overlap_sec: float = 2.0,
    output_dir: str = "./transcripts_colab"
):
    os.makedirs(output_dir, exist_ok=True)
    video_name = Path(video_path).stem
    
    print(f"🚀 Loading QwenCleo-ASR on {torch.cuda.get_device_name(0)} (bfloat16)...")
    t_load = time.time()
    asr = QwenCleoASR(
        model_id="mohammedaly22/QwenCleo-ASR",
        device="cuda:0",
        dtype="bfloat16",
        quiet=False
    )
    print(f"✅ Model loaded in {time.time() - t_load:.2f}s")
    
    # Extract audio
    wav_path = f"/tmp/{video_name}_16k.wav"
    print(f"🎵 Extracting audio to {wav_path}...")
    os.system(f"ffmpeg -y -i \"{video_path}\" -vn -acodec pcm_s16le -ar 16000 -ac 1 \"{wav_path}\" -loglevel error")
    
    # Transcribe
    print(f"🎙️ Starting QwenCleo-ASR inference...")
    t0 = time.time()
    result = asr.transcribe(wav_path)
    elapsed = time.time() - t0
    
    txt_out = os.path.join(output_dir, f"{video_name}.txt")
    with open(txt_out, "w", encoding="utf-8") as f:
        f.write(result.text)
        
    print("=" * 60)
    print(f"✅ Transcription Complete in {elapsed:.2f}s ({elapsed/60.0:.2f} mins)")
    print(f"📄 Output saved to: {txt_out}")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        transcribe_long_video_colab(sys.argv[1])
    else:
        print("Usage: python colab_qwencleo_pipeline.py <video_path>")
