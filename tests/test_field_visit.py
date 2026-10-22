"""Tests for the October 2026 field-visit tables. No map layers needed.

Run: python -m pytest tests
"""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_field_visit as fv  # noqa: E402


def read(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize("total, band", [(10, "Low"), (14, "Low"), (15, "Medium"), (20, "Medium"), (21, "High"), (30, "High")])
def test_screen_bands_follow_rajats_cutoffs(total, band):
    assert fv.screen_band(total) == band


def test_flow_from_bucket_readings():
    mean, low, high = fv.flow_from_readings([{"litres": "2", "seconds": "5"}, {"litres": "2", "seconds": "6"}])
    assert (round(mean, 2), low, high) == (22.0, 20.0, 24.0)


def test_every_spring_has_a_full_screen_and_known_links():
    springs = read(fv.SPRINGS_CSV)
    totals = fv.screen_totals(read(fv.SCORES_CSV))
    assert {s["field_site_id"] for s in springs} == set(totals)
    for site, t in totals.items():
        assert 10 <= t["screen_team_total"] <= 30 and 10 <= t["screen_recomputed_total"] <= 30, site
        if t["screen_team_total_written"]:
            assert int(t["screen_team_total_written"]) == t["screen_team_total"], site
    master_ids = {r["record_id"] for r in read(fv.MASTER_CSV)}
    di_ids = {d["di_site_id"] for d in read(fv.DI_CSV)}
    for s in springs:
        assert not s["dataset_spring_id"] or s["dataset_spring_id"] in master_ids, s["field_site_id"]
        for di in filter(None, s["linked_di_site_ids"].split(";")):
            assert di in di_ids, (s["field_site_id"], di)
        assert s["district"] == "Tehri Garhwal"  # all field springs are test data
    for d in read(fv.DI_CSV):
        assert not d["linked_dataset_spring_id"] or d["linked_dataset_spring_id"] in master_ids, d["di_site_id"]


def test_recomputed_scores_only_differ_with_a_reason():
    for row in read(fv.SCORES_CSV):
        if row["team_score"] != row["recomputed_score"]:
            assert row["recompute_note"], row


def test_master_uses_field_gps_and_form_flows():
    master = {r["record_id"]: r for r in read(fv.MASTER_CSV)}
    flows = {r["field_site_id"]: r for r in read(fv.OUT_DIR / "field_visit_springs_v1.csv")}
    for s in read(fv.SPRINGS_CSV):
        record = master[s["dataset_spring_id"]] if s["dataset_spring_id"] else next(
            r for r in master.values() if r["record_id"].startswith("FLD-") and r["spring_name"] == s["spring_name"])
        assert (float(record["latitude"]), float(record["longitude"])) == (float(s["latitude"]), float(s["longitude"])), s["field_site_id"]
        assert record["dataset_split"] == "test", s["field_site_id"]
        measured = flows[s["field_site_id"]]["flow_today_lpm"]
        if measured:
            assert float(record["discharge_lpm_low"]) == pytest.approx(float(measured), abs=0.05), s["field_site_id"]
        elif s["flow_today_lpm_low"]:
            assert float(record["discharge_lpm_low"]) == float(s["flow_today_lpm_low"]), s["field_site_id"]
