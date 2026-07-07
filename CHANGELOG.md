# Changelog — ClipMind

All notable changes and implemented features in this project.

---

## [1.0.0] — 2026-07-07

### Release Candidate 1

#### Added
* **Phase 29 — Version 1.0 Release Candidate**:
  * Version-locked Python package dependencies in `requirements.txt`.
  * Configured `.env.example` with upscaling parameters and customized overlays.
  * Added Docker container configs (`Dockerfile`, `docker-compose.yml`) with automated status health checks.
  * Created Linux/macOS bash startup bootstrappers (`start_all.sh`, `start_production.sh`) and Windows production bootstrappers (`start_production.bat`).
  * Created complete release documentation: `docs/configuration_guide.md`, `docs/production_deployment_guide.md`, and `docs/release_checklist.md`.
  * Cleaned up all dead code, unused helper imports, and validated AST parsing trees.
* **Phase 28 — Production Optimization**:
  * Re-architected rendering pipeline to use raw BGR24 frames streamed concurrently from OpenCV to FFmpeg stdin pipes.
  * Reduced video re-encoding passes from **three to two**, completely eliminating temporary AVI writes and saving hundreds of megabytes in I/O disk writes.
  * Hardened resource cleanup, capping cache databases, releasing VideoCapture devices, and reaping FFmpeg process handles in `finally` blocks.
  * Implemented environmental variable `USE_STREAMING_PIPELINE` to toggle comparison benchmarks.
* **Phase 27 — Premium Like Animation & Quality**:
  * Implemented adaptive Like button overlay counts (1, 2, or 3 appearances) based on clip duration thresholds.
  * Unified overlay rendering and audio click mixes under a single validated list ($t \ge 0.5\text{s}$ and $t + t_{\text{dur}} \le \text{duration} - 0.5\text{s}$) to avoid out-of-bounds rendering.
  * Applied $1.5\times$ playhead slowdown via `setpts` filter to extend WebM animation to $2.37\text{s}$ with smooth ease-in, hold, and ease-out.
  * Consolidated all scaling operations to high-quality Lanczos interpolation (`flags=lanczos` in FFmpeg, `cv2.INTER_LANCZOS4` in OpenCV).
  * Auto-scale output resolution dynamically: 4K vertical ($1215 \times 2160$) for source $\ge 4K$, else 1080p vertical ($1080 \times 1920$).
  * Tuned GPU presets (`h264_nvenc`, preset `p7`, VBR HQ, CQ 18) and CPU fallback settings (`libx264`, preset `slow`, CRF 16).
  * Integrated optional AI Upscaling mode (`VIDEO_UPSCALE_MODE`) with Real-ESRGAN validation.
* **Phase 26 — Like Button Overlay & Click Sync**:
  * Integrated custom animated overlays (`assets/animations/like_button.webm`) and transparency keying fallbacks.
  * Synchronized transient audio click triggers (`assets/sfx/like_click.mp3` at 9% volume) with visual click press frames.
* **Phase 25 — Cinematic Music & SFX Layering**:
  * Integrated local audio library matching emotional tones via Gemini analyses.
  * Hardened audio mixing using sidechain compression ducking or flat amix fallback.
