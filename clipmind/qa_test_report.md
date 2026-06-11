# QA Test Report: YouTube AI Clip Extractor

## 1. Executive Summary

- **Status of Previous Issue (Subscriptable TypeError):** **RESOLVED**. The transcript retrieval logic in `backend/analyzer.py` successfully accesses properties (`entry.start` and `entry.text`) using dot notation. Independent testing via `test_transcript.py` and the main API verification confirm transcript extraction works without errors.
- **Current Pipeline Status:** **FAILED**. The overall video analysis and clipping pipeline fails during the analysis step due to a model lookup error from the Gemini API.
- **New Issue Identified:** `404 models/gemini-1.5-flash is not found for API version v1beta`.

---

## 2. Issue Details (New Failure)

When running the pipeline via `test_api.py`, the backend begins processing but terminates at step 2 (Analysis) with the following exception:

```
[fetching_transcript] Progress: 10% - Extracting video ID and fetching transcript from YouTube...
[failed] Progress: 100% - Error: 404 models/gemini-1.5-flash is not found for API version v1beta, or is not supported for generateContent. Call ModelService.ListModels to see the list of available models and their supported methods.
Pipeline error reported: 404 models/gemini-1.5-flash is not found for API version v1beta, or is not supported for generateContent. Call ModelService.ListModels to see the list of available models and their supported methods.
```

- **Affected File:** `backend/analyzer.py`
- **Affected Function:** `analyze_with_gemini(transcript: str, api_key: str)`
- **Affected Line:** 84
- **Failure Cause:** Model request for `'gemini-1.5-flash'` returns a `404 Not Found` response.

---

## 3. Root Cause Analysis

A programmatic inspection of the available models under the configured `GEMINI_API_KEY` was conducted by executing:
```python
import google.generativeai as genai
print([m.name for m in genai.list_models()])
```

The call returned the list of available models, which includes newer models but **excludes** the older `gemini-1.5-flash`:

### Supported Models Under Configured API Key
- `models/gemini-2.0-flash`
- `models/gemini-2.5-flash`
- `models/gemini-3.5-flash`
- `models/gemini-2.0-flash-lite`
- `models/gemini-3.1-flash-lite`
- `models/gemini-2.5-pro`
- `models/gemini-3-pro-preview`
- `models/gemini-3.1-pro-preview`
- ... (and other newer preview/specialized models)

Because `gemini-1.5-flash` has been deprecated or is unavailable for this API key, requesting it via the Google Generative AI Python SDK results in a 404 error from the Google API server.

---

## 4. How to Fix

To fix this issue, update the model configuration in `backend/analyzer.py` to use a supported model available under the API key (e.g., `gemini-2.0-flash` or `gemini-2.5-flash`).

### Proposed Code Diff

```diff
diff --git a/backend/analyzer.py b/backend/analyzer.py
index a1b2c3d..e4f5g6h 100644
--- a/backend/analyzer.py
+++ b/backend/analyzer.py
@@ -81,7 +81,7 @@ def analyze_with_gemini(transcript: str, api_key: str) -> list:
 ]
 """
     
-    model = genai.GenerativeModel('gemini-1.5-flash')
+    model = genai.GenerativeModel('gemini-2.5-flash')
     response = model.generate_content(
         prompt,
         generation_config={"response_mime_type": "application/json"}
```

---

## 5. Verification Steps

1. Modify `backend/analyzer.py` line 84 to use an active model name like `gemini-2.5-flash`.
2. Run `d:\Desktop\LLM\backend\venv\Scripts\python.exe test_api.py` to ensure:
   - Transcript fetches successfully.
   - Analysis JSON is returned and parsed.
   - Video download finishes successfully.
   - Highlights are extracted and saved using ffmpeg.
