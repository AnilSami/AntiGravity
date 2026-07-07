# Installation Guide — ClipMind v1.0

Follow this guide to install ClipMind on your local machine or server.

---

## 📋 Prerequisites

Ensure you have the following software installed:
1. **Python 3.10+**: Download from [python.org](https://www.python.org/downloads/).
2. **FFmpeg**: Required for video segment clipping, audio analysis, and subtitle rendering.
   - **Windows**: Install via scoop (`scoop install ffmpeg`) or download from [Gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add it to your System `PATH`.
   - **macOS**: Install via Homebrew: `brew install ffmpeg`
   - **Linux**: Install via apt: `sudo apt-get install -y ffmpeg`
3. **Google Chrome / Chromium**: (Optional) For visual analytics components.

---

## 🛠️ Step-by-Step Local Installation

### Step 1: Clone the Repository
```bash
git clone https://github.com/AnilSami/AntiGravity.git
cd AntiGravity
```

### Step 2: Set Up Python Virtual Environment
Navigate into the backend directory and create a virtual environment:
```bash
cd backend
python -m venv venv
```

Activate the virtual environment:
- **Windows**:
  ```cmd
  venv\Scripts\activate
  ```
- **macOS / Linux**:
  ```bash
  source venv/bin/activate
  ```

### Step 3: Install Backend Dependencies
Install python packages from `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuration Setup

1. Copy `.env.example` in the root folder into the `backend/` folder and rename it to `.env`:
   ```bash
   cp ../.env.example .env
   ```
2. Open `.env` and fill in the required keys:
   - `GEMINI_API_KEY`: Your Google Gemini API Key.
   - `ENCRYPTION_KEY`: Fernet key for YouTube credentials encryption. (Auto-generated in development if empty, but MUST be pre-set in production).
     - Generate a key with:
       ```bash
       python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
       ```
