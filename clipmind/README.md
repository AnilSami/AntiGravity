# ClipMind: YouTube Smart Clip Extractor

ClipMind is a modern web application that accepts a YouTube link, retrieves its transcript, analyzes the content using **Gemini 2.5 Flash**, and automatically extracts key highlight clips (under 60 seconds each) that represent peak interest or important insights. It then crops them to a 9:16 portrait ratio using OpenCV face-tracking and burns subtitles in real-time.

## 🌟 Features

- **Dynamic Face-Tracking Crop**: Automatically detects the speaker's face and centers the video frame dynamically using OpenCV Haar Cascades, resulting in a perfect 9:16 portrait format for YouTube Shorts, TikTok, or Instagram Reels.
- **Perfect Audio-Video Synchronization**: Intermediate segments are transcoded with intra-frame-only H.264 settings (`-g 1 -bf 0`) to eliminate OpenCV decoding lag/shift and ensure frame-perfect A/V alignment.
- **Dazzling Glassmorphic Sunset UI**: A beautiful, responsive light sky-blue background gradient with slowly drifting white clouds, a sunset-orange setting sun, and frosted glass container cards.
- **YouTube Shorts SEO Metadata**: Automatically generates optimized titles, description descriptions, and hashtag tags, which can be copied directly with a single click.
- **Fast, Precise Seeking**: Employs FFmpeg input seeking (`-ss` before `-i`) to seek and cut segments instantly.

---

## 📸 User Interface Mockup

Below is a mockup of the clean, vibrant sky-blue user interface with frosted glass cards:

![ClipMind UI Screenshot](clipmind_ui_screenshot.png)

---

## 🛠️ Architecture

- **Frontend**: Vanilla HTML5, CSS3 (frosted glassmorphism, responsive grids, and transitions), and modern JavaScript (EventSource client for Server-Sent Events progress tracking).
- **Backend**: FastAPI (Python), utilizing `yt-dlp` for video downloading and `ffmpeg` for precise video trimming.
- **AI Engine**: Google Gemini 2.5 Flash via the official `google-generativeai` SDK.

---

## 📋 System Requirements

To run this application, you need:

1. **Python 3.8+**
2. **ffmpeg** (Required for clipping and audio/video merge)

### How to Install `ffmpeg` on Windows:
- Open **PowerShell** as Administrator and run:
  ```powershell
  winget install ffmpeg
  ```
- Verify installation:
  ```cmd
  ffmpeg -version
  ```

---

## 🚀 Quick Start (Windows)

1. **Start the Backend Server**:
   - Double-click **`start_all.bat`** in the `clipmind` directory.
   - This script creates a virtual environment (`venv`), installs all required dependencies (FastAPI, yt-dlp, google-generativeai, opencv-python, pillow, etc.), and starts the Uvicorn server on `http://localhost:8000`.

2. **Open the App**:
   - Locate and double-click `frontend/index.html` to open it in your browser.

3. **Extract Highlights**:
   - Paste a YouTube URL.
   - Enter your Gemini API Key.
   - Click **Extract Clips ✨** and watch the real-time progress stream!

---

## 📁 Project Structure & Code Explanations

```
clipmind/
│
├── backend/
│   ├── .env                 # API Credentials
│   ├── requirements.txt     # Python Dependencies
│   ├── main.py              # FastAPI Application & SSE endpoints
│   ├── analyzer.py          # YouTube Transcript Fetch & Gemini Prompt
│   ├── clipper.py           # yt-dlp, OpenCV face-tracking, and ffmpeg clipping
│   └── job_manager.py       # Asynchronous Pipeline coordinator & ASS generator
│
├── frontend/
│   ├── index.html           # Web app UI with animated background blobs
│   ├── style.css            # Premium Sky-Blue & Sunset Glassmorphism styling
│   └── app.js               # Frontend controller & EventSource SSE client
│
├── start_all.bat            # Automated Windows Startup batch script
├── clipmind_ui_screenshot.png # UI Screenshot
└── README.md                # Project documentation
```

### Key Modules:
- **`backend/clipper.py`**: Handles video downloading and clipping. It uses `get_shot_crop_offsets` to detect shot boundaries and analyze speaker facial positions to center the crop box. It then runs FFmpeg to merge the cropped video with the original audio and burn subtitles.
- **`backend/analyzer.py`**: Pulls the video transcripts and invokes the Gemini API to detect key highlight segments (keeping clips strictly between 25-58 seconds).
- **`backend/job_manager.py`**: Manages backend job states and creates dynamic `.ass` subtitle files with word-by-word highlighted text and custom emojis.
- **`frontend/style.css`**: Provides a premium, light sky-blue theme with frosted glass containers, floating clouds, and sunset-orange accents.

---

Created by **Anil Babu Samineni**.
