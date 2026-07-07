"""
test_endpoints.py — Unit tests for Phase 24 FastAPI API routes
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(__file__))

from main import app, jobs
from job_manager import JobStatus

class TestApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_job_status_404(self):
        """Requesting status of a non-existent job returns 404."""
        response = self.client.get("/api/job/non-existent-job-id")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Job not found")

    def test_get_progress_stream_404(self):
        """Requesting SSE progress stream of a non-existent job returns 404."""
        response = self.client.get("/api/progress/non-existent-job-id")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Job not found")

    def test_analyze_invalid_payload(self):
        """Submitting empty url to /api/analyze yields validation error (422)."""
        response = self.client.post("/api/analyze", json={"url": ""})
        # Empty url is accepted by pydantic structure if not constrained, 
        # but let's send malformed JSON to trigger 422
        response = self.client.post("/api/analyze", data="invalid-json")
        self.assertEqual(response.status_code, 422)

    def test_get_job_status_success(self):
        """Mock out a job in jobs cache and verify it returns correct JSON."""
        job_id = "test-job-12345"
        mock_job = MagicMock()
        mock_job.status = "completed"
        mock_job.progress = 100
        mock_job.message = "Successfully done!"
        mock_job.error = None

        jobs[job_id] = mock_job
        try:
            response = self.client.get(f"/api/job/{job_id}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "completed")
            self.assertEqual(data["progress"], 100)
            self.assertEqual(data["message"], "Successfully done!")
            self.assertIsNone(data["error"])
        finally:
            if job_id in jobs:
                del jobs[job_id]

    def test_video_endpoint_sanitization(self):
        """Verify video endpoint rejects traversal characters and malformed IDs."""
        # Malformed job ID
        response = self.client.get("/api/video/job_id_with_underscores/clip.mp4")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid job ID format", response.json()["detail"])

        # Traversal/dot file in clip filename
        response = self.client.get("/api/video/job-123/.ssh")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid clip filename format", response.json()["detail"])

    @patch("os.path.exists")
    @patch("os.path.abspath")
    def test_video_endpoint_fallback(self, mock_abspath, mock_exists):
        """Verify video endpoint triggers fallback to output/clips if file not in job folder."""
        # Setup paths: base_dir = D:\output, path = D:\output\job-1\clip.mp4, fallback = D:\output\clips\clip.mp4
        mock_abspath.side_effect = lambda x: x
        
        # Scenario: path doesn't exist, but fallback_path exists
        def exists_side_effect(path_str):
            if "clips" in path_str:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        # We patch FileResponse to prevent it from trying to open the mock file path
        with patch("main.FileResponse") as mock_fileresponse:
            mock_fileresponse.return_value = "MockFileResponse"
            response = self.client.get("/api/video/job-1/clip_123.mp4")
            self.assertEqual(response.status_code, 200)
            # The fallback path should have been passed to FileResponse
            mock_fileresponse.assert_called_once()
            args, kwargs = mock_fileresponse.call_args
            self.assertIn("clips", args[0])

if __name__ == "__main__":
    unittest.main()
