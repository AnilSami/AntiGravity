import os
import unittest
from upload_package import generate_upload_package

class TestUploadPackage(unittest.TestCase):
    def test_mock_generation(self):
        # Test mock generation behavior
        package = generate_upload_package(
            clip_text="This is a test transcript of a viral clip talking about secrets.",
            hook="This is a test transcript",
            virality_score=8.5,
            virality_reasoning="High emotional intensity.",
            duration=35.0,
            api_key="mock"
        )
        
        self.assertIsNotNone(package)
        self.assertIn("titles", package)
        self.assertEqual(len(package["titles"]), 3)
        self.assertIn("description", package)
        self.assertIn("hashtags", package)
        self.assertEqual(len(package["hashtags"]), 15)
        self.assertIn("thumbnail_text", package)
        self.assertIn("best_time_to_post", package)
        self.assertIn("target_audience", package)
        self.assertIn("hook_analysis", package)
        self.assertEqual(package["thumbnail_text"], "SHOCKING TRUTH EXPOSED")
        self.assertIn("keywords", package)
        self.assertEqual(len(package["keywords"]), 10)
        self.assertIn("category", package)
        self.assertIn("language", package)
        self.assertIn("search_intent", package)

    def test_fallback_on_api_error(self):
        # When api_key is invalid and LLM raises error, should gracefully return default package
        package = generate_upload_package(
            clip_text="Test transcript",
            hook="Hook text",
            virality_score=5.0,
            virality_reasoning="Normal clip.",
            duration=15.0,
            api_key="invalid_key_to_trigger_error"
        )
        self.assertIsNotNone(package)
        self.assertIn("titles", package)
        self.assertEqual(len(package["titles"]), 3)
        self.assertIn("metadata", package)
        self.assertEqual(package["metadata"]["provider"], "fallback")
        self.assertIn("keywords", package)
        self.assertIn("category", package)
        self.assertIn("language", package)
        self.assertIn("search_intent", package)

if __name__ == "__main__":
    unittest.main()
