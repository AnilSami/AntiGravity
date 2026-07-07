# Troubleshooting Guide — ClipMind v1.0

Solve common issues encountered during local installation or deployment.

---

## ❌ FFmpeg Not Found Error

- **Symptom**: `ffmpeg is not installed or not in PATH on this server. Video clipping is disabled.`
- **Resolution**:
  - Verify FFmpeg is installed by typing `ffmpeg -version` in your terminal.
  - If installed but not found, ensure the path to the `bin` directory of your FFmpeg installation is added to your environment variable `PATH`.
  - Restart your command prompt or VS Code to reload PATH.

---

## 🔒 SQLite Database Locked Errors

- **Symptom**: `sqlite3.OperationalError: database is locked`
- **Explanation**: SQLite permits concurrent reads but locks the entire database file during writes. Multiple parallel writes or unclosed cursor handles can cause this error.
- **Resolution**:
  - We have hardened database operations by enabling `WAL (Write-Ahead Logging)` mode dynamically during connection retrieval.
  - Ensure you close all SQLite DB browsers or external editors viewing `analytics.db` during pipeline runs.

---

## 🔑 Gemini API Key Invalid or Missing

- **Symptom**: `API Key is missing...`
- **Resolution**:
  - Create a `.env` file inside the `backend/` directory.
  - Ensure the variable name is exactly `GEMINI_API_KEY` (all capitals).
  - Do not use quotes around the key unless it contains special shell characters.

---

## 🌐 Browser CORS / null Origin Blocked

- **Symptom**: `Fetch API cannot load http://localhost:8000/api/... due to CORS origin null blocking.`
- **Explanation**: Double-clicking `frontend/index.html` to open it in a browser loads it via the `file://` protocol, which sends a null `Origin` header.
- **Resolution**:
  - We have appended `"null"` to the default allowed CORS origins in `config.py`.
  - Ensure `ALLOWED_ORIGINS` in your `.env` includes `null` or is left default.

---

## 🏎️ NVENC GOP Length Errors

- **Symptom**: `InitializeEncoder failed: Gop Length should be greater than B frames + 1`
- **Explanation**: Under certain GPU driver profiles, invoking NVENC with preset `p7` and GOP length of `1` (which is used for intermediate video frames seeking) violates driver constraints.
- **Resolution**:
  - We have resolved this by forcing the intermediate crop segments to use the fast `p1` preset for GPU and `ultrafast` for CPU, while keeping the slow/p7 preset for the final merged video compile.

---

## ⚙️ Real-ESRGAN Upscaler Warning

- **Symptom**: `VIDEO_UPSCALE_MODE is set to X, but no genuine AI super-resolution engine was found.`
- **Explanation**: The optional AI upscaler is configured but the binary `realesrgan-ncnn-vulkan` or `realesrgan` is not found on the system `PATH`.
- **Resolution**:
  - This is a non-fatal warning. The pipeline will automatically bypass AI upscaling and output the high-quality original vertical clip to preserve quality instead of applying fake stretching. Add the upscaler binary directory to your system `PATH` to resolve the warning.

