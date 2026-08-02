import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import json

from services.asset_manager import AssetManager

SAMPLE_CHAMP_DATA = {
    "data": {
        "Aatrox": {"id": "Aatrox", "key": "266", "name": "Aatrox", "tags": ["Fighter"]},
        "Ahri": {"id": "Ahri", "key": "103", "name": "Ahri", "tags": ["Mage"]}
    }
}

class TestAssetManager(unittest.TestCase):
    def setUp(self):
        self.assets = AssetManager()

    def test_init(self):
        self.assertEqual(self.assets.champ_data, {})
        self.assertEqual(self.assets.id_to_key, {})
        self.assertEqual(self.assets.name_to_id, {})

    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_load_champion_data_cache_miss(self, mock_exists, mock_makedirs):
        """When cache file doesn't exist, download from DDragon and populate maps."""
        # First call: cache file doesn't exist -> download
        # Second call: file now exists for reading
        mock_exists.side_effect = [False]

        # Mock the session.get() on the instance
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_CHAMP_DATA
        self.assets.session = MagicMock()
        self.assets.session.get.return_value = mock_response

        self.assets.ddragon_ver = "14.4.1"

        # Mock file write + read to return our sample data
        data_json = json.dumps(SAMPLE_CHAMP_DATA)
        m = mock_open(read_data=data_json)
        with patch('builtins.open', m):
            with patch('json.load', return_value=SAMPLE_CHAMP_DATA):
                with patch('json.dump'):
                    self.assets._load_champion_data()

        self.assertIn("Aatrox", self.assets.champ_data)
        self.assertEqual(self.assets.id_to_key[266], "Aatrox")
        self.assertEqual(self.assets.name_to_id["aatrox"], 266)

    @patch('os.path.exists', return_value=True)
    def test_load_champion_data_cache_hit(self, mock_exists):
        """When cache file exists, load from disk without downloading."""
        self.assets.session = MagicMock()
        self.assets.ddragon_ver = "14.4.1"

        with patch('builtins.open', mock_open()):
            with patch('json.load', return_value=SAMPLE_CHAMP_DATA):
                self.assets._load_champion_data()

        self.assertIn("Aatrox", self.assets.champ_data)
        self.assertEqual(self.assets.id_to_key[266], "Aatrox")
        self.assertEqual(self.assets.name_to_id["aatrox"], 266)
        # Should NOT have called session.get since cache exists
        self.assets.session.get.assert_not_called()

    def test_preload_champion_icons(self):
        """Preload method pushes download tasks to background queue."""
        with patch.object(self.assets, 'get_icon') as mock_get_icon:
            self.assets.preload_champion_icons(["Aatrox", "Ahri"])
            # Drain queue tasks
            self.assets._download_queue.join()
            self.assertTrue(mock_get_icon.called)

    def test_get_champ_name(self):
        """Test champion ID to name resolution with fast path EAFP fallback."""
        self.assets.id_to_key = {266: "Aatrox"}
        self.assertEqual(self.assets.get_champ_name(266), "Aatrox")
        self.assertEqual(self.assets.get_champ_name(9999), "9999")

    def test_get_memory_summary_diagnostics(self):
        """Test memory usage summary diagnostics logging and structure."""
        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("icon_cache_count", summary)
        self.assertIn("splash_cache_count", summary)
        self.assertIn("id_to_tags_count", summary)
        self.assertIn("champ_roles_count", summary)
        self.assertIn("est_ram_mb", summary)
        self.assertIn("disk_cache", summary)
        self.assertEqual(summary["icon_cache_count"], 0)
        self.assertEqual(summary["splash_cache_count"], 0)

    def test_interned_tags_and_roles(self):
        """Verify champion tags and Meraki roles are stored as interned immutable tuples."""
        self.assets.id_to_tags = {266: ("Fighter", "Tank")}
        self.assets.champ_roles = {266: ("TOP", "JUNGLE")}
        self.assertIsInstance(self.assets.id_to_tags[266], tuple)
        self.assertIsInstance(self.assets.champ_roles[266], tuple)
        self.assertEqual(self.assets.id_to_tags[266][0], "Fighter")
        self.assertEqual(self.assets.champ_roles[266][0], "TOP")

    def test_skin_icon_memory_optimization_and_eviction(self):
        """Verify champion skin icon preview LRU cache, memory stats, and eviction."""
        self.assertEqual(len(self.assets.skin_icons), 0)
        self.assertEqual(self.assets.max_skin_icons, 80)

        # Mock dummy skin icon entries in cache
        for i in range(100):
            self.assets.skin_icons[f"skin_icon_{i}_60x60"] = MagicMock()

        # Enforce LRU cap
        evicted = self.assets.evict_skin_icon_memory(max_skin_count=80)
        self.assertEqual(evicted, 20)
        self.assertEqual(len(self.assets.skin_icons), 80)

        stats = self.assets.get_skin_icon_memory_stats()
        self.assertEqual(stats["skin_icon_count"], 80)
        self.assertEqual(stats["max_skin_icon_count"], 80)
        self.assertEqual(stats["evictions"], 20)

        # Test cache hit tracking via get_skin_icon with mock entry
        mock_skin = MagicMock()
        self.assets.skin_icons["skin_icon_266001_60x60"] = mock_skin
        res = self.assets.get_skin_icon(266001, size=(60, 60))
        self.assertEqual(res, mock_skin)

        metrics = self.assets.get_skin_icon_lru_cache_metrics()
        self.assertGreaterEqual(metrics["hits"], 1)
        self.assertEqual(metrics["evictions"], 20)
        self.assertGreater(metrics["hit_ratio"], 0.0)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("skin_icon_cache_count", summary)
        self.assertIn("skin_icon_lru_metrics", summary)
        self.assertEqual(summary["skin_icon_cache_count"], 81)
        self.assertEqual(summary["max_skin_icons_limit"], 80)
        self.assertEqual(summary["skin_icon_lru_metrics"]["evictions"], 20)

    def test_splash_art_lru_cache_metrics_and_eviction(self):
        """Verify skin splash art LRU cache hit/miss tracking, eviction metrics, and benchmarking."""
        self.assertEqual(len(self.assets.splash_icons), 0)
        self.assertEqual(self.assets.max_splash_icons, 15)

        # Mock dummy splash art entries in LRU cache
        mock_img1 = MagicMock()
        mock_img2 = MagicMock()
        self.assets.splash_icons["splash_266001_1280_1.0"] = mock_img1
        self.assets.splash_icons["splash_103001_1280_1.0"] = mock_img2

        # Direct cache hit test via get_splash_art
        res = self.assets.get_splash_art(266001, width=1280, opacity=1.0)
        self.assertEqual(res, mock_img1)

        metrics = self.assets.get_splash_lru_cache_metrics()
        self.assertEqual(metrics["splash_count"], 2)
        self.assertEqual(metrics["hits"], 1)
        self.assertEqual(metrics["misses"], 0)
        self.assertEqual(metrics["hit_ratio"], 1.0)

        # Populate up to 25 items to trigger eviction
        for i in range(25):
            self.assets.splash_icons[f"splash_dummy_{i}_1280_1.0"] = MagicMock()

        evicted = self.assets.evict_splash_art_memory(max_splash_count=15)
        self.assertEqual(evicted, 12)
        self.assertEqual(len(self.assets.splash_icons), 15)

        metrics2 = self.assets.get_splash_lru_cache_metrics()
        self.assertEqual(metrics2["evictions"], 12)
        self.assertEqual(metrics2["splash_count"], 15)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("splash_lru_metrics", summary)
        self.assertEqual(summary["splash_lru_metrics"]["evictions"], 12)

    def test_splash_download_memory_pooling_and_gc_optimization(self):
        """Verify champion splash asset download GC optimization & metrics reporting for Task 149."""
        metrics_initial = self.assets.get_splash_gc_metrics()
        self.assertEqual(metrics_initial["splash_download_count"], 0)
        self.assertEqual(metrics_initial["gc_triggers_count"], 0)
        self.assertEqual(metrics_initial["splash_mem_pool_bytes_saved"], 0)

        # Force GC optimization execution
        res = self.assets.gc_optimize_splash_downloads(force_gc=True)
        self.assertEqual(res["gc_triggers_count"], 1)

        # Simulate splash asset download count increment
        self.assets._splash_download_count += 5
        metrics_after = self.assets.get_splash_gc_metrics()
        self.assertEqual(metrics_after["splash_download_count"], 5)
        self.assertEqual(metrics_after["gc_triggers_count"], 1)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("splash_gc_metrics", summary)
        self.assertEqual(summary["splash_gc_metrics"]["splash_download_count"], 5)

    def test_disk_cache_scan_caching_and_telemetry(self):
        """Verify disk cache scan performance optimization with TTL scan caching for Task 155."""
        stats1 = self.assets.get_disk_cache_stats()
        self.assertIn("total_files", stats1)

        # Immediate second call should hit TTL cache
        stats2 = self.assets.get_disk_cache_stats()
        self.assertEqual(stats1, stats2)

        telemetry = self.assets.get_disk_cache_scan_telemetry()
        self.assertEqual(telemetry["disk_scan_count"], 1)
        self.assertEqual(telemetry["disk_scan_cache_hits"], 1)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("disk_cache_scan_telemetry", summary)
        self.assertEqual(summary["disk_cache_scan_telemetry"]["disk_scan_count"], 1)

    def test_champ_search_index_and_telemetry(self):
        """Verify indexed champion search filtering and performance telemetry for Task 158."""
        self.assets.id_to_key = {266: "Aatrox", 103: "Ahri"}
        self.assets.champ_data = {"Aatrox": {"name": "Aatrox"}, "Ahri": {"name": "Ahri"}}
        self.assets.id_to_tags = {266: ("Fighter",), 103: ("Mage",)}
        self.assets.champ_roles = {266: ("TOP",), 103: ("MIDDLE",)}
        self.assets._build_champ_search_index()

        res_name = self.assets.search_champions(query="aatrox")
        self.assertEqual(len(res_name), 1)
        self.assertEqual(res_name[0]["name"], "Aatrox")

        res_role = self.assets.search_champions(role="MIDDLE")
        self.assertEqual(len(res_role), 1)
        self.assertEqual(res_role[0]["name"], "Ahri")

        res_tag = self.assets.search_champions(tag="Fighter")
        self.assertEqual(len(res_tag), 1)
        self.assertEqual(res_tag[0]["name"], "Aatrox")

        telemetry = self.assets.get_champ_search_telemetry()
        self.assertEqual(telemetry["search_count"], 3)
        self.assertEqual(telemetry["index_size"], 2)
        self.assertGreaterEqual(telemetry["total_latency_ms"], 0.0)

    def test_champ_search_fuzzy_matching_and_telemetry(self):
        """Verify champion search fuzzy matching fallback, initials matching, caching, and telemetry for Task 161."""
        self.assets.id_to_key = {266: "Aatrox", 103: "Ahri", 21: "MissFortune"}
        self.assets.champ_data = {
            "Aatrox": {"name": "Aatrox"},
            "Ahri": {"name": "Ahri"},
            "MissFortune": {"name": "Miss Fortune"},
        }
        self.assets.id_to_tags = {266: ("Fighter",), 103: ("Mage",), 21: ("Marksman",)}
        self.assets.champ_roles = {266: ("TOP",), 103: ("MIDDLE",), 21: ("BOTTOM",)}
        self.assets._build_champ_search_index()

        # Test initials fuzzy match: "mf" -> "Miss Fortune"
        res_fuzzy_init = self.assets.search_champions(query="mf", enable_fuzzy=True)
        self.assertEqual(len(res_fuzzy_init), 1)
        self.assertEqual(res_fuzzy_init[0]["name"], "Miss Fortune")

        # Second search should hit fuzzy cache
        res_fuzzy_cached = self.assets.search_champions(query="mf", enable_fuzzy=True)
        self.assertEqual(res_fuzzy_cached[0]["name"], "Miss Fortune")

        telemetry = self.assets.get_fuzzy_search_telemetry()
        self.assertGreaterEqual(telemetry["fuzzy_search_count"], 1)
        self.assertEqual(telemetry["fuzzy_cache_hits"], 1)
        self.assertEqual(telemetry["fuzzy_cache_misses"], 1)
        self.assertEqual(telemetry["fuzzy_cache_hit_ratio"], 0.5)
        self.assertIn("fuzzy_cache_evictions", telemetry)
        self.assertIn("fuzzy_cache_memory_kb", telemetry)

        lru_metrics = self.assets.get_fuzzy_search_lru_cache_metrics()
        self.assertEqual(lru_metrics["hits"], 1)
        self.assertEqual(lru_metrics["misses"], 1)
        self.assertEqual(lru_metrics["hit_ratio"], 0.5)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("fuzzy_search_telemetry", summary)
        self.assertIn("fuzzy_search_lru_metrics", summary)
        self.assertEqual(summary["fuzzy_search_telemetry"]["fuzzy_cache_hits"], 1)
        self.assertEqual(summary["fuzzy_search_lru_metrics"]["hits"], 1)

if __name__ == '__main__':
    unittest.main()


