import os
import sys
import unittest
import json
import sqlite3
import math

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from analytics_repository import SqliteAnalyticsRepository
from analytics_engine import calculate_welch_t_test, analyze_ab_test

class TestExperimentationFramework(unittest.TestCase):
    def setUp(self):
        self.db_path = "output/test_experiments.db"
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass
        self.repo = SqliteAnalyticsRepository(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_schema_migration_columns(self):
        """Verifies that experiment tracking columns are created during initialization."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(clip_analytics)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()
        
        self.assertIn("experiment_id", columns)
        self.assertIn("variant_id", columns)
        self.assertIn("scoring_version", columns)
        self.assertIn("prompt_version", columns)
        self.assertIn("weight_version", columns)

    def test_save_metadata_with_experiment(self):
        """Verifies metadata insertion handles experiment attributes correctly."""
        self.repo.save_clip_metadata(
            video_id="vid_exp_1",
            clip_id="clip_exp_1",
            virality_score=8.2,
            detailed_scores={"hook_strength": 9, "controversy": 5},
            experiment_id="exp_test_v1",
            variant_id="B",
            scoring_version="B",
            prompt_version="prompt_v2",
            weight_version="weight_v2_high_hook"
        )
        
        records = self.repo.get_all_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["clip_id"], "clip_exp_1")
        self.assertEqual(records[0]["experiment_id"], "exp_test_v1")
        self.assertEqual(records[0]["variant_id"], "B")
        self.assertEqual(records[0]["scoring_version"], "B")
        self.assertEqual(records[0]["prompt_version"], "prompt_v2")
        self.assertEqual(records[0]["weight_version"], "weight_v2_high_hook")

    def test_welch_t_test_solver(self):
        """Verifies Welch's t-test calculation under clear difference."""
        x1 = [10.0, 12.0, 11.0, 13.0, 12.0, 11.5, 12.5, 11.8, 12.2, 11.0] # mean ~11.8
        x2 = [5.0, 6.0, 5.5, 4.8, 5.2, 6.1, 5.7, 5.3, 4.9, 5.5]       # mean ~5.4
        
        t_stat, p_val, conf = calculate_welch_t_test(x1, x2)
        
        self.assertTrue(t_stat > 0.0)
        self.assertTrue(p_val < 0.001)
        self.assertTrue(conf > 99.0)

    def test_experiment_guardrails(self):
        """Verifies winner is only declared when sample size and confidence requirements are met."""
        # Inject global DB overrides for test isolation
        from analytics_repository import db as global_db
        original_path = global_db.db_path
        global_db.db_path = self.db_path
        
        try:
            # Case A: Low sample size (< 30) but high difference
            for i in range(1, 11): # 10 records total
                variant = "A" if i % 2 == 1 else "B"
                self.repo.save_clip_metadata(f"v_{i}", f"c_{i}", 5.0, {}, "exp_virality_v1", variant)
                views = (1000 + i * 5) if variant=="A" else (9000 + i * 5)
                ret = (40.0 + (i % 3)) if variant=="A" else (85.0 + (i % 3))
                shares = (50 + i) if variant=="A" else (500 + i)
                self.repo.update_clip_analytics(f"c_{i}", "TikTok", views, 100, 10, shares, 45.0, ret, "2026-06-18")
                
            res = analyze_ab_test()
            self.assertEqual(res["status"], "Experiment Running - More Data Required")
            self.assertIsNone(res["winner"])
            self.assertEqual(res["current_leader"], "B") # B has higher composite mean
            
            # Case B: High sample size (>= 30) and high difference
            for i in range(11, 71): # 60 more records, total 70
                variant = "A" if i % 2 == 1 else "B"
                self.repo.save_clip_metadata(f"v_{i}", f"c_{i}", 5.0, {}, "exp_virality_v1", variant)
                views = (1000 + i * 5) if variant=="A" else (9000 + i * 5)
                ret = (40.0 + (i % 3)) if variant=="A" else (85.0 + (i % 3))
                shares = (50 + i) if variant=="A" else (500 + i)
                self.repo.update_clip_analytics(f"c_{i}", "TikTok", views, 100, 10, shares, 45.0, ret, "2026-06-18")
                
            res_large = analyze_ab_test()
            self.assertEqual(res_large["status"], "Statistically Significant Winner Declared")
            self.assertEqual(res_large["winner"], "B")
            self.assertTrue(res_large["thresholds_met"])
            
        finally:
            global_db.db_path = original_path

if __name__ == "__main__":
    unittest.main()
