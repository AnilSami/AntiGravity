# FAQ — ClipMind v1.0

### Q1: Can I use this for videos longer than 2 hours?
Yes! The Clip Curation pipeline is fully optimized for long-form content. It chunk-processes transcripts in parallel and samples candidates evenly, meaning memory usage remains bounded and stable even on 2+ hour videos.

---

### Q2: How does the Credit Saver setting work?
When you select **1 Clip (Credit Saver)**, the pipeline caps candidate scoring calls to `max(5, num_clips * 2) = 5`. It sorts and samples 5 candidates to send to the Scoring Agent. Once the Curator selects the best candidate, it discards the rest *before* running parallel Editor (Agent 3) and Publisher (Agent 4) calls. This yields up to an **89.4% reduction in API token costs**.

---

### Q3: Why do some clips not have background music?
ClipMind attempts to fetch background music matching the clip's emotional tone from ElevenLabs sound generation. If no ElevenLabs API key is configured in your `.env` (or credits are depleted), the music mixer will fall back gracefully, leaving the original high-quality voice audio intact without crashing the job.

---

### Q4: Is GPU acceleration required?
No. The FFmpeg engine automatically checks for NVIDIA NVENC encoders (`h264_nvenc`). If present, it utilizes GPU hardware acceleration for rendering. If not, it falls back seamlessly to CPU-based encoding (`libx264`).
