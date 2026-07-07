import wave
import numpy as np
import os
import subprocess

def analyze_audio_frequencies(wav_path):
    print(f"\nAnalyzing frequencies of wav file: {wav_path}")
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        num_channels = params.nchannels
        sample_width = params.sampwidth
        frame_rate = params.framerate
        num_frames = params.nframes
        
        print(f"Channels: {num_channels}, Sample Width: {sample_width} bytes, Frame Rate: {frame_rate} Hz, Frames: {num_frames}")
        
        # Read frames
        raw_data = w.readframes(num_frames)
        # Convert to numpy array based on sample width (assume 16-bit)
        if sample_width == 2:
            data = np.frombuffer(raw_data, dtype=np.int16)
        elif sample_width == 4:
            data = np.frombuffer(raw_data, dtype=np.int32)
        else:
            print("Unsupported sample width")
            return
            
        # If stereo, take the first channel
        if num_channels > 1:
            data = data[::num_channels]
            
        # Perform Fast Fourier Transform (FFT)
        fft_data = np.abs(np.fft.fft(data))
        freqs = np.fft.fftfreq(len(data), 1.0 / frame_rate)
        
        # Find peaks in positive frequencies
        pos_indices = np.where(freqs > 0)
        pos_freqs = freqs[pos_indices]
        pos_fft = fft_data[pos_indices]
        
        # Get top 5 strongest frequencies
        top_indices = np.argsort(pos_fft)[-10:][::-1]
        print("Top 10 strongest frequencies detected:")
        seen_freqs = set()
        for idx in top_indices:
            freq = pos_freqs[idx]
            amplitude = pos_fft[idx]
            # Round frequency to nearest integer for clarity
            rounded_freq = round(freq)
            if rounded_freq not in seen_freqs:
                print(f"  Frequency: {rounded_freq} Hz (amplitude: {amplitude:.1f})")
                seen_freqs.add(rounded_freq)
                if len(seen_freqs) >= 5:
                    break

if __name__ == "__main__":
    mp4_path = "output/clips/test_mix_id_with_music.mp4"
    wav_path = "scratch/output_audio.wav"
    
    # Extract audio to wav
    print("Extracting audio from MP4 to WAV...")
    cmd = ["ffmpeg", "-y", "-i", mp4_path, "-ac", "1", "-c:a", "pcm_s16le", wav_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    analyze_audio_frequencies(wav_path)
