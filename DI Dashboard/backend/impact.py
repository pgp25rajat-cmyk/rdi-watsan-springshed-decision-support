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

Water injected (the planner's Module C method, scripts/module_c_di_impact.py), per DI handpump:
    rain used (mm)        = annual rain (IMD gauges, else CHIRPS) + 0.5 x winter snow at the spring's height
    rain collected (m3)   = roof area (m2) x rain used / 1000 x 0.8 (gutter, pipe and splash losses)
    injected (m3)         = rain collected x 0.85 (first flush, overflow, downtime, clogging)
    reaching spring (m3)  = injected x share x depth factor
        share (low / mid / best case): 0.30/0.60/1.00 in a recharge zone on the spring's slope, 0.10/0.30/0.60 in a zone
        linked by a fault or rock tilt, 0.05/0.20/0.50 by a crack, 0.05/0.15/0.30 elsewhere in the catchment,
        0/0.02/0.10 outside it, 0 below the spring
        depth factor: injection point (handpump ground - depth, 70 m if not known) against the spring outlet:
        x1.0 more than 10 m above, x0.7 within 10 m, x0.4 up to 50 m below, x0.2 deeper
    added spring flow (L/min) = reaching x 1000 / 525,600 (spread over the year), or
                                reaching x 1000 / (5 x 30.44 x 1,440) (best case: all in the 5 lean months)
    "now" counts only handpumps whose DI line is not disconnected or broken.
    share of the spring gain DI could explain = lean-season added flow (mid) / spring change (mid).
"""

from datetime import date

COLLECTION = 0.8
INJECTION = 0.85
LEAN_MONTHS = 5
SNOW_CAPTURE = 0.5
DEFAULT_DEPTH_M = 70
SHARE = {
    "in_zone_slope": (0.3, 0.6, 1.0),
    "in_zone_linked": (0.1, 0.3, 0.6),
    "in_zone_crack": (0.05, 0.2, 0.5),
    "in_catchment": (0.05, 0.15, 0.3),
    "outside": (0.0, 0.02, 0.1),
    "below_spring": (0.0, 0.0, 0.0),
}
SHARE_LABEL = {
    "in_zone_slope": "In a recharge zone on the spring's slope",
    "in_zone_linked": "In a recharge zone linked by a fault or rock tilt",
    "in_zone_crack": "In a recharge zone linked by a crack",
    "in_catchment": "In the spring's catchment",
    "outside": "Outside the spring's catchment",
    "below_spring": "Below the spring",
}
DEPTH_FACTOR = [
    (10, 1.0, "above the spring outlet"),
    (-10, 0.7, "about level with the spring outlet"),
    (-50, 0.4, "below the spring outlet"),
    (-1e9, 0.2, "far below the spring outlet"),
]
OFF_LINE = ("disconnected", "broken")
MINUTES_PER_YEAR = 525_600
LEAN_MINUTES = LEAN_MONTHS * 30.44 * 1440
BASIS_RANK = {"measured": 4, "observed": 4, "agreed": 3, "estimate": 3, "report": 2, "recall": 1}
BASIS_LABEL = {
    "measured": "Measured (bucket and stopwatch)",
    "observed": "Seen on the visit",
    "estimate": "Estimated by eye",
    "report": "Report value, method not stated",
    "recall": "What people recalled",
    "agreed": "Team value (RDI reports and field forms)",
}
NOT_WORKING = ("defunct", "no_water", "no_water_dry_season", "broken")
SPRING_METRICS = [
    ("lean_flow_lpm", "Dry-season spring flow"),
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
    elif low == high == 0:
        direction = "no_change"
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
                "monsoon_after": next(
                    (
                        point(o)
                        for o in sorted(spring, key=order_key)[::-1]
                        if o["metric"] == "monsoon_flow_lpm" and o["period"] == "after_di"
                    ),
                    None,
                ),
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


SEQUENCE_LABELS = {
    ("before_di", "lean_flow_lpm"): "Before DI · dry season",
    ("after_di", "lean_flow_lpm"): "After DI · dry season",
    ("after_di", "monsoon_flow_lpm"): "After DI · monsoon",
}


def last_two(obs):
    """Readings in order (Rajat, 2026-10-24): before-DI dry flow first, after-DI dry flow next, after-DI monsoon
    flow latest; any later portal visit follows. The last two are compared."""
    spring = [o for o in obs if o["asset"] == "spring" and o["low"] is not None]
    agreed = {
        (o["period"], o["metric"]): o
        for o in spring
        if o["basis"] == "agreed" and (o["period"], o["metric"]) in SEQUENCE_LABELS
    }
    if agreed:
        seq = [
            {**point(agreed[k]), "record_label": label}
            for k, label in SEQUENCE_LABELS.items()
            if k in agreed
        ]
        last_date = max((agreed[k].get("date") or "" for k in agreed), default="")
        portal = sorted(
            [o for o in spring if o["record"] == "portal_visit" and (o.get("date") or "") > last_date
             and o["metric"] in ("flow_lpm", "lean_flow_lpm") and not o["id"].endswith("-flow-day")],
            key=order_key,
        )
        seq += [point(o) for o in portal]
        if len(seq) >= 2:
            b, a = seq[-2], seq[-1]
            cautions = []
            if "dry season" in b["record_label"] and "monsoon" in a["record_label"]:
                cautions.append("Dry-season flow compared with monsoon flow: much of this rise is the rain season.")
            return {"before": b, "after": a, "change": change(b, a), "like_for_like": not cautions,
                    "cautions": cautions, "sequence": seq}
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
    return {"before": point(b), "after": point(a), "change": change(b, a), "like_for_like": not reasons,
            "cautions": reasons, "sequence": [point(o) for o in flows]}


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
                "remarks": h.get("remarks", ""),
                "evidence": "recall" if before else None,
            }
        )
    return rows


def depth_factor(injection_z, spring_z):
    for above, factor, words in DEPTH_FACTOR:
        if injection_z - spring_z >= above:
            return factor, words
    return DEPTH_FACTOR[-1][1:]


def di_water(site, spring_result):
    """Water injected and the share that may reach the spring, per handpump and for the site (planner Module C)."""
    rain = site.get("annual_rain_mm")
    snow = site.get("snow_mm") or 0
    rain_used = None if not rain else rain + SNOW_CAPTURE * snow
    spring_z = site.get("elevation_m")
    pumps = site["handpumps"] if "handpumps" in site else (
        [{"name": site.get("handpump_name"), "roof_area_m2": site.get("roof_area_m2")}]
        + list(site.get("additional_handpumps") or [])
    )
    rain_info = {
        "annual_rain_mm": rain,
        "annual_rain_source": site.get("annual_rain_source", ""),
        "rain_chirps_mm": site.get("rain_chirps_mm"),
        "monsoon_share_pct": site.get("rain_monsoon_share_pct"),
        "dry_season_mm": site.get("rain_dry_season_mm"),
        "snow_mm": snow,
        "snow_used_mm": round(SNOW_CAPTURE * snow),
        "rain_used_mm": None if rain_used is None else round(rain_used),
    }
    rows = []
    for h in pumps:
        row = {"id": h.get("id") or h.get("name"), "name": h.get("name"), "roof_area_m2": h.get("roof_area_m2")}
        roof = h.get("roof_area_m2")
        if not roof or not rain_used:
            rows.append({**row, "volume_m3": None})
            continue
        where = h.get("location_class") or "in_catchment"
        depth = h.get("bore_depth_m") or DEFAULT_DEPTH_M
        factor, words = 1.0, ""
        injection_z = None
        if h.get("elevation_m") is not None and spring_z is not None:
            injection_z = h["elevation_m"] - depth
            factor, words = depth_factor(injection_z, spring_z)
        share = [f * factor for f in SHARE[where]]
        collected = roof * rain_used / 1000 * COLLECTION
        injected = collected * INJECTION
        reaching = [injected * f for f in share]
        rows.append(
            {
                **row,
                "collected_m3": round(collected, 1),
                "volume_m3": round(injected, 1),
                "location_class": where,
                "location_label": SHARE_LABEL[where],
                "location_note": h.get("location_note", ""),
                "depth_m": depth,
                "depth_given": bool(h.get("bore_depth_m")),
                "injection_elevation_m": None if injection_z is None else round(injection_z),
                "depth_factor": factor,
                "depth_words": words,
                "share": [round(f, 3) for f in share],
                "reaching_m3": [round(r, 1) for r in reaching],
                "added_lpm_year": [round(r * 1000 / MINUTES_PER_YEAR, 3) for r in reaching],
                "added_lpm_lean": [round(r * 1000 / LEAN_MINUTES, 3) for r in reaching],
                "online": (h.get("di_status") or "") not in OFF_LINE,
                "di_status": h.get("di_status") or "",
            }
        )
    known = [r for r in rows if r["volume_m3"] is not None]
    if not known:
        return {"available": False, "rows": rows, **rain_info,
                "reason": "Roof area or annual rainfall is not recorded." if rows else "No DI handpump at this site."}
    now = [r for r in known if r["online"]]

    def total(items, key):
        return [round(sum(r[key][i] for r in items), 3) for i in range(3)]

    result = {
        "available": True,
        "rows": rows,
        "missing_roofs": [r["name"] for r in rows if r["volume_m3"] is None],
        **rain_info,
        "collection": COLLECTION,
        "injection": INJECTION,
        "lean_months": LEAN_MONTHS,
        "collected_m3": round(sum(r["collected_m3"] for r in known), 1),
        "volume_m3": round(sum(r["volume_m3"] for r in known), 1),
        "reaching_m3": total(known, "reaching_m3"),
        "added_lpm_year": total(known, "added_lpm_year"),
        "added_lpm_lean": total(known, "added_lpm_lean"),
        "volume_now_m3": round(sum(r["volume_m3"] for r in now), 1),
        "reaching_now_m3": total(now, "reaching_m3") if now else [0, 0, 0],
        "offline": [r["name"] for r in known if not r["online"]],
        "share_of_gain_pct": None,
    }
    if spring_result and spring_result.get("kind") == "numeric" and spring_result["change"]["mid"] > 0:
        result["share_of_gain_pct"] = round(100 * result["added_lpm_lean"][1] / spring_result["change"]["mid"])
        result["gain_metric"] = spring_result["metric_label"]
    return result


def site_impact(site, state):
    obs = [o for o in state.get("source_observations", []) if o["site_id"] == site["id"]]
    active = [v for v in state["visits"] if v["status"] == "submitted"]
    obs += portal_observations(site, active)
    spring = spring_before_after(obs)
    # Why a spring has no flow record yet (e.g. Badeda: covered, no access).
    flow_note = next(
        (o["text"] for o in obs if o["asset"] == "spring" and o["basis"] == "not_measured" and o.get("text")), ""
    )
    return {
        "role": site.get("role") or "DI site",
        "spring_name": site.get("spring_name") or site.get("name"),
        "flow_note": flow_note if not spring else "",
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
        "beyond_water": beyond_water(site, [v for v in active if v["site_id"] == site["id"]]),
    }


def beyond_water(site, visits):
    """What people said changed for them, from the community interaction part of the field forms and later visits."""
    seen, changes = set(), []
    for v in sorted(visits, key=lambda v: v.get("visit_date") or ""):
        for c in v.get("changes") or []:
            key = (c.get("area"), c.get("before"), c.get("after"))
            if key in seen:
                continue
            seen.add(key)
            changes.append({**c, "date": v.get("visit_date")})
    return {"story": (site.get("field_history") or {}).get("impact_beyond_water", ""), "changes": changes}


def portfolio(impacts):
    di_sites = impacts
    numeric = [i["spring_before_after"] for i in di_sites if (i["spring_before_after"] or {}).get("kind") == "numeric"]
    reported = [i["spring_before_after"] for i in di_sites if (i["spring_before_after"] or {}).get("kind") == "reported"]
    # A handpump linked to two springs (Arakot 2) is counted once.
    pumps = list({p["name"]: p for i in di_sites for p in i["handpumps_before_after"]}.values())
    water = [i["di_water"] for i in di_sites if i["di_water"]["available"]]
    # A handpump linked to two springs (Arakot 2) is counted once in the total.
    rows = {r["id"]: r for w in water for r in w["rows"] if r["volume_m3"] is not None}
    volumes = {k: r["volume_m3"] for k, r in rows.items()}
    reaching = [round(sum(r["reaching_m3"][i] for r in rows.values()), 1) for i in range(3)]
    reaching_now = [round(sum(r["reaching_m3"][i] for r in rows.values() if r["online"]), 1) for i in range(3)]
    return {
        "di_sites": len(di_sites),
        "spring_numeric": len(numeric),
        "spring_numeric_up": sum(
            r["change"]["direction"] in ("increase", "likely_increase", "dry_to_flowing") for r in numeric
        ),
        "spring_reported": len(reported),
        "spring_reported_up": sum(r["direction"] == "increase" for r in reported),
        "spring_reported_same": sum(r["direction"] == "same" for r in reported),
        "spring_no_data": len(di_sites) - len(numeric) - len(reported),
        "spring_no_data_names": [i["spring_name"] for i in di_sites if not i["spring_before_after"]],
        "pumps": len(pumps),
        "pumps_with_before": sum(p["before"] is not None for p in pumps),
        "pumps_restored": sum(p["outcome"] == "restored" for p in pumps),
        "pumps_improved": sum(p["outcome"] == "improved" for p in pumps),
        "pumps_not_working": sum(p["outcome"] == "not_working_now" for p in pumps),
        "last_two": sum(i["last_two"] is not None for i in impacts),
        "di_volume_m3": round(sum(volumes.values()), 1),
        "di_collected_m3": round(sum(r["collected_m3"] for r in rows.values()), 1),
        "di_reaching_m3": reaching,
        "di_reaching_now_m3": reaching_now,
        "di_offline": sorted({r["name"] for r in rows.values() if not r["online"]}),
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
        "formula": "Same change formula. Readings in order: before-DI dry flow, after-DI dry flow, after-DI monsoon "
        "flow (latest), then any later visit. The last two are compared.",
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
        "id": "rainfall",
        "asset": "water injected",
        "name": "Rainfall used for DI",
        "unit": "mm a year",
        "formula": "Rain used = annual rain + 0.5 × winter snow at the spring's height",
        "weights": "Annual rain from the IMD gridded rain gauges (2001-2025 mean); CHIRPS satellite rain only when "
        "gauges are missing, as in the planner. Snow is ERA5 winter snowfall read at the spring's height; half is "
        "counted as melting into the gutters (judgement).",
        "needs": "The spring's position (rain and snow are read from the planner's data layers).",
        "missing": "No rain value: no water estimate for the site.",
        "interpretation": "A long-term average year. A wet or dry year will differ.",
    },
    {
        "id": "rain_collected",
        "asset": "water injected",
        "name": "Rain collected from the DI roofs",
        "unit": "m³ a year",
        "formula": "Collected = roof area (m²) × rain used (mm) / 1000 × 0.8",
        "weights": "0.8 = share of roof rain reaching the handpump after gutter, pipe and splash losses (RDI design "
        "0.7-0.8). Same default as the planner.",
        "needs": "Roof area per DI handpump (field form).",
        "missing": "No roof area: that handpump is left out and named.",
        "interpretation": "Rain the roof can send to the handpump in an average year.",
    },
    {
        "id": "water_injected",
        "asset": "water injected",
        "name": "Water injected into the aquifer",
        "unit": "m³ a year",
        "formula": "Injected = collected × 0.85",
        "weights": "0.85 = share actually injected after first flush, overflow, downtime and clogging (a different "
        "loss from the 0.8 above). Same default as the planner.",
        "needs": "Collected water.",
        "missing": "As above.",
        "interpretation": "Water going into the ground when the DI line works. A disconnected line injects nothing "
        "until it is repaired, so the 'now' figures leave it out.",
    },
    {
        "id": "water_reaching_spring",
        "asset": "water injected",
        "name": "DI water that may reach the spring",
        "unit": "m³ a year and L/min",
        "formula": "Reaching = injected × share × depth factor. Added flow = reaching × 1000 / 525,600 (spread over "
        "the year) or reaching × 1000 / (5 × 30.44 × 1,440) (best case: all in the 5 lean months)",
        "weights": "Share (low / mid / best case): 0.30/0.60/1.00 in a recharge zone on the spring's slope; "
        "0.10/0.30/0.60 in a zone linked by a fault or rock tilt; 0.05/0.20/0.50 by a crack; 0.05/0.15/0.30 elsewhere "
        "in the catchment; 0/0.02/0.10 outside it; 0 below the spring. Depth factor from the injection point "
        "(handpump ground − depth, 70 m if unknown) against the spring outlet: × 1.0 more than 10 m above, × 0.7 "
        "within 10 m, × 0.4 up to 50 m below, × 0.2 deeper. Same as the planner.",
        "needs": "Handpump and spring heights (DEM), handpump depth, and where the handpump sits. Where it sits comes "
        "from the spring planner (scripts/planner_di_locations.py: recharge zones R1-R3, catchment or outside), so "
        "both give the same share; Kaddukhal stays 'outside' because the geologist found no link.",
        "missing": "Without a link to the spring the real share is zero; only monitoring can show it.",
        "interpretation": "An approximate range for planning and monitoring, not a measured flow. The rest of the "
        "water feeds other springs, streams or deeper groundwater.",
    },
    {
        "id": "share_explained",
        "asset": "water injected",
        "name": "Share of the spring gain DI could explain",
        "unit": "%",
        "formula": "100 × best-case lean-season added flow (mid) / dry-season spring gain (mid)",
        "weights": "Uses the mid share and assumes all of it comes out in the lean months, so it leans high.",
        "needs": "A numeric before/after dry-season gain and a DI water estimate.",
        "missing": "Not shown when the spring did not gain or there is no estimate.",
        "interpretation": "Well below 100% means DI alone does not account for the whole gain; rain, other works "
        "or the spring's own variation also played a part.",
    },
]
