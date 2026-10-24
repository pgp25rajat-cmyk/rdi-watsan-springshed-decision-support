"""Impact results: before vs after DI (primary), the last two records, and how much water DI could supply.

All values are ranges (low-high) because most WATSAN records are estimates or recalled ranges. A single measured
value is a range with low = high. Nothing is replaced by a midpoint except where a chart needs one point, and
the midpoint is labelled.

Change between two records (before B, after A):
    change range   = (A_low - B_high) to (A_high - B_low)
    change (mid)   = mid(A) - mid(B), where mid = (low + high) / 2
    change %       = 100 x change (mid) / mid(B); not given when B is 0 (a dry spring)
    direction      = increase if the whole change range is above 0, decrease if below 0,
                     likely increase / decrease if the ranges overlap but the midpoints moved,
                     "dry to flowing" if B was 0 and A is above 0, otherwise "no clear change"

DI water (planner Module C defaults, scripts/module_c_di_impact.py):
    injected per year V (m3) = roof area (m2) x annual rain (mm) x 0.8 collection x 0.85 injection / 1000
    as a steady flow (L/min) = V x 1000 / 525,600 minutes
    best case, all in the 5 lean months (L/min) = V x 1000 / (5 x 30.44 x 1,440)
    share of the spring gain DI could explain = DI steady flow / spring change (mid), shown only for a gain.
    This assumes every litre injected reaches this spring, so it is an upper limit.
"""

from datetime import date

COLLECTION = 0.8
INJECTION = 0.85
LEAN_MONTHS = 5
MINUTES_PER_YEAR = 525_600
BASIS_RANK = {"measured": 4, "observed": 4, "estimate": 3, "report": 2, "recall": 1}
BASIS_LABEL = {
    "measured": "Measured (bucket and stopwatch)",
    "observed": "Seen on the visit",
    "estimate": "Estimated by eye",
    "report": "Report value, method not stated",
    "recall": "What people recalled",
}
NOT_WORKING = ("defunct", "no_water", "no_water_dry_season", "broken")
SPRING_METRICS = [
    ("lean_flow_lpm", "Dry-season (lean) flow"),
    ("flow_lpm", "Flow on the day"),
]


def midpoint(o):
    return (o["low"] + o["high"]) / 2


def change(before, after):
    b_mid, a_mid = midpoint(before), midpoint(after)
    low, high = after["low"] - before["high"], after["high"] - before["low"]
    mid = a_mid - b_mid
    if before["high"] == 0 and after["low"] > 0:
        direction = "dry_to_flowing"
    elif before["high"] == 0 and after["high"] == 0:
        direction = "still_dry"
    elif low > 0:
        direction = "increase"
    elif high < 0:
        direction = "decrease"
    elif mid > 0:
        direction = "likely_increase"
    elif mid < 0:
        direction = "likely_decrease"
    else:
        direction = "no_clear_change"
    return {
        "low": round(low, 2),
        "high": round(high, 2),
        "mid": round(mid, 2),
        "percent": round(100 * mid / b_mid, 1) if b_mid > 0 else None,
        "direction": direction,
    }


def point(o):
    return {
        "id": o["id"],
        "record": o["record"],
        "record_label": o["record_label"],
        "date": o.get("date"),
        "low": o["low"],
        "high": o["high"],
        "mid": round(midpoint(o), 2),
        "basis": o["basis"],
        "basis_label": BASIS_LABEL.get(o["basis"], o["basis"]),
        "source": o.get("source", ""),
        "note": o.get("note", ""),
    }


def order_key(o):
    """Records sorted oldest first. Before-DI recall first; an undated report before any dated record."""
    if o["period"] == "before_di" and not o.get("date"):
        return (0, "")
    if not o.get("date"):
        return (1, o.get("record", ""))
    return (2, o["date"])


def install_year(site, asset_name):
    for h in site.get("handpumps") or []:
        if h.get("name") == asset_name and h.get("di_year"):
            return h["di_year"]
    for h in site.get("additional_handpumps") or []:
        if h.get("name") == asset_name and h.get("di_year"):
            return h["di_year"]
    return site.get("di_year")


def visit_period(site, visit, asset_name):
    """before_di / after_di for a portal visit: as entered, else from the DI year. With no DI year recorded the
    visit counts as after DI (these sites already have DI) and is flagged."""
    if visit.get("period") in ("before_di", "after_di"):
        return visit["period"], False
    year = install_year(site, asset_name)
    visit_year = date.fromisoformat(visit["visit_date"]).year
    if year:
        if visit_year > year:
            return "after_di", False
        if visit_year < year:
            return "before_di", False
        return "unclear", False
    return "after_di", True


def portal_observations(site, visits):
    """Turn portal visits (not the imported field visit) into the same observation rows as the data file."""
    rows = []
    for v in visits:
        if v.get("imported") or v["site_id"] != site["id"]:
            continue
        pump_name = v.get("pump_asset_name") or site.get("handpump_name")
        period, assumed = visit_period(site, v, pump_name)
        base = {
            "site_id": site["id"],
            "record": "portal_visit",
            "record_label": "Visit, " + v["visit_date"],
            "period": period,
            "period_assumed": assumed,
            "date": v["visit_date"],
            "source": "Portal visit by " + (v.get("visitor") or "the team"),
            "note": "",
            "visit_id": v["id"],
            "season": v.get("season"),
        }
        flow = v["spring"].get("flow_lpm")
        if flow is not None:
            rows.append(
                {
                    **base,
                    "id": v["id"] + "-flow",
                    "asset": "spring",
                    "asset_id": site["id"],
                    "metric": "lean_flow_lpm" if v.get("season") == "dry" else "flow_lpm",
                    "low": flow,
                    "high": flow,
                    "text": "",
                    "basis": "measured",
                    "note": "Spring found dry" if v["spring"].get("status") == "dry" else "",
                }
            )
            if v.get("season") == "dry":
                rows.append({**rows[-1], "id": v["id"] + "-flow-day", "metric": "flow_lpm"})
        if v["pump"].get("status") not in (None, "", "not_checked"):
            rows.append(
                {
                    **base,
                    "id": v["id"] + "-pump",
                    "asset": "handpump",
                    "asset_id": pump_name,
                    "metric": "pump_status",
                    "low": None,
                    "high": None,
                    "text": v["pump"]["status"],
                    "basis": "observed",
                }
            )
    return rows


def spring_before_after(obs):
    spring = [o for o in obs if o["asset"] == "spring" and o["low"] is not None]
    for metric, label in SPRING_METRICS:
        before = sorted([o for o in spring if o["metric"] == metric and o["period"] == "before_di"], key=order_key)
        after = sorted([o for o in spring if o["metric"] == metric and o["period"] == "after_di"], key=order_key)
        if before and after:
            b = before[-1]
            same_basis = [o for o in after if o["basis"] == b["basis"]]
            a = (same_basis or after)[-1]
            weakest = min((b, a), key=lambda o: BASIS_RANK.get(o["basis"], 0))
            return {
                "kind": "numeric",
                "metric": metric,
                "metric_label": label,
                "before": point(b),
                "after": point(a),
                "change": change(b, a),
                "evidence": weakest["basis"],
                "evidence_label": BASIS_LABEL.get(weakest["basis"], weakest["basis"]),
                "like_for_like": b["basis"] == a["basis"],
            }
    reported = sorted(
        [o for o in obs if o["asset"] == "spring" and o["metric"] == "reported_change"], key=order_key
    )
    if reported:
        r = reported[-1]
        return {
            "kind": "reported",
            "direction": r["text"],
            "evidence": r["basis"],
            "evidence_label": BASIS_LABEL.get(r["basis"], r["basis"]),
            "note": r["note"],
            "source": r["source"],
        }
    return None


def last_two(obs):
    flows = sorted(
        [o for o in obs if o["asset"] == "spring" and o["metric"] == "flow_lpm" and o["low"] is not None],
        key=order_key,
    )
    if len(flows) < 2:
        return None
    b, a = flows[-2], flows[-1]
    reasons = []
    if b["basis"] != a["basis"]:
        reasons.append(f"Different methods: {BASIS_LABEL.get(b['basis'], b['basis'])} vs {BASIS_LABEL.get(a['basis'], a['basis'])}.")
    if not b.get("date") or not a.get("date"):
        reasons.append("One record has no date or season, so the order and season are assumed.")
    elif b.get("season") and a.get("season") and b["season"] != a["season"]:
        reasons.append("Different seasons.")
    return {"before": point(b), "after": point(a), "change": change(b, a), "like_for_like": not reasons, "cautions": reasons}


def pump_before_after(site, obs):
    rows = []
    names = {h.get("id"): h.get("name") for h in site.get("handpumps") or []}
    pumps = site["handpumps"] if "handpumps" in site else (
        [{"id": site.get("handpump_name"), "name": site.get("handpump_name")}]
        + [{"id": p["name"], "name": p["name"]} for p in site.get("additional_handpumps") or []]
    )
    for h in pumps:
        mine = [
            o
            for o in obs
            if o["asset"] == "handpump" and o["metric"] == "pump_status" and o["asset_id"] in (h.get("id"), h.get("name"))
        ]
        before = sorted([o for o in mine if o["period"] == "before_di"], key=order_key)
        after = sorted([o for o in mine if o["period"] == "after_di" and o["text"] != "not_checked"], key=order_key)
        b = before[-1]["text"] if before else None
        a = after[-1]["text"] if after else None
        if b in NOT_WORKING and a == "working":
            outcome = "restored"
        elif b == "poor_quality" and a == "working":
            outcome = "improved"
        elif a in ("broken", "no_water"):
            outcome = "not_working_now"
        elif b and a:
            outcome = "no_change"
        else:
            outcome = "unknown"
        rows.append(
            {
                "name": h.get("name") or names.get(h.get("id")),
                "before": b,
                "before_note": before[-1]["note"] if before else "",
                "after": a,
                "after_date": after[-1].get("date") if after else None,
                "outcome": outcome,
                "evidence": "recall" if before else None,
            }
        )
    return rows


def di_water(site, spring_result):
    rain = site.get("annual_rain_mm")
    pumps = site["handpumps"] if "handpumps" in site else (
        [{"name": site.get("handpump_name"), "roof_area_m2": site.get("roof_area_m2")}]
        + list(site.get("additional_handpumps") or [])
    )
    rows = []
    for h in pumps:
        roof = h.get("roof_area_m2")
        if not roof or not rain:
            rows.append({"name": h.get("name"), "roof_area_m2": roof, "volume_m3": None})
            continue
        volume = roof * rain * COLLECTION * INJECTION / 1000
        rows.append({"name": h.get("name"), "roof_area_m2": roof, "volume_m3": round(volume, 1)})
    known = [r for r in rows if r["volume_m3"] is not None]
    if not known:
        return {"available": False, "rows": rows, "annual_rain_mm": rain,
                "reason": "Roof area or annual rainfall is not recorded." if rows else "No DI handpump at this site."}
    volume = sum(r["volume_m3"] for r in known)
    steady = volume * 1000 / MINUTES_PER_YEAR
    lean = volume * 1000 / (LEAN_MONTHS * 30.44 * 1440)
    result = {
        "available": True,
        "rows": rows,
        "missing_roofs": [r["name"] for r in rows if r["volume_m3"] is None],
        "annual_rain_mm": rain,
        "annual_rain_source": site.get("annual_rain_source", ""),
        "collection": COLLECTION,
        "injection": INJECTION,
        "volume_m3": round(volume, 1),
        "steady_lpm": round(steady, 2),
        "lean_lpm": round(lean, 2),
        "share_of_gain_pct": None,
    }
    if spring_result and spring_result.get("kind") == "numeric" and spring_result["change"]["mid"] > 0:
        result["share_of_gain_pct"] = round(100 * steady / spring_result["change"]["mid"])
        result["gain_metric"] = spring_result["metric_label"]
    return result


def site_impact(site, state):
    obs = [o for o in state.get("source_observations", []) if o["site_id"] == site["id"]]
    active = [v for v in state["visits"] if v["status"] == "submitted"]
    obs += portal_observations(site, active)
    spring = spring_before_after(obs)
    return {
        "role": site.get("role") or "DI site",
        "spring_before_after": spring,
        "last_two": last_two(obs),
        "handpumps_before_after": pump_before_after(site, obs),
        "di_water": di_water(site, spring),
        "records": sorted(
            [
                {**point(o), "metric": o["metric"], "period": o["period"]}
                for o in obs
                if o["asset"] == "spring" and o["low"] is not None
            ],
            key=lambda o: order_key({"period": o["period"], "date": o["date"], "record": o["record"]}),
        ),
        "period_assumed": any(o.get("period_assumed") for o in obs),
    }


def portfolio(impacts):
    di_sites = [i for i in impacts if not i["role"].lower().startswith("comparison")]
    numeric = [i["spring_before_after"] for i in di_sites if (i["spring_before_after"] or {}).get("kind") == "numeric"]
    reported = [i["spring_before_after"] for i in di_sites if (i["spring_before_after"] or {}).get("kind") == "reported"]
    pumps = [p for i in di_sites for p in i["handpumps_before_after"]]
    water = [i["di_water"] for i in di_sites if i["di_water"]["available"]]
    return {
        "di_sites": len(di_sites),
        "comparison_sites": len(impacts) - len(di_sites),
        "spring_numeric": len(numeric),
        "spring_numeric_up": sum(
            r["change"]["direction"] in ("increase", "likely_increase", "dry_to_flowing") for r in numeric
        ),
        "spring_reported": len(reported),
        "spring_reported_up": sum(r["direction"] == "increase" for r in reported),
        "spring_reported_same": sum(r["direction"] == "same" for r in reported),
        "spring_no_data": len(di_sites) - len(numeric) - len(reported),
        "pumps": len(pumps),
        "pumps_with_before": sum(p["before"] is not None for p in pumps),
        "pumps_restored": sum(p["outcome"] == "restored" for p in pumps),
        "pumps_improved": sum(p["outcome"] == "improved" for p in pumps),
        "pumps_not_working": sum(p["outcome"] == "not_working_now" for p in pumps),
        "last_two": sum(i["last_two"] is not None for i in impacts),
        "di_volume_m3": round(sum(w["volume_m3"] for w in water), 1),
        "di_sites_with_volume": len(water),
    }


INDICATORS = [
    {
        "id": "before_after",
        "asset": "spring",
        "name": "Spring flow before vs after DI",
        "unit": "L/min and %",
        "formula": "Change = after − before. Range: (after_low − before_high) to (after_high − before_low). "
        "Change % = 100 × (mid_after − mid_before) / mid_before",
        "weights": "No weights. Dry-season (lean) flow is used first because DI should matter most when rain stops; "
        "flow on the day is used when no lean-flow pair exists.",
        "needs": "A before-DI value and an after-DI value for the same spring and metric. Same basis preferred "
        "(recall with recall, measured with measured).",
        "missing": "With no numbers, the direction people reported (more / same / less) is shown instead. A dry "
        "spring that now flows is shown as 'dry to flowing'; % is not given from a zero baseline.",
        "interpretation": "Primary impact result. Before-DI values are recall, so treat it as an indication. "
        "Rain, other recharge works and solar pumping can also change flow.",
    },
    {
        "id": "last_two",
        "asset": "spring",
        "name": "Change between the last two records",
        "unit": "L/min and %",
        "formula": "Same change formula, using the two most recent spring-flow records of any kind",
        "weights": "No weights.",
        "needs": "Two spring-flow records. An undated report is placed before any dated visit.",
        "missing": "Shown with cautions when the methods or seasons differ, or a date is missing.",
        "interpretation": "Shows the latest movement. It becomes like-for-like once two portal visits in the same "
        "season exist.",
    },
    {
        "id": "pump_before_after",
        "asset": "handpump",
        "name": "Handpump condition before vs after DI",
        "unit": "count",
        "formula": "Restored = defunct / no water / broken before DI and working after. "
        "Improved = working with poor water before and working after.",
        "weights": "One count per handpump.",
        "needs": "What the handpump was like before DI (recall) and its condition on the latest visit.",
        "missing": "No before-DI account: outcome unknown, not counted as restored.",
        "interpretation": "DI's most direct effect: a defunct handpump given water again.",
    },
    {
        "id": "di_water",
        "asset": "di",
        "name": "Water DI can put into the ground",
        "unit": "m³ a year and L/min",
        "formula": "V = roof area × annual rain × 0.8 × 0.85 / 1000; steady flow = V × 1000 / 525,600; "
        "lean-season best case = V × 1000 / (5 × 30.44 × 1,440)",
        "weights": "0.8 = share of roof rain collected (RDI design 0.7-0.8); 0.85 = share injected after first "
        "flush, overflow and clogging. Same defaults as the planner.",
        "needs": "Roof area per handpump (field form) and annual rain at the spring (CHIRPS 2018-2025, as the planner).",
        "missing": "No roof area: no estimate for that handpump.",
        "interpretation": "An upper limit on the water DI adds, not measured injection.",
    },
    {
        "id": "share_explained",
        "asset": "di",
        "name": "Share of the spring gain DI could explain",
        "unit": "%",
        "formula": "100 × DI steady flow / spring change (mid)",
        "weights": "Assumes every injected litre reaches this spring, so this is the most DI could explain.",
        "needs": "A numeric before/after gain and a DI water estimate.",
        "missing": "Not shown when the spring did not gain or there is no estimate.",
        "interpretation": "Below 100% means DI alone cannot account for the whole gain; rain or other works "
        "also played a part. Above 100% means DI could cover it if the link is real.",
    },
]
