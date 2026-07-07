# Configuration Guide — ClipMind v1.0

This guide explains how to configure environment variables, settings presets, custom visual overlays, and backend options in ClipMind.

---

## ⚙️ Environment Variables Reference

ClipMind uses environment variables (loaded via `.env` or system environment) to drive application setup.

| Variable Name | Default Value | Description | Required in Production |
|---|---|---|---|
| `APP_ENV` | `development` | Environment mode (`development`, `beta`, `production`). | Yes |
| `GEMINI_API_KEY` | (empty) | API Key for Google Gemini LLM curation logic. | Yes (or OpenAI key) |
| `OPENAI_API_KEY` | (empty) | API Key for OpenAI fallback model logic. | No |
| `ANTHROPIC_API_KEY` | (empty) | API Key for Anthropic fallback model logic. | No |
| `YOUTUBE_CLIENT_ID` | (empty) | OAuth Client ID for YouTube Publishing API. | Yes |
| `YOUTUBE_CLIENT_SECRET` | (empty)| OAuth Client Secret for YouTube Publishing API. | Yes |
| `YOUTUBE_REDIRECT_URI` | (empty) | OAuth Redirect callback override URL. | No |
| `ENCRYPTION_KEY` | (empty) | 32-byte Fernet key for encrypting OAuth tokens. | Yes |
| `ALLOWED_ORIGINS` | (local urls) | Comma-separated list of permitted CORS origins. | Yes |
| `ENFORCE_HTTPS` | `false` | Redirect HTTP requests and secure cookies behind reverse proxies. | Yes (in prod) |
| `DATABASE_URL` | sqlite URL | SQLite path or PostgreSQL connection string. | Yes |
| `MUSIC_ENABLED` | `true` | Globally enable/disable background music layering. | No |
| `MUSIC_LIBRARY_PATH` | `assets/music` | Relative path to local audio track directories. | No |
| `VIDEO_UPSCALE_MODE` | `Off` | Optional upscaling (`Off`, `2x AI Upscale`, `4K AI Upscale`, `8K AI Upscale`). | No |
| `DEFAULT_MUSIC_VOLUME` | `15` | Fallback percentage volume for background tracks. | No |
| `RANDOMIZE_TRACKS` | `true` | Shuffle audio tracks to avoid repeated music choices. | No |

---

## 🎨 Custom Like Overlay & Color Keying

To customize the visual Like button overlay animation, place your files inside the `assets/animations/` folder. ClipMind prioritizes assets in this order:
1. `like_button.webm` (WebM with alpha transparency - recommended)
2. `like_button.mp4` (MP4, uses colorkey transparency fallback)
3. `like_button.gif` (GIF, transparent or solid color fallback)

### Colorkey Tuning (for MP4/solid assets)
If your custom asset does not contain a native alpha/transparency channel, configure the following `.env` parameters to key out backgrounds:
* `LIKE_OVERLAY_KEY_COLOR`: Set the target background color (e.g. `white`, `black`, `green`, or hex `0xFFFFFF`).
* `LIKE_OVERLAY_SIMILARITY`: Similarity tolerance ($0.01$ matches only the exact color, $1.0$ keys out all colors).
* `LIKE_OVERLAY_BLEND`: Boundary blending/feathering ($0.0$ is a hard boundary, $0.1$ is soft).
