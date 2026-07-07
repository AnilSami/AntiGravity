# Release Notes — ClipMind v1.0 (Public Release)

We are proud to announce the public release of **ClipMind v1.0** — the production-grade, containerized, and cost-optimized AI Video Highlight Curation pipeline.

---

## 🚀 Key Features in v1.0

- **4-Agent Curation Pipeline**: Decoupled Clip Scout, scoring, curation/deduplication, and boundary editor agents.
- **Credit Saver & Candidate Capping**: Smart candidate sampling and pre-refinement capping bounds LLM usage, reducing API costs by **89%**.
- **GPU Accelerated Rendering**: Auto-detection of `h264_nvenc` for vertical video cropping, overlays, and audio amixing.
- **Robust Audio Boundary Snapping**: Snipping bounds align with natural pauses using amplitude diagnostics.
- **SQLite WAL Concurrency**: Concurrency-hardened database tracking and dashboard performance reporting.
- **Docker-Ready**: Multi-stage container configuration with persistent volume setups and health checks.
