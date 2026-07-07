# API Documentation — ClipMind v1.0

ClipMind exposes a FastAPI REST backend with Server-Sent Events (SSE) progress streams.

---

## 🔌 API Endpoints

### 1. Submit Video for Curation
- **Route**: `POST /api/analyze`
- **Request Body (JSON)**:
  ```json
  {
    "url": "https://www.youtube.com/watch?v=UF8uR6Z6KLc",
    "gemini_api_key": "your_api_key_here",
    "num_clips": 1,
    "subtitle_style": "kinetic",
    "font_name": "Anton",
    "font_size": 75,
    "creator_preset": "custom",
    "bypass_camera_qa": false
  }
  ```
- **Response (JSON)**:
  ```json
  {
    "job_id": "b0a2c079-c5c7-434a-9ef5-fa5069f984d7"
  }
  ```

---

### 2. Live Job Progress (SSE)
- **Route**: `GET /api/progress/{job_id}`
- **Format**: `text/event-stream`
- **Payload Event Output**:
  ```json
  data: {"status": "clipping", "progress": 65, "message": "Running face tracking QA...", "error": null}
  ```

---

### 3. Retrieve Completed Clips
- **Route**: `GET /api/clips/{job_id}`
- **Response (JSON)**:
  ```json
  {
    "clips": [
      {
        "clip_id": "af4f8527",
        "title": "Why Motivation Beats Everything Else",
        "virality_score": 8.75,
        "duration": 37.5,
        "shorts_title": "Why Motivation Beats Everything Else #Shorts",
        "shorts_description": "Founders must maintain high motivation to face obstacles...",
        "shorts_tags": ["motivation", "startups", "founders"]
      }
    ]
  }
  ```

---

### 4. Serve Video Clip File
- **Route**: `GET /api/video/{job_id}/{clip_filename}`
- **Headers supported**: Range Requests (`bytes=`) for native video player scrub and preview compatibility.
- **Response**: Binary MP4 stream.

---

### 5. Submit Creator Feedback
- **Route**: `POST /api/analytics/feedback`
- **Request Body (JSON)**:
  ```json
  {
    "clip_id": "af4f8527",
    "feedback": "Great"
  }
  ```
- **Response**: `{"status": "success", "message": "Creator feedback recorded successfully."}`
