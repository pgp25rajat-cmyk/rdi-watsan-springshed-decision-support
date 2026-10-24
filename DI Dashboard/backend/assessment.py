"""Separate spring, handpump and DI results; documented arithmetic, no composite score."""

import re
from math import radians, sin, cos, asin, sqrt
from .rules import active_visits, rainfall_location

METHOD_VERSION = "3.0"
INDICATORS = [
    {
        "id": "spring_flow",
        "asset": "spring",
        "name": "Spring discharge",
        "unit": "L/min",
        "formula": "Q = (60V₁/t₁ + 60V₂/t₂ + 60V₃/t₃) / 3",
        "weights": "Each of three repeat readings has weight 1/3. These are repeat measurements, not impact domains.",
        "needs": "Three litres/seconds readings at one outlet; full or partial capture stated.",
        "missing": "Keep an estimate/range as reported; do not manufacture raw readings.",
        "interpretation": "Current availability at the visit, not annual yield or additional DI water.",
    },
    {
        "id": "spring_change",
        "asset": "spring",
        "name": "Change in spring flow",
        "unit": "L/min and %",
        "formula": "ΔQ = Qlater − Qearlier; change % = 100 × ΔQ / Qearlier",
        "weights": "No weighting. Direct difference of comparable observations.",
        "needs": "Same spring, season, outlet, method and full capture; exact dates. Current visit must be suitable too.",
        "missing": "No matched baseline means change is unavailable. Percent from a zero baseline is undefined.",
        "interpretation": "Observed change. Rainfall, other works and aquifer conditions may also explain it.",
    },
    {
        "id": "pump_delivery",
        "asset": "handpump",
        "name": "Handpump delivery and change",
        "unit": "L/min and %",
        "formula": "Delivery = mean(60Vᵢ/tᵢ); Δdelivery = later − earlier",
        "weights": "Repeat readings each 1/3. No weight shared with spring flow.",
        "needs": "Same handpump, pumping procedure and season; three delivery readings.",
        "missing": "Working does not imply a measured yield. Broken is not interpreted as aquifer dryness.",
        "interpretation": "Water delivered by the pump under the recorded test procedure.",
    },
    {
        "id": "pump_recovery",
        "asset": "handpump",
        "name": "Handpumps restored",
        "unit": "count",
        "formula": "Count assets with an earlier broken/no-water check and a later working check",
        "weights": "One count per handpump, once.",
        "needs": "Two dated checks of the same handpump; latest check working.",
        "missing": "One working visit alone cannot establish restoration.",
        "interpretation": "A functional recovery; repairs or other work may be responsible.",
    },
    {
        "id": "di_function",
        "asset": "di",
        "name": "DI lines connected",
        "unit": "count and % of checked",
        "formula": "100 × connected lines / lines with connected, broken, blocked or disconnected checks",
        "weights": "Each checked DI line counts equally. Not checked is excluded and shown separately.",
        "needs": "Latest DI condition per linked handpump.",
        "missing": "Never count an unchecked line as connected or failed.",
        "interpretation": "Operational status of the recharge connection, not measured injection volume.",
    },
    {
        "id": "maintenance",
        "asset": "di",
        "name": "Maintenance needs",
        "unit": "count",
        "formula": "Count sites with a broken pump, broken/blocked/disconnected DI line, or a first-flush/filter/overflow check marked needs work or missing",
        "weights": "No score or trade-off between safety checks. Count each affected site once.",
        "needs": "Latest field checks, displayed with their date.",
        "missing": "Unknown safety checks remain unknown. A connected line is not a safe-to-inject certificate.",
        "interpretation": "A work list, not a weighted impact index.",
    },
    {
        "id": "quality_change",
        "asset": "both",
        "name": "Water-test change",
        "unit": "Original parameter unit",
        "formula": "ΔC = later result − earlier result; show both dates, locations and test method",
        "weights": "No weighting across parameters or between spring and handpump.",
        "needs": "Same parameter, sample asset/location, unit and kit/lab; exact dates.",
        "missing": "A colour/iron account cannot be converted into mg/L or treated as a lab test.",
        "interpretation": "A measured difference, not a potability decision. pH is not treated as a concentration percentage.",
    },
    {
        "id": "rainfall",
        "asset": "context",
        "name": "Rain before each visit",
        "unit": "mm / 90 days",
        "formula": "P90 = sum of 90 consecutive available daily rain values ending the day before the visit",
        "weights": "No statistical weights. Each day contributes its recorded rainfall.",
        "needs": "Complete ERA5 date coverage; handpump coordinates preferred, spring proxy labelled.",
        "missing": "A missing day makes the total unavailable; it is not zero-filled.",
        "interpretation": "Regional weather context. It cannot isolate DI’s causal contribution.",
    },
    {
        "id": "roof",
        "asset": "di",
        "name": "Roof collection potential",
        "unit": "m³",
        "formula": "Vpotential = rainfall(mm) × roof area(m²) × collection factor / 1000",
        "weights": "Collection factor is a stated roof/runoff assumption, not an impact weight.",
        "needs": "Recorded roof area, justified collection factor, complete rainfall period.",
        "missing": "No assumed roof area or default collection factor.",
        "interpretation": "Water that could be collected; not actual injected water, recharge or spring-flow gain.",
    },
    {
        "id": "households",
        "asset": "village",
        "name": "Households recorded",
        "unit": "households",
        "formula": "Use the one-time site count; portfolio household total is not summed without checking overlap",
        "weights": "No weighting. No repeated count at every visit.",
        "needs": "Site household count and a clear service area.",
        "missing": "Unknown stays blank, never zero.",
        "interpretation": "Reported reach, not additional beneficiaries caused by DI.",
    },
    {
        "id": "village",
        "asset": "village",
        "name": "Changes in village life",
        "unit": "dated accounts",
        "formula": "Record earlier → now, who/what was observed, related asset, source and other work",
        "weights": "No weights and no conversion of narratives to a numeric impact score. Repeated accounts are not new beneficiaries.",
        "needs": "Comparable follow-up on collection effort, hygiene, toilets, education, farming or livelihoods.",
        "missing": "Not discussed differs from no change. No short-term improvement is invented.",
        "interpretation": "Broader outcomes can follow combined water interventions; retain that context.",
    },
]


def distance(site):
    keys = ("latitude", "longitude", "pump_latitude", "pump_longitude")
    if any(site.get(k) is None for k in keys):
        return None
    a, b, c, d = map(lambda k: radians(site[k]), keys)
    return 6371000 * 2 * asin(min(1, sqrt(sin((c - a) / 2) ** 2 + cos(a) * cos(c) * sin((d - b) / 2) ** 2)))


def pump_comparison(visits):
    rows = [
        v
        for v in visits
        if v["pump"].get("flow_lpm") is not None and not v.get("date_accuracy") and v["pump"].get("measure")
    ]
    if not rows:
        return None
    current = rows[-1]
    if current["season"] == "unknown":
        return None
    old = next(
        (
            v
            for v in reversed(rows[:-1])
            if v["season"] == current["season"]
            and v["visit_date"] != current["visit_date"]
            and v["pump"].get("procedure") == current["pump"].get("procedure")
        ),
        None,
    )
    if not old:
        return None
    before, after = old["pump"]["flow_lpm"], current["pump"]["flow_lpm"]
    return {
        "before_id": old["id"],
        "after_id": current["id"],
        "before_date": old["visit_date"],
        "after_date": current["visit_date"],
        "before_lpm": before,
        "after_lpm": after,
        "difference_lpm": after - before,
        "percent": 100 * (after - before) / before if before else None,
    }


def enrich(state, results):
    active = active_visits(state["visits"])
    mapped = 0
    pump_mapped = 0
    for site, a in zip(state["sites"], results):
        rows = [v for v in active if v["site_id"] == site["id"]]
        normal = lambda name: re.sub(r"[^a-z0-9]", "", str(name).lower())
        pump_rows = [
            v
            for v in rows
            if not v.get("pump_asset_name")
            or normal(v["pump_asset_name"]) == normal(site.get("handpump_name"))
        ]
        latest = pump_rows[-1] if pump_rows else None
        equipment = []
        for p, is_primary in [
            (dict(name=site.get("handpump_name") or "DI handpump"), True),
            *[(p, False) for p in site.get("additional_handpumps", [])],
        ]:
            checks = (
                pump_rows
                if is_primary
                else [v for v in rows if normal(v.get("pump_asset_name")) == normal(p["name"])]
            )
            check = checks[-1] if checks else None
            equipment.append(
                {
                    "name": p["name"],
                    "primary": is_primary,
                    "pump_status": check["pump"]["status"] if check else "not_checked",
                    "di_status": check["di"]["status"] if check else "not_checked",
                    "visit_date": check["visit_date"] if check else None,
                    "visit_id": check["id"] if check else None,
                }
            )

        flows = [v for v in pump_rows if v["pump"].get("flow_lpm") is not None]
        known = [v for v in pump_rows if v["pump"].get("status") in ("working", "broken", "no_water")]
        restored = bool(
            known
            and known[-1]["pump"]["status"] == "working"
            and any(
                v["pump"]["status"] in ("broken", "no_water") and v["visit_date"] < known[-1]["visit_date"]
                for v in known[:-1]
            )
        )
        reasons = []
        if latest:
            if latest["pump"]["status"] in ("broken", "no_water"):
                reasons.append("Handpump " + latest["pump"]["status"].replace("_", " "))
            if latest["di"]["status"] in ("broken", "blocked", "disconnected"):
                reasons.append("DI line " + latest["di"]["status"])
            for k in ("filter", "first_flush", "overflow"):
                if latest.get("safety", {}).get(k) in ("needs_work", "missing"):
                    reasons.append(
                        k.replace("_", " ").capitalize() + ": " + latest["safety"][k].replace("_", " ")
                    )
        qchanges = []
        for v in rows:
            for t in v["tests"]:
                old = next(
                    (
                        (p, pt)
                        for p in reversed(rows)
                        if p["visit_date"] < v["visit_date"]
                        and not p.get("date_accuracy")
                        and not v.get("date_accuracy")
                        for pt in p["tests"]
                        if (pt["parameter"], pt["sample_point"], pt["method"], pt["unit"])
                        == (t["parameter"], t["sample_point"], t["method"], t["unit"])
                    ),
                    None,
                )
                if old:
                    qchanges.append(
                        {
                            "parameter": t["parameter"],
                            "sample_point": t["sample_point"],
                            "unit": t["unit"],
                            "before": old[1]["value"],
                            "after": t["value"],
                            "difference": t["value"] - old[1]["value"],
                            "before_date": old[0]["visit_date"],
                            "after_date": v["visit_date"],
                        }
                    )
        for item in equipment:
            if not item["primary"] and item["di_status"] in ("broken", "blocked", "disconnected"):
                reasons.append(item["name"] + ": DI line " + item["di_status"])
        gap = distance(site)
        notes = list(site.get("evidence_notes", []))
        if gap is not None and gap > 5000:
            notes.append(
                "Spring and handpump coordinates are more than 5 km apart. Check the source coordinates and asset link; distance alone does not establish connection."
            )
        a.update(
            spring={
                "flow_lpm": a["current_flow"],
                "flow_date": a["flow_date"],
                "comparison": a["comparison"],
                "reported_range": next(
                    (
                        v["spring"].get("reported_range")
                        for v in reversed(rows)
                        if v["spring"].get("reported_range")
                    ),
                    None,
                ),
            },
            handpump={
                "flow_lpm": flows[-1]["pump"]["flow_lpm"] if flows else None,
                "flow_date": flows[-1]["visit_date"] if flows else None,
                "comparison": pump_comparison(pump_rows),
                "status": latest["pump"]["status"] if latest else "not_checked",
                "restored": restored,
            },
            equipment=equipment,
            di_status=latest["di"]["status"] if latest else "not_checked",
            maintenance=reasons,
            quality_changes=qchanges,
            straight_distance_m=gap,
            rainfall_at=rainfall_location(site)["rainfall_at"],
            evidence_notes=notes,
            evidence_count=sum(e["site_id"] == site["id"] for e in state.get("evidence_records", [])),
        )
        mapped += site.get("latitude") is not None
        pump_mapped += (site.get("pump_latitude") is not None) + sum(
            p.get("latitude") is not None for p in site.get("additional_handpumps", [])
        )
    gear = [p for a in results for p in a["equipment"]]
    checked = [p for p in gear if p["di_status"] != "not_checked"]
    connected = sum(p["di_status"] == "connected" for p in checked)
    pump_checked = [p for p in gear if p["pump_status"] != "not_checked"]
    portfolio = {
        "sites": len(results),
        "visits": len(active),
        "springs_with_flow": sum(a["current_flow"] is not None for a in results),
        "spring_comparisons": sum(a["comparison"] is not None for a in results),
        "pump_comparisons": sum(a["handpump"]["comparison"] is not None for a in results),
        "pump_checked": len(pump_checked),
        "pump_working": sum(p["pump_status"] == "working" for p in pump_checked),
        "pump_restored": sum(a["handpump"]["restored"] for a in results),
        "di_checked": len(checked),
        "di_connected": connected,
        "di_connected_percent": 100 * connected / len(checked) if checked else None,
        "needs_work": sum(bool(a["maintenance"]) for a in results),
        "springs_mapped": mapped,
        "handpumps_mapped": pump_mapped,
        "evidence_records": len(state.get("evidence_records", [])),
        "lab_results": sum(a["quality_test_count"] for a in results),
    }
    return {
        "sites": results,
        "portfolio": portfolio,
        "version": METHOD_VERSION,
        "methodology": {
            "version": METHOD_VERSION,
            "composite_weights": None,
            "decision": "No composite impact index. Keep spring, handpump, DI operation and village outcomes separate.",
            "indicators": INDICATORS,
            "causal_contribution": "Not quantified without a suitable counterfactual/control design and sufficient repeated evidence.",
        },
    }
