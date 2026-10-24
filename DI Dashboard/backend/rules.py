"""Validated portal data and reproducible assessment rules. Never reads attachments."""

import calendar
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from uuid import uuid4
from .store import now


class Invalid(ValueError):
    pass


DOMAINS = {
    "access": "Collecting water",
    "hygiene": "Hygiene",
    "sanitation": "Toilets",
    "education": "School",
    "livelihoods": "Farming and income",
    "equity": "Who benefits",
    "vegetation": "Vegetation",
    "quality": "Water quality",
    "upkeep": "Maintenance",
}
SEASONS = {
    "dry": "Dry season",
    "monsoon": "Monsoon",
    "post_monsoon": "After the monsoon",
    "winter": "Winter",
    "unknown": "Not sure",
}


def today():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()


def number(v, name, low=0, high=1e9):
    if isinstance(v, bool):
        raise Invalid(name + " needs a number.")
    try:
        n = float(v)
    except (ValueError, TypeError):
        raise Invalid(name + " needs a number.")
    if not isfinite(n) or not low <= n <= high:
        raise Invalid(f"{name} must be between {low:g} and {high:g}.")
    return n


def text(v, name, limit=200, required=True):
    s = str(v or "").strip()
    if required and not s:
        raise Invalid("Please add " + name + ".")
    if len(s) > limit:
        raise Invalid(f"{name} is too long (maximum {limit} characters).")
    return s


def day(v, name):
    try:
        d = date.fromisoformat(v)
    except (ValueError, TypeError):
        raise Invalid("Please add a valid " + name + ".")
    if d > today():
        raise Invalid(name + " cannot be in the future.")
    return d.isoformat()


def rainfall_location(site):
    if site.get("pump_latitude") is not None and site.get("pump_longitude") is not None:
        return {
            **site,
            "latitude": site["pump_latitude"],
            "longitude": site["pump_longitude"],
            "rainfall_at": "handpump",
        }
    return {**site, "rainfall_at": "spring_proxy"}


def coords_key(site):
    s = rainfall_location(site)
    return (
        f"{s['latitude']:.6f},{s['longitude']:.6f}:era5"
        if s.get("latitude") is not None and s.get("longitude") is not None
        else None
    )


def validate_site(b, old=None):
    if not isinstance(b, dict):
        raise Invalid("Site details are missing.")
    s = {
        k: b.get(k)
        for k in (
            "name",
            "spring_name",
            "village",
            "district",
            "handpump_name",
            "gps_later",
            "latitude",
            "longitude",
            "di_year",
            "roof_area_m2",
            "collection_factor",
            "link_basis",
            "water_before",
            "supply",
            "households",
            "collection_before",
            "other_works",
        )
    }
    for k, label in [
        ("name", "a site name"),
        ("spring_name", "the spring name"),
        ("village", "the village"),
        ("district", "the district"),
        ("handpump_name", "a handpump name or local landmark"),
    ]:
        s[k] = text(s[k], label)
    if not isinstance(s["gps_later"], bool):
        raise Invalid("Choose whether GPS is available.")
    if s["gps_later"]:
        s["latitude"] = s["longitude"] = None
    else:
        s["latitude"] = number(s["latitude"], "Latitude", -90, 90)
        s["longitude"] = number(s["longitude"], "Longitude", -180, 180)
    s["pump_gps_later"] = b.get("pump_gps_later", True)
    if not isinstance(s["pump_gps_later"], bool):
        raise Invalid("Choose whether handpump GPS is available.")
    if s["pump_gps_later"]:
        s["pump_latitude"] = s["pump_longitude"] = None
    else:
        s["pump_latitude"] = number(b.get("pump_latitude"), "Handpump latitude", -90, 90)
        s["pump_longitude"] = number(b.get("pump_longitude"), "Handpump longitude", -180, 180)
    for k in (
        "photo_id",
        "photo_url",
        "photo_caption",
        "source_refs",
        "location_status",
        "location_notes",
        "additional_handpumps",
        "field_history",
        "evidence_notes",
    ):
        if old and k in old:
            s[k] = old[k]
    if "additional_handpumps" in b:
        s["additional_handpumps"] = validate_handpumps(b["additional_handpumps"], (old or {}).get("additional_handpumps"))
    if s["link_basis"] not in ("reported", "field_checked", "unknown"):
        raise Invalid("Choose how the spring and handpump are linked.")
    for k, limit in [
        ("water_before", 3000),
        ("collection_before", 3000),
        ("other_works", 3000),
        ("supply", 100),
    ]:
        s[k] = text(s[k], k.replace("_", " "), limit, False)
    for k in ("roof_area_m2", "collection_factor", "households", "di_year"):
        if s[k] in ("", None):
            s[k] = None
        else:
            s[k] = number(s[k], k.replace("_", " "), 0, 1 if k == "collection_factor" else 1e8)
    if s["households"] is not None and not s["households"].is_integer():
        raise Invalid("Households must be a whole number.")
    if s["di_year"] is not None and (
        not s["di_year"].is_integer() or not 1900 <= s["di_year"] <= today().year
    ):
        raise Invalid("Check the DI installation year.")
    # Keep imported details the form does not show (record ids, rainfall, role). A portal edit makes the site the
    # team's own version, so later data-file imports leave it alone.
    for k, v in (old or {}).items():
        if k not in s and k != "imported":
            s[k] = v
    if (old or {}).get("handpumps"):
        # Imported sites keep one list of all handpumps (with their data-file ids) for the impact results.
        first = next((h for h in old["handpumps"] if h.get("primary")), old["handpumps"][0])
        primary = {
            **first,
            "name": s["handpump_name"],
            "latitude": s["pump_latitude"],
            "longitude": s["pump_longitude"],
            "roof_area_m2": s["roof_area_m2"],
            "di_year": s["di_year"],
            "primary": True,
        }
        s["handpumps"] = [primary] + [{**h, "primary": False} for h in s.get("additional_handpumps") or []]
    s.update(
        id=old["id"] if old else "site-" + uuid4().hex[:12],
        setup_complete=True,
        registered_at=old["registered_at"] if old else now(),
        updated_at=now(),
    )
    return s


def validate_handpumps(rows, old_rows=None):
    """Additional DI handpumps linked to the same spring: name, optional GPS, roof area and DI year."""
    if not isinstance(rows, list) or len(rows) > 10:
        raise Invalid("Check the additional handpumps.")
    old_by_name = {p.get("name"): p for p in old_rows or []}
    clean = []
    for i, p in enumerate(rows):
        if not isinstance(p, dict):
            raise Invalid("Check the additional handpumps.")
        name = text(p.get("name"), f"a name for additional handpump {i + 1}")
        item = {**old_by_name.get(name, {}), "name": name}
        lat, lon = p.get("latitude"), p.get("longitude")
        if lat in ("", None) and lon in ("", None):
            item["latitude"] = item["longitude"] = None
        else:
            item["latitude"] = number(lat, name + " latitude", -90, 90)
            item["longitude"] = number(lon, name + " longitude", -180, 180)
        for k, high in (("roof_area_m2", 1e5), ("di_year", today().year)):
            item[k] = None if p.get(k) in ("", None) else number(p.get(k), name + " " + k.replace("_", " "), 0, high)
        if item["di_year"] is not None and (not item["di_year"].is_integer() or item["di_year"] < 1900):
            raise Invalid("Check the DI installation year for " + name + ".")
        clean.append(item)
    if len({p["name"].lower() for p in clean}) != len(clean):
        raise Invalid("Give each additional handpump a different name.")
    return clean


def flow_readings(rows, label):
    if not isinstance(rows, list) or len(rows) != 3:
        raise Invalid(label + " needs three readings.")
    cleaned = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            raise Invalid(label + " reading is incomplete.")
        litres = number(r.get("litres"), f"{label}: litres in reading {i+1}", 0.001, 1e6)
        seconds = number(r.get("seconds"), f"{label}: seconds in reading {i+1}", 0.001, 86400)
        cleaned.append({"litres": litres, "seconds": seconds, "rate_lpm": litres * 60 / seconds})
    mean = sum(r["rate_lpm"] for r in cleaned) / 3
    return cleaned, mean


def validate_visit(b, state, submit=False):
    if not isinstance(b, dict):
        raise Invalid("Visit details are missing.")
    site = next((s for s in state["sites"] if s["id"] == b.get("site_id")), None)
    if not site:
        raise Invalid("Choose a site.")
    existing = next((v for v in state["visits"] if v["id"] == b.get("id")), None)
    if existing and existing["status"] == "submitted":
        raise Invalid("Use Correct this visit to change a saved visit.")
    v = {
        k: b.get(k)
        for k in (
            "visit_date",
            "visitor",
            "season",
            "spring",
            "pump",
            "di",
            "safety",
            "tests",
            "change_status",
            "changes",
            "other_work",
            "notes",
            "supersedes",
            "correction_reason",
            "recent_rain",
            "period",
            "pump_asset_name",
        )
    }
    for k in ("spring", "pump", "di", "safety"):
        if v[k] is None:
            v[k] = {}
        if not isinstance(v[k], dict):
            raise Invalid("Check the " + k + " details.")
    for k in ("tests", "changes"):
        if v[k] is None:
            v[k] = []
        if not isinstance(v[k], list) or any(not isinstance(row, dict) for row in v[k]):
            raise Invalid("Check the " + k + " entries.")
    for k in ("visit_date", "visitor", "season", "change_status", "notes", "other_work"):
        if v[k] is None:
            v[k] = ""
    v.update(
        id=existing["id"] if existing else "visit-" + uuid4().hex[:12],
        site_id=site["id"],
        status="submitted" if submit else "draft",
        created_at=existing["created_at"] if existing else now(),
        saved_at=now(),
        entry_method="portal",
        rule_version="2.0",
    )
    if not submit:
        if v.get("supersedes") and not any(
            r["id"] == v["supersedes"] and r["status"] == "submitted" and r["site_id"] == site["id"]
            for r in state["visits"]
        ):
            raise Invalid("Choose a saved visit at this site to correct.")
        return v
    if not site.get("setup_complete"):
        raise Invalid("Please finish the one-time site details before saving a visit.")
    v["visit_date"] = day(v["visit_date"], "visit date")
    v["visitor"] = text(v["visitor"], "who visited")
    if v["season"] not in SEASONS:
        raise Invalid("Choose the season, or Not sure.")
    if v.get("period") in (None, "", "auto"):
        v["period"] = ""
    elif v["period"] not in ("before_di", "after_di"):
        raise Invalid("Choose whether this visit was before or after DI.")
    names = [site.get("handpump_name")] + [p.get("name") for p in site.get("additional_handpumps", [])]
    if v.get("pump_asset_name") in (None, "") or v["pump_asset_name"] == site.get("handpump_name"):
        v.pop("pump_asset_name", None)
    elif v["pump_asset_name"] not in names:
        raise Invalid("Choose one of this site's handpumps.")
    if not isinstance(v["spring"], dict):
        raise Invalid("Record the spring flow, or say why it was not measured.")
    spring = v["spring"]
    status = spring.get("status")
    if status not in ("measured", "dry", "not_measured"):
        raise Invalid("Choose whether the spring flow was measured.")
    if status == "measured":
        spring["readings"], spring["flow_lpm"] = flow_readings(spring.get("readings"), "Spring flow")
        if spring.get("capture") not in ("full", "partial"):
            raise Invalid("Say whether you collected the whole spring flow.")
        spring["point"] = text(spring.get("point"), "the measurement point")
        spring["flow_m3_s"] = spring["flow_lpm"] / 60000
        spring["method"] = "bucket_stopwatch"
    elif status == "dry":
        spring.update(flow_lpm=0.0, flow_m3_s=0.0, method="no_flow_observed", capture="full")
    else:
        spring["reason"] = text(spring.get("reason"), "why the flow was not measured", 1000)
        spring.pop("flow_lpm", None)
        spring.pop("flow_m3_s", None)
    if not isinstance(v["pump"], dict) or v["pump"].get("status") not in (
        "working",
        "no_water",
        "broken",
        "not_checked",
    ):
        raise Invalid("Choose the handpump condition.")
    pump = v["pump"]
    if pump.get("measure"):
        if pump["status"] != "working":
            raise Invalid("Only a working pump can have a delivery test.")
        pump["readings"], pump["flow_lpm"] = flow_readings(pump.get("readings"), "Handpump delivery")
        pump["procedure"] = text(pump.get("procedure"), "how the pump test was done", 1000)
        pump["flow_m3_s"] = pump["flow_lpm"] / 60000
    else:
        for k in ("readings", "flow_lpm", "flow_m3_s"):
            pump.pop(k, None)
    if not isinstance(v["di"], dict) or v["di"].get("status") not in (
        "connected",
        "broken",
        "blocked",
        "disconnected",
        "not_checked",
    ):
        raise Invalid("Choose the DI pipe condition.")
    safety = v["safety"] or {}
    v["safety"] = safety
    if not isinstance(safety, dict):
        raise Invalid("Check the filter details.")
    for k in ("filter", "first_flush", "overflow"):
        if safety.get(k, "not_checked") not in ("ok", "needs_work", "missing", "not_checked"):
            raise Invalid("Choose a valid filter / first-flush condition.")
    tests = v["tests"] or []
    v["tests"] = tests
    if not isinstance(tests, list) or len(tests) > 20:
        raise Invalid("Check the water tests.")
    units = {"Iron": "mg/L", "pH": "pH", "Turbidity": "NTU", "E. coli": "CFU/100 mL", "TDS": "mg/L"}
    for test in tests:
        if not isinstance(test, dict) or test.get("parameter") not in units:
            raise Invalid("Choose the water-test parameter.")
        test["value"] = number(test.get("value"), "Test result", 0, 14 if test["parameter"] == "pH" else 1e9)
        test["unit"] = units[test["parameter"]]
        test["method"] = text(test.get("method"), "the test kit or lab")
        test["sample_point"] = text(test.get("sample_point"), "the water sample location")
    if v["change_status"] not in ("none", "some", "not_discussed"):
        raise Invalid("Say whether any changes were discussed.")
    changes = v["changes"] or []
    v["changes"] = changes if v["change_status"] == "some" else []
    if not isinstance(v["changes"], list) or len(v["changes"]) > 20:
        raise Invalid("Check the village changes.")
    if v["change_status"] == "some" and not v["changes"]:
        raise Invalid("Add at least one change, or choose No change noticed / Not discussed.")
    for change in v["changes"]:
        if change.get("area") not in DOMAINS:
            raise Invalid("Choose what changed.")
        if change.get("direction") not in ("better", "same", "worse", "unclear"):
            raise Invalid("Choose the direction of change.")
        change["before"] = text(change.get("before"), "the earlier situation", 3000)
        change["after"] = text(change.get("after"), "the situation now", 3000)
        if change.get("basis") not in ("seen", "people_said"):
            raise Invalid("Say how you know about the change.")
        if change["basis"] == "people_said":
            change["who"] = text(change.get("who"), "who told you about the change")
    for k in ("notes", "other_work"):
        v[k] = text(v[k], k.replace("_", " "), 6000, False)
    for c in v["changes"]:
        c["asset"] = c.get("asset", "village")
        if c["asset"] not in ("spring", "handpump", "village"):
            raise Invalid("Choose what the change relates to.")
    v["recent_rain"] = text(v.get("recent_rain"), "recent rain", 1000, False)
    if v.get("supersedes"):
        old = next(
            (r for r in state["visits"] if r["id"] == v["supersedes"] and r["status"] == "submitted"), None
        )
        if not old or old["site_id"] != v["site_id"]:
            raise Invalid("A correction must refer to a saved visit at this site.")
        if any(x.get("supersedes") == old["id"] and x["status"] == "submitted" for x in state["visits"]):
            raise Invalid("That visit already has a correction. Open the latest version.")
        v["correction_reason"] = text(v.get("correction_reason"), "why the visit needs correcting", 2000)
    return v


def active_visits(visits):
    done = [v for v in visits if v["status"] == "submitted"]
    replaced = {v.get("supersedes") for v in done}
    return sorted(
        [v for v in done if v["id"] not in replaced], key=lambda v: (v["visit_date"], v["saved_at"])
    )


def rain_window(data, end, days=90):
    if not data:
        return None
    start = end - timedelta(days=days - 1)
    lookup = dict(zip(data["dates"], data["rain_mm"]))
    values = [lookup.get((start + timedelta(days=i)).isoformat()) for i in range(days)]
    if any(x is None for x in values):
        return None
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "rain_mm": sum(values),
        "rain_m": sum(values) / 1000,
    }


def same_outlet(a, b):
    """Two spring readings can be compared: same method and point, or one of them found the spring dry.
    A dry spring has no flow at any point, so dry -> flowing (or flowing -> dry) is a valid change."""
    if "no_flow_observed" in (a.get("method"), b.get("method")):
        return True
    return a.get("method") == b.get("method") and a.get("point", "") == b.get("point", "")


def site_assessment(site, state):
    visits = [v for v in active_visits(state["visits"]) if v["site_id"] == site["id"]]
    measured = [v for v in visits if v["spring"].get("flow_lpm") is not None]
    current = measured[-1] if measured else None
    comparison = None
    if current and current["season"] != "unknown":
        past = [
            v
            for v in measured[:-1]
            if v["season"] == current["season"]
            and v["visit_date"] != current["visit_date"]
            and not v.get("date_accuracy")
            and not current.get("date_accuracy")
            and v["spring"].get("capture") == "full"
            and current["spring"].get("capture") == "full"
            and same_outlet(v["spring"], current["spring"])
        ]
        if past:
            old = past[-1]
            delta = current["spring"]["flow_lpm"] - old["spring"]["flow_lpm"]
            comparison = {
                "before_id": old["id"],
                "after_id": current["id"],
                "before_date": old["visit_date"],
                "after_date": current["visit_date"],
                "before_lpm": old["spring"]["flow_lpm"],
                "after_lpm": current["spring"]["flow_lpm"],
                "difference_lpm": delta,
                "percent": delta / old["spring"]["flow_lpm"] * 100 if old["spring"]["flow_lpm"] else None,
                "dry_to_flowing": old["spring"]["flow_lpm"] == 0 and current["spring"]["flow_lpm"] > 0,
            }
    weather = state["weather"].get(coords_key(site))
    rain = None
    potential = None
    if weather and weather["dates"]:
        end = min(today() - timedelta(days=1), date.fromisoformat(weather["dates"][-1]))
        rain = rain_window(weather, end)
        if rain and site.get("roof_area_m2") is not None and site.get("collection_factor") is not None:
            potential = {
                "volume_m3": rain["rain_mm"] * site["roof_area_m2"] * site["collection_factor"] / 1000,
                "volume_litres": rain["rain_mm"] * site["roof_area_m2"] * site["collection_factor"],
                "roof_area_m2": site["roof_area_m2"],
                "collection_factor": site["collection_factor"],
                "period_start": rain["start"],
                "period_end": rain["end"],
                "meaning": "Rainwater that could be collected from the roof; not measured injection or extra spring flow.",
            }
    if comparison:
        before_rain = rain_window(weather, date.fromisoformat(comparison["before_date"]) - timedelta(days=1))
        after_rain = rain_window(weather, date.fromisoformat(comparison["after_date"]) - timedelta(days=1))
        comparison.update(before_rain=before_rain, after_rain=after_rain)
    changes = [
        {**c, "visit_id": v["id"], "date": v["visit_date"], "visitor": v["visitor"]}
        for v in visits
        for c in v["changes"]
    ]
    return {
        "site_id": site["id"],
        "visit_count": len(visits),
        "latest_visit": visits[-1] if visits else None,
        "current_flow": current["spring"]["flow_lpm"] if current else None,
        "flow_date": current["visit_date"] if current else None,
        "latest_flow_visit": current,
        "comparison": comparison,
        "changes": changes,
        "rain": rain,
        "roof_potential": potential,
        "quality_test_count": sum(len(v["tests"]) for v in visits),
        "attribution": "Rain, repairs and other work may also explain a change. DI’s share is not yet known.",
    }


def assess(state):
    from .assessment import enrich

    return enrich(state, [site_assessment(s, state) for s in state["sites"]])
