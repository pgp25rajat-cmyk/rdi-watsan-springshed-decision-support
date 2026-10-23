"""Tests for Module A's output under the shared module contract. No map layers needed.

Run: python -m pytest tests
"""

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import module_a_vulnerability as module_a  # noqa: E402

EXAMPLE_ID = "ATL-SPR-0199"  # Kimi Nauli, Nainital: an input spring at 1,197 m


class DatasetSession:
    """Stands in for the map layers: returns the dataset's feature row for the example spring."""

    def __init__(self):
        self.row = next(r for r in module_a.read_csv(module_a.FEATURES_CSV) if r["record_id"] == EXAMPLE_ID)
        self.indicators = module_a.load_indicators()
        self.reference, _ = module_a.load_reference()

    def features(self, lat, lon, elevation):
        return {k: v for k, v in self.row.items() if v not in ("", None)}


@pytest.fixture(scope="module")
def session():
    return DatasetSession()


def spring_input(**field):
    return {"spring": {"name": "Kimi Nauli", "latitude": 29.23016, "longitude": 79.63362, "elevation_m": 1197.1}, "field": field}


def test_location_only_is_low_confidence_exposure_score(session):
    out = module_a.assess(spring_input(), session)
    assert out["module"] == "A"
    assert set(out) >= {"spring", "result", "confidence", "rationale", "missing_inputs", "warnings", "report_markdown"}
    assert 0 <= out["result"]["score"] <= 100
    assert out["confidence"] == "Low"
    assert out["missing_inputs"][0]["id"] == "flow_vs_past"
    assert "exposure score" in out["report_markdown"]
    assert out["status"] == "provisional"


def test_field_answers_raise_confidence_and_floor_rule(session):
    out = module_a.assess(spring_input(flow_vs_past="dries_at_times", lean_flow_lpm=0, monsoon_flow_lpm=20, households=30,
                                       low_flow_months=4, users_vs_past="more"), session)
    assert out["result"]["class"] in ("Medium", "High")
    assert out["confidence"] in ("Medium", "High")
    assert out["status"] in ("complete", "provisional")
    assert any(i["id"] == "flow_vs_past" and i["score"] == 100 for i in out["result"]["indicators"])


def test_bad_answer_is_reported_not_scored(session):
    out = module_a.assess(spring_input(flow_vs_past="sometimes"), session)
    assert not any(i["id"] == "flow_vs_past" for i in out["result"]["indicators"])
    assert any("flow_vs_past" in w for w in out["warnings"])


def test_validation_scores_without_the_outcome_and_logs_repeat_looks(tmp_path, monkeypatch):
    import module_a_checks as checks
    monkeypatch.setattr(checks, "OUT", tmp_path)
    ids = [r["record_id"] for r in module_a.read_csv(module_a.INPUT_CSV)[:40]
           if r["coordinate_status"] == "ok"][:6]
    path = tmp_path / "springs.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "record_id", "decline_label", "flow_vs_past"])
        labels = [("declining", ""), ("steady", ""), ("", "much_less"), ("", "same"), ("", "a_bit_less"), ("", "")]
        for i, (record_id, (label, trend)) in enumerate(zip(ids, labels)):
            writer.writerow([f"spring {i}", record_id, label, trend])
    results = checks.validate(path, None, None)
    assert len(results) == 5  # the row with no outcome is skipped
    assert sum(r["a_bit_less"] for r in results) == 1
    assert all("flow_vs_past" not in r for r in results)
    checks.validate(path, None, None)
    assert len(module_a.read_csv(tmp_path / "validation_log.csv")) == 2
    assert any("checked before" in p.read_text() for p in tmp_path.glob("validation_*.txt"))


def test_any_dry_month_scores_and_new_questions():
    """Rajat 2026-10-23: even one month with no flow scores (never 0); disaster and existing works are asked."""
    answers, problems = module_a.clean_answers({"low_flow_months": 0, "dry_months": 1, "disaster_prone": "major",
                                                "existing_interventions": "trenches, pits", "recharge_works": "neglected"})
    assert not problems and answers["existing_interventions"] == ["trenches", "pits"]
    scores = module_a.field_scores(answers)
    assert scores["low_flow_months"][0] == 75
    assert scores["disaster_prone"][0] == 100
    assert scores["recharge_works"][0] == 50 and "contour trenches" in scores["recharge_works"][1]
    assert module_a.field_scores({"low_flow_months": 1})["low_flow_months"][0] == 25
    assert module_a.field_scores({"low_flow_months": 2, "dry_months": 3})["low_flow_months"][0] == 100
    assert module_a.field_scores({"existing_interventions": ["none"]})["recharge_works"][0] == 100


def test_weights_follow_rajat_2026_10_23():
    w = {k: v["weight"] for k, v in module_a.load_indicators().items()}
    assert (w["flow_vs_past"], w["lean_flow"], w["low_flow_months"], w["disaster_prone"]) == (10, 10, 13, 2)
    assert sum(w.values()) == 100


def test_landslide_band_and_plain_summary():
    assert module_a.landslide_band({"landslide_count_500m": "0", "landslide_distance_m": "900"})[0] == 0
    assert module_a.landslide_band({"landslide_count_500m": "2", "landslide_distance_m": "300"})[0] == 50
    assert module_a.landslide_band({"landslide_count_500m": "1", "landslide_distance_m": "0"})[0] == 100
    assert module_a.landslide_band({}) is None
    session = DatasetSession()
    row = session.row
    out = module_a.assess({"spring": {"latitude": float(row["latitude_dd"]), "longitude": float(row["longitude_dd"]),
                                      "elevation_m": 1197}, "field": {"flow_vs_past": "same", "lean_flow_lpm": 8}}, session)
    assert out["summary"][0].startswith("This spring has a ") and "because" in out["summary"][0]
    assert out["rationale"][: len(out["summary"])] == out["summary"]
