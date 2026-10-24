import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.store import Store
from backend.rules import Invalid, validate_site, validate_visit, assess
from backend import watsan_import
from backend.impact import change


def reading(lpm):
    return [{"litres": lpm, "seconds": 60}] * 3


class ImpactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Store(Path(self.tmp.name) / "t.sqlite", seed=False)

    def tearDown(self):
        self.tmp.cleanup()

    def site(self, **extra):
        site = validate_site(
            dict(name="S", spring_name="S", handpump_name="HP 1", village="V", district="D",
                 gps_later=True, link_basis="reported", **extra)
        )
        self.db.save_site(site)
        return site

    def visit(self, site, day, spring, pump="working", di="connected", **extra):
        v = validate_visit(
            dict(site_id=site["id"], visit_date=day, visitor="R", season="dry", spring=spring,
                 pump={"status": pump}, di={"status": di}, change_status="not_discussed", **extra),
            self.db.state(), True,
        )
        self.db.save_visit(v)
        return v

    def test_change_ranges(self):
        c = change({"low": 1, "high": 2}, {"low": 2, "high": 3})
        self.assertEqual((c["low"], c["high"], c["mid"], c["percent"]), (0, 2, 1, 66.7))
        self.assertEqual(c["direction"], "likely_increase")
        self.assertEqual(change({"low": 4, "high": 4}, {"low": 6, "high": 6})["direction"], "increase")
        dry = change({"low": 0, "high": 0}, {"low": 3, "high": 3})
        self.assertEqual(dry["direction"], "dry_to_flowing")
        self.assertIsNone(dry["percent"])

    def test_dry_spring_that_flows_is_a_change(self):
        s = self.site()
        self.visit(s, "2024-05-01", {"status": "dry"})
        self.visit(s, "2025-05-01", {"status": "measured", "readings": reading(5), "capture": "full", "point": "outlet"})
        a = assess(self.db.state())["sites"][0]
        self.assertTrue(a["comparison"]["dry_to_flowing"])
        self.assertEqual(a["comparison"]["after_lpm"], 5)

    def test_before_after_from_visits_and_di_year(self):
        s = self.site(di_year=2024)
        self.visit(s, "2023-05-01", {"status": "measured", "readings": reading(2), "capture": "full", "point": "o"})
        self.visit(s, "2025-05-01", {"status": "measured", "readings": reading(5), "capture": "full", "point": "o"})
        r = assess(self.db.state())["sites"][0]["impact"]["spring_before_after"]
        self.assertEqual((r["before"]["mid"], r["after"]["mid"]), (2, 5))
        self.assertEqual(r["metric"], "lean_flow_lpm")
        self.assertEqual(r["change"]["direction"], "increase")

    def test_period_entered_on_the_visit_wins(self):
        s = self.site()
        self.visit(s, "2025-04-01", {"status": "dry"}, period="before_di")
        self.visit(s, "2025-05-01", {"status": "measured", "readings": reading(1), "capture": "full", "point": "o"})
        r = assess(self.db.state())["sites"][0]["impact"]["spring_before_after"]
        self.assertEqual(r["change"]["direction"], "dry_to_flowing")

    def test_disconnected_and_additional_handpump(self):
        s = validate_site(
            dict(name="S", spring_name="S", handpump_name="HP 1", village="V", district="D", gps_later=True,
                 link_basis="reported", additional_handpumps=[{"name": "HP 2", "roof_area_m2": "100"}])
        )
        self.db.save_site(s)
        self.assertEqual(s["additional_handpumps"][0]["roof_area_m2"], 100)
        self.visit(s, "2025-05-01", {"status": "dry"}, pump="broken", di="disconnected", pump_asset_name="HP 2")
        a = assess(self.db.state())["sites"][0]
        hp2 = next(e for e in a["equipment"] if e["name"] == "HP 2")
        self.assertEqual(hp2["di_status"], "disconnected")
        self.assertIn("HP 2: DI line disconnected", a["maintenance"])
        with self.assertRaises(Invalid):
            self.visit(s, "2025-06-01", {"status": "dry"}, pump_asset_name="Unknown pump")

    def test_watsan_data_file_import(self):
        self.assertTrue(watsan_import.load(self.db))
        self.assertFalse(watsan_import.load(self.db))  # unchanged file: no second import
        result = assess(self.db.state())
        sites = {s["id"]: s for s in self.db.state()["sites"]}
        self.assertEqual(len(sites), 9)
        by_id = {a["site_id"]: a for a in result["sites"]}
        balench = by_id["wdi-01"]["impact"]
        self.assertEqual(balench["spring_before_after"]["metric"], "lean_flow_lpm")
        self.assertEqual(balench["spring_before_after"]["change"]["mid"], 1.5)
        self.assertEqual(balench["handpumps_before_after"][0]["outcome"], "restored")
        self.assertGreater(balench["di_water"]["volume_m3"], 0)
        # Arakot 2 is linked to Balench and Paniyar Dhar; its water is counted once in the total.
        self.assertEqual(by_id["wdi-06"]["impact"]["handpumps_before_after"][0]["name"], "Arakot 2")
        # Last two readings: after-DI dry (10) then after-DI monsoon (17) for Malani.
        malani = by_id["wdi-04"]["impact"]["last_two"]
        self.assertEqual((malani["before"]["mid"], malani["after"]["mid"]), (10, 17))
        self.assertEqual(len(malani["sequence"]), 3)
        # Kaddukhal is broken now (Rajat, 2026-10-24); its remark says so.
        kaddukhal = by_id["wdi-03"]["impact"]["handpumps_before_after"][0]
        self.assertEqual((kaddukhal["outcome"], kaddukhal["after"]), ("not_working_now", "broken"))
        self.assertIn("broken", kaddukhal["remarks"])
        self.assertTrue(by_id["wdi-02"]["impact"]["beyond_water"]["story"])
        p = result["portfolio"]["impact"]
        self.assertEqual(p["di_sites"], 9)
        self.assertEqual(p["pumps_restored"], 8)
        # Water injected follows the planner: collected = roof x rain used x 0.8, injected = x 0.85,
        # reaching = injected x share x depth factor.
        w = balench["di_water"]
        arakot1 = w["rows"][0]
        self.assertAlmostEqual(arakot1["collected_m3"], 150 * w["rain_used_mm"] / 1000 * 0.8, places=0)
        self.assertAlmostEqual(arakot1["volume_m3"], arakot1["collected_m3"] * 0.85, places=0)
        self.assertAlmostEqual(arakot1["reaching_m3"][1], arakot1["volume_m3"] * 0.15, places=0)
        self.assertFalse(arakot1["online"])  # roof pipe broken
        self.assertEqual(p["di_offline"], ["Arakot 1", "Chopriyal 2"])
        f = result["portfolio"]["follow_up"]
        self.assertEqual([n["handpump"] for n in f["handpumps"]["needs_work"]], ["Kaddukhal"])
        self.assertEqual({n["handpump"] for n in f["di_lines"]["needs_work"]}, {"Arakot 1", "Chopriyal 2"})
        self.assertEqual(f["handpumps"]["checked"] + f["handpumps"]["not_checked"], 9)  # Arakot 2 counted once
        self.assertLess(p["di_reaching_now_m3"][1], p["di_reaching_m3"][1])
        # Arakot 2 (linked to two springs) is counted once in the total.
        per_site = sum(a["impact"]["di_water"].get("volume_m3") or 0 for a in result["sites"])
        arakot2 = by_id["wdi-06"]["impact"]["di_water"]["volume_m3"]
        self.assertLess(abs(p["di_volume_m3"] - (per_site - arakot2)), 2)

    def test_portal_edit_survives_reimport(self):
        watsan_import.load(self.db)
        old = next(s for s in self.db.state()["sites"] if s["id"] == "wdi-02")
        edited = validate_site({**old, "households": 30}, old)
        self.db.save_site(edited)
        self.db.import_records("changed", *watsan_import.build()[1:])
        site = next(s for s in self.db.state()["sites"] if s["id"] == "wdi-02")
        self.assertEqual(site["households"], 30)
        self.assertEqual(site["handpumps"][0]["id"], "FV26-DI-CHP1")


if __name__ == "__main__":
    unittest.main()
