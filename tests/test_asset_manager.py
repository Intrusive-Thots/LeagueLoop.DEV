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

    def test_champ_search_fuzzy_eviction_memory_profiling(self):
        """Verify memory allocation profiling during fuzzy champion search query cache evictions for Task 167."""
        self.assets.id_to_key = {21: "MissFortune", 266: "Aatrox", 157: "Yasuo", 222: "Jinx"}
        self.assets.key_to_name = {"MissFortune": "Miss Fortune", "Aatrox": "Aatrox", "Yasuo": "Yasuo", "Jinx": "Jinx"}
        self.assets._build_champ_search_index()

        # Set small max capacity to trigger evictions easily
        self.assets._champ_search_fuzzy_cache_max = 2

        # Perform 3 distinct fuzzy searches to overflow cache of size 2
        self.assets.search_champions(query="mff", enable_fuzzy=True)
        self.assets.search_champions(query="aatt", enable_fuzzy=True)
        self.assets.search_champions(query="yass", enable_fuzzy=True)


        evictions_profile = self.assets.get_fuzzy_search_eviction_profile_telemetry()
        self.assertGreaterEqual(evictions_profile["fuzzy_eviction_count"], 1)
        self.assertGreater(evictions_profile["total_eviction_memory_bytes_reclaimed"], 0)
        self.assertGreater(evictions_profile["avg_eviction_memory_bytes"], 0.0)
        self.assertGreater(len(evictions_profile["recent_eviction_profiles"]), 0)

        # Check telemetry output
        fuzzy_t = self.assets.get_fuzzy_search_telemetry()
        self.assertIn("eviction_memory_bytes_reclaimed", fuzzy_t)
        self.assertIn("avg_eviction_memory_bytes", fuzzy_t)
        self.assertIn("eviction_profile_telemetry", fuzzy_t)

    def test_champ_search_predicate_memory_recycling(self):
        """Verify memory recycling for champion search index filter predicate functions for Task 170."""
        self.assets.id_to_key = {266: "Aatrox", 103: "Ahri"}
        self.assets.champ_data = {"Aatrox": {"name": "Aatrox"}, "Ahri": {"name": "Ahri"}}
        self.assets._build_champ_search_index()

        initial_telemetry = self.assets.get_search_predicate_pool_telemetry()
        self.assertEqual(initial_telemetry["predicate_recycle_hits"], 0)
        self.assertEqual(initial_telemetry["predicate_recycle_misses"], 0)

        # First search will create & cache predicate
        self.assets.search_champions(query="aatrox")
        tel1 = self.assets.get_search_predicate_pool_telemetry()
        self.assertEqual(tel1["predicate_recycle_misses"], 1)
        self.assertEqual(tel1["predicate_recycle_hits"], 0)

        # Second search with identical filter criteria should hit predicate cache
        self.assets.search_champions(query="aatrox")
        tel2 = self.assets.get_search_predicate_pool_telemetry()
        self.assertEqual(tel2["predicate_recycle_hits"], 1)
        self.assertGreater(tel2["predicate_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["predicate_bytes_recycled"], 0)

        champ_tel = self.assets.get_champ_search_telemetry()
        self.assertIn("predicate_recycle_hits", champ_tel)
        self.assertIn("predicate_recycle_hit_ratio", champ_tel)

        # Clear pool
        self.assets.clear_search_predicate_pool()
        self.assertEqual(len(self.assets._champ_search_predicate_cache), 0)

    def test_champ_search_slice_tuple_memory_pooling(self):
        """Verify memory pooling for champion search result slice tuple creation for Task 173."""
        self.assets.id_to_key = {266: "Aatrox", 103: "Ahri", 157: "Yasuo"}
        self.assets.champ_data = {"Aatrox": {"name": "Aatrox"}, "Ahri": {"name": "Ahri"}, "Yasuo": {"name": "Yasuo"}}
        self.assets._build_champ_search_index()

        initial_tel = self.assets.get_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["slice_recycle_misses"], 0)

        # First query builds and caches slice tuple
        res1 = self.assets.search_champions(query="a", limit=10)
        tel1 = self.assets.get_search_slice_pool_telemetry()
        self.assertEqual(tel1["slice_recycle_misses"], 1)
        self.assertEqual(tel1["slice_recycle_hits"], 0)

        # Repeated query accesses pooled slice tuple
        res2 = self.assets.search_champions(query="a", limit=10)
        tel2 = self.assets.get_search_slice_pool_telemetry()
        self.assertEqual(tel2["slice_recycle_hits"], 1)
        self.assertGreater(tel2["slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["slice_bytes_recycled"], 0)
        self.assertEqual(res1, res2)

        champ_tel = self.assets.get_champ_search_telemetry()
        self.assertIn("slice_recycle_hits", champ_tel)
        self.assertIn("slice_recycle_hit_ratio", champ_tel)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("search_slice_pool_telemetry", summary)

        # Clear pool
        self.assets.clear_search_slice_pool()
        self.assertEqual(len(self.assets._champ_search_slice_pool), 0)

    def test_skin_search_slice_tuple_memory_pooling(self):
        """Verify benchmark and optimization of memory pooling for champion skin preview search query slice tuple creation for Task 176."""
        self.assets.id_to_key = {266: "Aatrox", 103: "Ahri"}
        self.assets.champ_data = {"Aatrox": {"name": "Aatrox"}, "Ahri": {"name": "Ahri"}}
        self.assets._build_champ_search_index()

        initial_tel = self.assets.get_skin_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["skin_slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["skin_slice_recycle_misses"], 0)

        # First query builds and caches skin preview slice tuple
        skins1 = self.assets.search_skin_previews(query="aatrox", limit=10)
        tel1 = self.assets.get_skin_search_slice_pool_telemetry()
        self.assertEqual(tel1["skin_slice_recycle_misses"], 1)
        self.assertEqual(tel1["skin_slice_recycle_hits"], 0)

        # Repeated query accesses pooled skin preview slice tuple
        skins2 = self.assets.search_skin_previews(query="aatrox", limit=10)
        tel2 = self.assets.get_skin_search_slice_pool_telemetry()
        self.assertEqual(tel2["skin_slice_recycle_hits"], 1)
        self.assertGreater(tel2["skin_slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["skin_slice_bytes_recycled"], 0)
        self.assertEqual(skins1, skins2)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("skin_search_slice_pool_telemetry", summary)
        self.assertEqual(summary["skin_search_slice_pool_telemetry"]["skin_slice_recycle_hits"], 1)

        # Clear pool
        self.assets.clear_skin_search_slice_pool()
        self.assertEqual(len(self.assets._skin_search_slice_pool), 0)

    def test_splash_search_slice_tuple_memory_pooling(self):
        """Verify benchmark and optimization of memory pooling for champion splash art filter query result slice tuple creation for Task 179."""
        self.assets.id_to_key = {266: "Aatrox", 103: "Ahri"}
        self.assets.champ_data = {"Aatrox": {"name": "Aatrox"}, "Ahri": {"name": "Ahri"}}
        self.assets._build_champ_search_index()

        initial_tel = self.assets.get_splash_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["splash_slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["splash_slice_recycle_misses"], 0)

        # First query builds and caches splash preview slice tuple
        splashes1 = self.assets.search_splash_previews(query="aatrox", limit=10)
        tel1 = self.assets.get_splash_search_slice_pool_telemetry()
        self.assertEqual(tel1["splash_slice_recycle_misses"], 1)
        self.assertEqual(tel1["splash_slice_recycle_hits"], 0)

        # Repeated query accesses pooled splash preview slice tuple
        splashes2 = self.assets.search_splash_previews(query="aatrox", limit=10)
        tel2 = self.assets.get_splash_search_slice_pool_telemetry()
        self.assertEqual(tel2["splash_slice_recycle_hits"], 1)
        self.assertGreater(tel2["splash_slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["splash_slice_bytes_recycled"], 0)
        self.assertEqual(splashes1, splashes2)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("splash_search_slice_pool_telemetry", summary)
        self.assertEqual(summary["splash_search_slice_pool_telemetry"]["splash_slice_recycle_hits"], 1)

        # Clear pool
        self.assets.clear_splash_search_slice_pool()
        self.assertEqual(len(self.assets._splash_search_slice_pool), 0)

    def test_item_build_search_slice_tuple_memory_pooling(self):
        """Verify benchmark and optimization of memory pooling for champion item build recommendation search query slice tuple creation for Task 182."""
        self.assets.id_to_key = {266: "Aatrox", 103: "Ahri"}
        self.assets.champ_data = {"Aatrox": {"name": "Aatrox", "tags": ["Fighter"]}, "Ahri": {"name": "Ahri", "tags": ["Mage"]}}
        self.assets._build_champ_search_index()

        initial_tel = self.assets.get_item_build_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["item_build_slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["item_build_slice_recycle_misses"], 0)

        # First query builds and caches item build slice tuple
        builds1 = self.assets.search_item_build_recommendations(query="aatrox", limit=10)
        tel1 = self.assets.get_item_build_search_slice_pool_telemetry()
        self.assertEqual(tel1["item_build_slice_recycle_misses"], 1)
        self.assertEqual(tel1["item_build_slice_recycle_hits"], 0)

        # Repeated query accesses pooled item build slice tuple
        builds2 = self.assets.search_item_build_recommendations(query="aatrox", limit=10)
        tel2 = self.assets.get_item_build_search_slice_pool_telemetry()
        self.assertEqual(tel2["item_build_slice_recycle_hits"], 1)
        self.assertGreater(tel2["item_build_slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["item_build_slice_bytes_recycled"], 0)
        self.assertEqual(builds1, builds2)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("item_build_search_slice_pool_telemetry", summary)
        self.assertEqual(summary["item_build_search_slice_pool_telemetry"]["item_build_slice_recycle_hits"], 1)

        # Clear pool
        self.assets.clear_item_build_search_slice_pool()
        self.assertEqual(len(self.assets._item_build_search_slice_pool), 0)

    def test_rune_page_search_slice_tuple_pooling(self):
        """Task 185: Test champion rune page recommendation search query result slice tuple memory recycling and telemetry."""
        initial_tel = self.assets.get_rune_page_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["rune_page_slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["rune_page_slice_recycle_misses"], 0)

        # Initial query creates slice tuple (miss)
        runes1 = self.assets.search_rune_page_recommendations(query="aatrox", limit=10)
        tel1 = self.assets.get_rune_page_search_slice_pool_telemetry()
        self.assertEqual(tel1["rune_page_slice_recycle_misses"], 1)
        self.assertEqual(tel1["rune_page_slice_recycle_hits"], 0)

        # Repeated query accesses pooled rune page slice tuple (hit)
        runes2 = self.assets.search_rune_page_recommendations(query="aatrox", limit=10)
        tel2 = self.assets.get_rune_page_search_slice_pool_telemetry()
        self.assertEqual(tel2["rune_page_slice_recycle_hits"], 1)
        self.assertGreater(tel2["rune_page_slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["rune_page_slice_bytes_recycled"], 0)
        self.assertEqual(runes1, runes2)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("rune_page_search_slice_pool_telemetry", summary)
        self.assertEqual(summary["rune_page_search_slice_pool_telemetry"]["rune_page_slice_recycle_hits"], 1)

        # Clear pool
        self.assets.clear_rune_page_search_slice_pool()
        self.assertEqual(len(self.assets._rune_page_search_slice_pool), 0)

    def test_spell_ability_recommendations_memory_pooling(self):
        """Task 188: Test champion spell ability recommendation search query result slice tuple memory recycling and telemetry."""
        initial_tel = self.assets.get_spell_ability_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["spell_ability_slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["spell_ability_slice_recycle_misses"], 0)

        # Initial query creates slice tuple (miss)
        spells1 = self.assets.search_spell_ability_recommendations(query="ahri", limit=10)
        tel1 = self.assets.get_spell_ability_search_slice_pool_telemetry()
        self.assertEqual(tel1["spell_ability_slice_recycle_misses"], 1)
        self.assertEqual(tel1["spell_ability_slice_recycle_hits"], 0)

        # Repeated query accesses pooled spell ability slice tuple (hit)
        spells2 = self.assets.search_spell_ability_recommendations(query="ahri", limit=10)
        tel2 = self.assets.get_spell_ability_search_slice_pool_telemetry()
        self.assertEqual(tel2["spell_ability_slice_recycle_hits"], 1)
        self.assertGreater(tel2["spell_ability_slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["spell_ability_slice_bytes_recycled"], 0)
        self.assertEqual(spells1, spells2)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("spell_ability_search_slice_pool_telemetry", summary)
        self.assertEqual(summary["spell_ability_search_slice_pool_telemetry"]["spell_ability_slice_recycle_hits"], 1)

        # Clear pool
        self.assets.clear_spell_ability_search_slice_pool()
        self.assertEqual(len(self.assets._spell_ability_search_slice_pool), 0)

    def test_counters_recommendations_memory_pooling(self):
        """Task 191: Test champion counters recommendation search query result slice tuple memory recycling and telemetry."""
        initial_tel = self.assets.get_counters_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["counters_slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["counters_slice_recycle_misses"], 0)

        # Initial query creates slice tuple (miss)
        counters1 = self.assets.search_counters_recommendations(query="ahri", limit=10)
        tel1 = self.assets.get_counters_search_slice_pool_telemetry()
        self.assertEqual(tel1["counters_slice_recycle_misses"], 1)
        self.assertEqual(tel1["counters_slice_recycle_hits"], 0)

        # Repeated query accesses pooled counters slice tuple (hit)
        counters2 = self.assets.search_counters_recommendations(query="ahri", limit=10)
        tel2 = self.assets.get_counters_search_slice_pool_telemetry()
        self.assertEqual(tel2["counters_slice_recycle_hits"], 1)
        self.assertGreater(tel2["counters_slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["counters_slice_bytes_recycled"], 0)
        self.assertEqual(counters1, counters2)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("counters_search_slice_pool_telemetry", summary)
        self.assertEqual(summary["counters_search_slice_pool_telemetry"]["counters_slice_recycle_hits"], 1)

        # Clear pool
        self.assets.clear_counters_search_slice_pool()
        self.assertEqual(len(self.assets._counters_search_slice_pool), 0)

    def test_synergy_recommendations_memory_pooling(self):
        """Task 194: Test champion synergy recommendations search query result slice tuple memory recycling and telemetry."""
        initial_tel = self.assets.get_synergy_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["synergy_slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["synergy_slice_recycle_misses"], 0)

        # Initial query creates slice tuple (miss)
        synergies1 = self.assets.search_synergy_recommendations(query="ahri", limit=10)
        tel1 = self.assets.get_synergy_search_slice_pool_telemetry()
        self.assertEqual(tel1["synergy_slice_recycle_misses"], 1)
        self.assertEqual(tel1["synergy_slice_recycle_hits"], 0)

        # Repeated query accesses pooled synergy slice tuple (hit)
        synergies2 = self.assets.search_synergy_recommendations(query="ahri", limit=10)
        tel2 = self.assets.get_synergy_search_slice_pool_telemetry()
        self.assertEqual(tel2["synergy_slice_recycle_hits"], 1)
        self.assertGreater(tel2["synergy_slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["synergy_slice_bytes_recycled"], 0)
        self.assertEqual(synergies1, synergies2)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("synergy_search_slice_pool_telemetry", summary)
        self.assertEqual(summary["synergy_search_slice_pool_telemetry"]["synergy_slice_recycle_hits"], 1)

        # Clear pool
        self.assets.clear_synergy_search_slice_pool()
        self.assertEqual(len(self.assets._synergy_search_slice_pool), 0)

    def test_draft_pick_recommendations_memory_pooling(self):
        """Task 197: Test champion draft pick recommendations search query result slice tuple memory recycling and telemetry."""
        initial_tel = self.assets.get_draft_pick_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["draft_pick_slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["draft_pick_slice_recycle_misses"], 0)

        # Initial query creates slice tuple (miss)
        picks1 = self.assets.search_draft_pick_recommendations(query="ahri", limit=10)
        tel1 = self.assets.get_draft_pick_search_slice_pool_telemetry()
        self.assertEqual(tel1["draft_pick_slice_recycle_misses"], 1)
        self.assertEqual(tel1["draft_pick_slice_recycle_hits"], 0)

        # Repeated query accesses pooled draft pick slice tuple (hit)
        picks2 = self.assets.search_draft_pick_recommendations(query="ahri", limit=10)
        tel2 = self.assets.get_draft_pick_search_slice_pool_telemetry()
        self.assertEqual(tel2["draft_pick_slice_recycle_hits"], 1)
        self.assertGreater(tel2["draft_pick_slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["draft_pick_slice_bytes_recycled"], 0)
        self.assertEqual(picks1, picks2)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("draft_pick_search_slice_pool_telemetry", summary)
        self.assertEqual(summary["draft_pick_search_slice_pool_telemetry"]["draft_pick_slice_recycle_hits"], 1)

        # Clear pool
        self.assets.clear_draft_pick_search_slice_pool()
        self.assertEqual(len(self.assets._draft_pick_search_slice_pool), 0)

    def test_ban_priority_recommendations_memory_pooling(self):
        """Task 200: Test champion ban priority recommendations search query result slice tuple memory recycling and telemetry."""
        initial_tel = self.assets.get_ban_priority_search_slice_pool_telemetry()
        self.assertEqual(initial_tel["ban_priority_slice_recycle_hits"], 0)
        self.assertEqual(initial_tel["ban_priority_slice_recycle_misses"], 0)

        # Initial query creates slice tuple (miss)
        bans1 = self.assets.search_ban_priority_recommendations(query="ahri", limit=10)
        tel1 = self.assets.get_ban_priority_search_slice_pool_telemetry()
        self.assertEqual(tel1["ban_priority_slice_recycle_misses"], 1)
        self.assertEqual(tel1["ban_priority_slice_recycle_hits"], 0)

        # Repeated query accesses pooled ban priority slice tuple (hit)
        bans2 = self.assets.search_ban_priority_recommendations(query="ahri", limit=10)
        tel2 = self.assets.get_ban_priority_search_slice_pool_telemetry()
        self.assertEqual(tel2["ban_priority_slice_recycle_hits"], 1)
        self.assertGreater(tel2["ban_priority_slice_recycle_hit_ratio"], 0.0)
        self.assertGreater(tel2["ban_priority_slice_bytes_recycled"], 0)
        self.assertEqual(bans1, bans2)

        summary = self.assets.get_memory_summary_diagnostics()
        self.assertIn("ban_priority_search_slice_pool_telemetry", summary)
        self.assertEqual(summary["ban_priority_search_slice_pool_telemetry"]["ban_priority_slice_recycle_hits"], 1)

        # Clear pool
        self.assets.clear_ban_priority_search_slice_pool()
        self.assertEqual(len(self.assets._ban_priority_search_slice_pool), 0)

if __name__ == '__main__':
    unittest.main()






