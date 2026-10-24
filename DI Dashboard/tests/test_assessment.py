import copy, json, tempfile, unittest, sys, io
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.store import Store
from backend.rules import *
from backend.weather import decode_weather, RainfallWorker


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "runtime/tests"
        root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.path = Path(self.tmp.name) / "test.sqlite"
        self.db = Store(self.path, seed=False)
        self.site = validate_site(
            dict(
                name="Test spring",
                spring_name="Test spring",
                handpump_name="Test pump",
                village="Test village",
                district="Test district",
                gps_later=True,
                link_basis="unknown",
            )
        )
        self.db.save_site(self.site)

    def tearDown(self):
        self.tmp.cleanup()

    def visit(self, when="2025-04-01", litres=10):
        return dict(
            site_id=self.site["id"],
            visit_date=when,
            visitor="Test team",
            season="dry",
            spring=dict(
                status="measured",
                point="Outlet A",
                capture="full",
                readings=[dict(litres=litres, seconds=60)] * 3,
            ),
            pump=dict(status="working"),
            di=dict(status="connected"),
            safety={},
            tests=[],
            change_status="none",
            changes=[],
            notes="",
            other_work="",
        )

    def save(self, b):
        v = validate_visit(copy.deepcopy(b), self.db.state(), True)
        self.db.save_visit(v)
        return v

    def test_site_required_and_zero_coordinates(self):
        with self.assertRaises(Invalid):
            validate_site({})
        b = {**self.site, "gps_later": False, "latitude": 0, "longitude": 0}
        s = validate_site(b, self.site)
        self.assertEqual(coords_key(s), "0.000000,0.000000:era5")
        b["latitude"] = 91
        with self.assertRaises(Invalid):
            validate_site(b, self.site)

    def test_database_persistence_and_unlimited_sites(self):
        for i in range(10):
            self.db.save_site(validate_site({**self.site, "name": str(i)}))
        self.assertEqual(len(Store(self.path, seed=False).state()["sites"]), 11)
        draft = validate_visit(self.visit(), self.db.state())
        self.db.save_visit(draft)
        state = Store(self.path, seed=False).state()
        self.assertEqual(state["visits"][0]["status"], "draft")
        self.assertEqual(assess(state)["sites"][0]["visit_count"], 0)

    def test_readings_si_and_invalid_input(self):
        v = self.save(self.visit())
        self.assertEqual(v["spring"]["flow_lpm"], 10)
        self.assertAlmostEqual(v["spring"]["flow_m3_s"], 10 / 60000)
        for rows in (
            [{"litres": 10, "seconds": 0}] * 3,
            [{"litres": 10, "seconds": 60}] * 2,
            [{"litres": "NaN", "seconds": 60}] * 3,
        ):
            b = self.visit()
            b["spring"]["readings"] = rows
            with self.assertRaises(Invalid):
                self.save(b)

    def test_missing_is_not_zero(self):
        b = self.visit()
        b["spring"] = {"status": "not_measured", "reason": "No access", "flow_lpm": 999}
        v = self.save(b)
        self.assertNotIn("flow_lpm", v["spring"])
        self.assertIsNone(assess(self.db.state())["sites"][0]["current_flow"])

    def test_correction_and_immutability(self):
        old = self.save(self.visit())
        with self.assertRaises(Invalid):
            self.save(old)
        b = self.visit(litres=20)
        b.update(supersedes=old["id"], correction_reason="Corrected paper reading")
        new = self.save(b)
        self.assertEqual(len(self.db.state()["visits"]), 2)
        self.assertEqual([v["id"] for v in active_visits(self.db.state()["visits"])], [new["id"]])
        with self.assertRaises(Invalid):
            self.save(b)

    def test_fair_comparison(self):
        self.save(self.visit())
        self.save(self.visit("2026-04-01", 15))
        a = assess(self.db.state())["sites"][0]
        self.assertEqual(a["comparison"]["difference_lpm"], 5)
        b = self.visit("2026-05-01", 30)
        b["spring"]["capture"] = "partial"
        self.save(b)
        self.assertIsNone(assess(self.db.state())["sites"][0]["comparison"])

    def test_files_never_used_as_data(self):
        self.save(self.visit())
        before = assess(self.db.state())
        self.db.attachment(
            dict(
                id="test-file",
                site_id=self.site["id"],
                visit_id=None,
                name="flow is 999.txt",
                path="unused",
                contents="flow_lpm=999",
            )
        )
        self.assertEqual(before, assess(self.db.state()))

    def test_rain_missing_days_and_roof_units(self):
        end = today() - timedelta(days=7)
        dates = [(end - timedelta(days=89 - i)).isoformat() for i in range(90)]
        weather = dict(dates=dates, rain_mm=[2] * 90)
        self.assertEqual(rain_window(weather, end)["rain_mm"], 180)
        weather["rain_mm"][0] = None
        self.assertIsNone(rain_window(weather, end))
        weather["rain_mm"][0] = 2
        s = {
            **self.site,
            "gps_later": False,
            "latitude": 30.4,
            "longitude": 78.3,
            "roof_area_m2": 100,
            "collection_factor": 0.8,
        }
        self.db.save_site(s)
        self.db.weather(coords_key(s), weather, "{}", "test")
        self.assertEqual(assess(self.db.state())["sites"][0]["roof_potential"]["volume_m3"], 14.4)

    def test_weather_units_and_provider_null(self):
        obj = {
            "daily_units": {"rain_sum": "mm"},
            "daily": {"time": ["2025-01-01", "2025-01-02"], "rain_sum": [None, 4]},
        }
        site = {**self.site, "latitude": 30.4, "longitude": 78.3}
        out = decode_weather(json.dumps(obj), site, date(2025, 1, 1), date(2025, 1, 2))
        self.assertEqual(out["rain_mm"], [None, 4])
        obj["daily_units"]["rain_sum"] = "inch"
        with self.assertRaises(ValueError):
            decode_weather(json.dumps(obj), site, date(2025, 1, 1), date(2025, 1, 2))

    def test_no_network_without_gps(self):
        def prohibited(*a, **k):
            self.fail("Coordinates missing: no request should be sent")

        RainfallWorker(self.db, prohibited).refresh_due()
        self.assertEqual(self.db.state()["weather_jobs"][0]["status"], "needs_gps")

    def test_request_replay(self):
        v = validate_visit(self.visit(), self.db.state(), True)
        self.db.save_visit(v, "key", "hash")
        self.assertEqual(self.db.save_visit(v, "key", "hash"), v)
        with self.assertRaises(ValueError):
            self.db.save_visit(v, "key", "changed")

    def test_shared_weather_cache_and_failure_retention(self):
        site = {**self.site, "latitude": 30.4, "longitude": 78.3, "gps_later": False}
        self.db.save_site(site)
        self.db.save_site(validate_site({**site, "name": "Second test site"}))
        calls = []

        def opener(request, **kwargs):
            calls.append(request.full_url)
            self.assertNotIn("Test", request.full_url)
            return io.BytesIO(
                json.dumps(
                    {
                        "daily_units": {"rain_sum": "mm"},
                        "daily": {"time": ["2025-01-01", "2025-01-02"], "rain_sum": [1, 2]},
                    }
                ).encode()
            )

        worker = RainfallWorker(self.db, opener)
        worker.refresh_due()
        worker.refresh_due()
        self.assertEqual(len(calls), 1)
        key = coords_key(site)
        cache = self.db.state()["weather"][key]
        cache["fetched_at"] = "2020-01-01T00:00:00+00:00"
        self.db.weather(key, cache, "original", "checksum")

        def offline(*a, **k):
            raise OSError("Network unavailable")

        RainfallWorker(self.db, offline).refresh_due()
        self.assertEqual(self.db.state()["weather"][key], cache)
        self.assertTrue(all(j["status"] == "failed" for j in self.db.state()["weather_jobs"]))

    def test_minimal_draft_can_be_reopened(self):
        v = validate_visit({"site_id": self.site["id"]}, self.db.state())
        self.assertEqual(v["tests"], [])
        self.assertEqual(v["spring"], {})
        self.assertEqual(v["visitor"], "")
        with self.assertRaises(Invalid):
            validate_visit({**self.visit(), "changes": ["invalid"]}, self.db.state(), True)

    def test_independent_locations_and_rainfall_at_pump(self):
        s = validate_site(
            {
                **self.site,
                "gps_later": False,
                "latitude": 30.3,
                "longitude": 78.3,
                "pump_gps_later": False,
                "pump_latitude": 30.4,
                "pump_longitude": 78.4,
            },
            self.site,
        )
        self.assertEqual(s["latitude"], 30.3)
        self.assertEqual(s["pump_latitude"], 30.4)
        self.assertEqual(coords_key(s), "30.400000,78.400000:era5")
        self.db.save_site(s)
        self.assertGreater(assess(self.db.state())["sites"][0]["straight_distance_m"], 1000)
        with self.assertRaises(Invalid):
            validate_site({**s, "pump_latitude": 100}, s)

    def test_pump_and_spring_changes_are_independent(self):
        for when, flow, pump in [("2025-04-01", 10, 1), ("2026-04-01", 15, 2)]:
            b = self.visit(when, flow)
            b["pump"].update(
                measure=True, readings=[{"litres": pump, "seconds": 60}] * 3, procedure="Steady full strokes"
            )
            self.save(b)
        a = assess(self.db.state())["sites"][0]
        self.assertEqual(a["spring"]["comparison"]["difference_lpm"], 5)
        self.assertEqual(a["handpump"]["comparison"]["difference_lpm"], 1)

    def test_unknown_di_excluded_and_no_impact_weights(self):
        self.save(self.visit())
        second = validate_site({**self.site, "name": "Second site"})
        self.db.save_site(second)
        state = assess(self.db.state())
        self.assertEqual(state["portfolio"]["di_checked"], 1)
        self.assertEqual(state["portfolio"]["di_connected_percent"], 100)
        self.assertIsNone(state["methodology"]["composite_weights"])

    def test_source_date_range_does_not_create_comparison(self):
        self.save(self.visit())
        v = validate_visit(self.visit("2026-04-01", 20), self.db.state(), True)
        v.update(date_accuracy="range", visit_date_end="2026-04-02", entry_method="source_review")
        self.db.save_visit(v)
        a = assess(self.db.state())["sites"][0]
        self.assertIsNone(a["comparison"])
        self.assertEqual(a["current_flow"], 20)

    def test_another_pumps_status_is_not_transferred(self):
        site = {
            **self.site,
            "additional_handpumps": [{"name": "Other pump", "latitude": 30.4, "longitude": 78.4}],
        }
        self.db.save_site(site)
        v = validate_visit(self.visit(), self.db.state(), True)
        v.update(pump_asset_name="Other pump")
        v["pump"]["status"] = "broken"
        v["di"]["status"] = "broken"
        self.db.save_visit(v)
        a = assess(self.db.state())["sites"][0]
        self.assertEqual(a["handpump"]["status"], "not_checked")
        self.assertEqual(a["di_status"], "not_checked")
        self.assertEqual(a["equipment"][1]["pump_status"], "broken")
        self.assertTrue(a["maintenance"])


if __name__ == "__main__":
    unittest.main()
