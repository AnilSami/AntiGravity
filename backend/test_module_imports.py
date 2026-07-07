import unittest
import importlib
import logging

logger = logging.getLogger(__name__)

class TestModuleImports(unittest.TestCase):
    """CI test to verify all backend modules import cleanly without syntax or import errors."""

    def test_all_modules_import_cleanly(self):
        modules = [
            "config",
            "analytics_repository",
            "youtube_service",
            "subtitle_detector",
            "upload_package",
            "music_selector",
            "clipper",
            "analyzer",
            "job_manager",
            "main"
        ]
        for mod_name in modules:
            with self.subTest(module=mod_name):
                try:
                    mod = importlib.import_module(mod_name)
                    self.assertIsNotNone(mod, f"Module {mod_name} returned None on import")
                except Exception as e:
                    logger.error(f"Failed to import {mod_name}: {e}", exc_info=True)
                    self.fail(f"Module '{mod_name}' failed to import cleanly: {e}")
