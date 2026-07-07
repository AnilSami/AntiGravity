import os
import sys
import unittest
import json
import sqlite3

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from analytics_repository import SqliteAnalyticsRepository
from analytics_engine import calculate_correlation

class TestCreatorIntelligenceSystem(unittest.TestCase):
    def setUp(self):
        # Create a test-specific SQLite database
        self.db_path = "output/test_analytics.db"
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass
        self.repo = SqliteAnalyticsRepository(db_path=self.db_path)

    def tearDown(self):
        # Clean up database file after test run
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_database_initialization(self):
        """Verifies tables are created with proper columns."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(clip_analytics)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()
        
        self.assertIn("video_id", columns)
        self.assertIn("clip_id", columns)
        self.assertIn("published", columns)
        self.assertIn("creator_selected", columns)
        self.assertIn("creator_rejected", columns)

    def test_save_and_update_analytics(self):
        """Verifies metadata insertion and performance updates."""
        # 1. Save metadata
        self.repo.save_clip_metadata(
            video_id="vid_test_1",
            clip_id="clip_test_1",
            virality_score=8.5,
            detailed_scores={"hook_strength": 9, "storytelling": 8}
        )
        
        records = self.repo.get_all_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["clip_id"], "clip_test_1")
        self.assertEqual(records[0]["virality_score"], 8.5)
        
        # 2. Update performance metrics
        self.repo.update_clip_analytics(
            clip_id="clip_test_1",
            platform="TikTok",
            views=15000,
            likes=1200,
            comments=45,
            shares=300,
            watch_time=45.2,
            retention=75.5,
            upload_date="2026-06-18"
        )
        
        records = self.repo.get_all_records()
        self.assertEqual(records[0]["platform"], "TikTok")
        self.assertEqual(records[0]["views"], 15000)
        self.assertEqual(records[0]["retention"], 75.5)

    def test_creator_action_tracking(self):
        """Verifies that creator choice flags are updated successfully."""
        self.repo.save_clip_metadata("vid_1", "clip_1", 7.0, {})
        
        # Select and publish
        self.repo.update_creator_action("clip_1", selected=True, published=True)
        records = self.repo.get_all_records()
        self.assertEqual(records[0]["creator_selected"], 1)
        self.assertEqual(records[0]["published"], 1)
        self.assertEqual(records[0]["creator_rejected"], 0)
        
        # Reject
        self.repo.update_creator_action("clip_1", selected=False, rejected=True, published=False)
        records = self.repo.get_all_records()
        self.assertEqual(records[0]["creator_selected"], 0)
        self.assertEqual(records[0]["published"], 0)
        self.assertEqual(records[0]["creator_rejected"], 1)

    def test_pearson_correlation_calculation(self):
        """Verifies correlation calculations against expected mathematical figures."""
        # Clean positive correlation
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        r = calculate_correlation(x, y)
        self.assertAlmostEqual(r, 1.0, places=5)
        
        # Clean negative correlation
        y_neg = [10.0, 8.0, 6.0, 4.0, 2.0]
        r_neg = calculate_correlation(x, y_neg)
        self.assertAlmostEqual(r_neg, -1.0, places=5)
        
        # Zero correlation
        y_zero = [1.0, 1.0, 1.0, 1.0, 1.0]
        r_zero = calculate_correlation(x, y_zero)
        self.assertEqual(r_zero, 0.0)

if __name__ == "__main__":
    unittest.main()
