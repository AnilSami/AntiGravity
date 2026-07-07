# benchmark_whisper.py
import os
import sys
import time
import psutil
import json

# Adjust path to find analyzer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyzer import transcribe_audio_whisper, LocalTranscriptSnippet

def get_gpu_memory():
    try:
        import torch
        if torch.cuda.is_available():
            # Returns in megabytes
            return torch.cuda.memory_allocated() / (1024 * 1024), torch.cuda.get_device_name(0)
    except Exception:
        pass
    return 0.0, "N/A"

def get_process_memory():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024) # MB

def run_benchmark():
    video_path = os.path.join(os.path.dirname(__file__), "benchmark_audio.mp3")
    if not os.path.exists(video_path):
        print(f"Error: benchmark audio not found at {video_path}")
        sys.exit(1)
        
    models = ["tiny", "base", "small"]
    results = {}
    
    print("==================================================")
    print("  CLIPMIND WHISPER BENCHMARK RUNNER")
    print("==================================================")
    print(f"Input Video: {video_path}")
    
    for model_name in models:
        print(f"\nBenchmarking model: {model_name}...")
        
        # Initial memory footprint
        mem_before = get_process_memory()
        gpu_before, gpu_name = get_gpu_memory()
        
        start_time = time.time()
        
        snippets = []
        error = None
        try:
            snippets = transcribe_audio_whisper(video_path, model_size=model_name)
        except Exception as e:
            error = str(e)
            print(f"  [ERROR] Model run failed: {e}")
            
        elapsed = time.time() - start_time
        
        # Peak memory footprint
        mem_after = get_process_memory()
        gpu_after, _ = get_gpu_memory()
        
        mem_used = max(0.0, mem_after - mem_before)
        gpu_used = max(0.0, gpu_after - gpu_before)
        
        results[model_name] = {
            "status": "success" if error is None else "failed",
            "elapsed_seconds": round(elapsed, 2),
            "memory_used_mb": round(mem_used, 2),
            "gpu_used_mb": round(gpu_used, 2),
            "gpu_name": gpu_name,
            "segment_count": len(snippets),
            "first_few_text": " | ".join([s.text for s in snippets[:3]]) if snippets else "",
            "error": error
        }
        
        print(f"  Status: {results[model_name]['status']}")
        print(f"  Elapsed: {results[model_name]['elapsed_seconds']}s")
        print(f"  Segments: {results[model_name]['segment_count']}")
        print(f"  Memory increase: {results[model_name]['memory_used_mb']} MB")
        print(f"  GPU memory increase: {results[model_name]['gpu_used_mb']} MB")
        
    # Write to a JSON file
    output_path = os.path.join(os.path.dirname(__file__), "..", "scratch", "whisper_benchmark_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print("\nBenchmark complete. Saved results to scratch/whisper_benchmark_results.json")

if __name__ == "__main__":
    run_benchmark()
