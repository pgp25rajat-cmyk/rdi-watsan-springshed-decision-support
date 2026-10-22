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


def test_recomputed_scores_only_differ_with_a_reason():
    for row in read(fv.SCORES_CSV):
        if row["team_score"] != row["recomputed_score"]:
            assert row["recompute_note"], row
