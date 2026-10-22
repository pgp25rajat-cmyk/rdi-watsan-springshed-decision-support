"""Spring-level values transcribed from papers and reports supplied to the project.

Every value is typed in exactly as printed in the source (thousands separators
removed, degree symbols dropped from coordinates) and carries its own source
locator and value status. Nothing here is converted, interpolated or inferred:
blank means the source does not report it.

Value status vocabulary (used in the long table):
- measured: the source reports it as an observed field or monitoring value.
- reported: the source states the value but not how or when it was measured.
- approximate: the source itself marks it as approximate (~, "around", 2-decimal coordinates).
- delineated_estimate: an area or boundary produced by a delineation method (GIS or field hydrogeology).
- derived_by_source: computed by the source from other values (index, split of a group area).
- descriptive: text classification or description (geology, spring type, location names).
"""

RATHI_REF = (
    "Rathi, V.K., Ram, S., Agarwal, A. & Nema, R.K. (2021). Delineation of springsheds (recharge zones) "
    "for the springs in Garhwal region of Uttarakhand, India. Journal of Soil and Water Conservation 20(4): 418-423. "
    "doi:10.5958/2455-7145.2021.00052.7"
)
DANIEL_REF = (
    "Daniel, D., Anandhi, A. & Sen, S. (2021). Conceptual model for the vulnerability assessment of springs in the "
    "Indian Himalayas. Climate 9(8): 121. doi:10.3390/cli9080121 (CC BY)"
)
CHAMBA_REF = (
    "RDI/WATSAN (SRHU). Hydrogeological Assessment Report - Revival of defunct handpumps by aquifer recharging "
    "using Direct Injection technology, Chamba, Tehri-Garhwal (Spring Assesment Report.docx, undated)"
)
ATLAS_REF = (
    "CHIRAG with ACWADAM and ATREE. Spring Atlas of Uttarakhand (eds. B.S. Mehra and H. Kulkarni) - "
    "Details of representative springs"
)

COMMON_FIELDS = {
    "source_area_name", "district", "block", "gram_panchayat", "village", "spring_name",
    "latitude_source_value", "longitude_source_value", "elevation_m_source_value",
    "slope_aspect_source_value", "slope_degrees_source_value", "lithology_source_value",
    "spring_type_source_value", "tds_source_value", "ph_source_value", "discharge_lpm_source_value",
    "rainfall_source_value", "geological_structure_source_value", "porosity_source_value",
    "recharge_area_ha_source_value",
}

LITERATURE_COLUMNS = [
    "source_reference",
    "value_status_summary",
    "recharge_area_basis_source_value",
    "springshed_area_km2_source_value",
    "springshed_elevation_min_m_source_value",
    "springshed_elevation_max_m_source_value",
    "spring_group_source_value",
    "catchment_area_ha_source_value",
    "catchment_elevation_range_m_source_value",
    "discharge_max_m3_per_day_source_value",
    "discharge_dependable_q75_lpm_source_value",
    "discharge_annual_series_source_value",
    "handpump_discharge_lpm_source_value",
    "water_quality_other_source_value",
    "recharge_area_slope_aspect_source_value",
    "intervention_source_value",
    "vulnerability_index_source_value",
    "candidate_match_record_ids",
]

UNITS = {
    "latitude_source_value": "decimal degrees N",
    "longitude_source_value": "decimal degrees E",
    "elevation_m_source_value": "m asl",
    "slope_degrees_source_value": "degrees",
    "tds_source_value": "mg/l",
    "discharge_lpm_source_value": "L/min",
    "rainfall_source_value": "mm/year",
    "recharge_area_ha_source_value": "ha",
    "springshed_area_km2_source_value": "km2",
    "springshed_elevation_min_m_source_value": "m",
    "springshed_elevation_max_m_source_value": "m",
    "catchment_area_ha_source_value": "ha",
    "catchment_elevation_range_m_source_value": "m asl",
    "discharge_max_m3_per_day_source_value": "m3/day",
    "discharge_dependable_q75_lpm_source_value": "L/min",
    "handpump_discharge_lpm_source_value": "L/min",
}


# --------------------------------------------------------------------------- Rathi et al. (2021)
# Table 1 (Chandrabhaga) and Table 2 (Danda). Columns: spring, max flow (m3/day), clubbed springs,
# % of spring flow, group area (km2, printed once per group), springshed area (km2), elev min, elev max.
RATHI_TABLE_1 = [
    ("Sp01", "15.1", "01,03", "11.0", "0.092", "0.01", "1545", "1660"),
    ("Sp03", "117.4", "01,03", "89.0", "", "0.082", "1505", "1660"),
    ("Sp4A", "49.8", "4A,4B", "51.0", "0.037", "0.019", "1375", "1570"),
    ("Sp4B", "48", "4A,4B", "49.0", "", "0.018", "1365", "1570"),
    ("Sp05", "28.3", "5", "", "0.019", "0.019", "1420", "1685"),
    ("Sp06", "25.5", "6,7,8", "27.6", "0.059", "0.016", "1445", "1800"),
    ("Sp07", "49.3", "6,7,8", "53.5", "", "0.032", "1440", "1800"),
    ("Sp08", "17.4", "6,7,8", "18.9", "", "0.011", "1460", "1800"),
    ("Sp09", "46.3", "9", "", "0.035", "0.035", "1440", "1640"),
    ("Sp10A", "27.9", "10A,11", "65.0", "0.029", "0.019", "1655", "1800"),
    ("Sp11", "14.7", "10A,11", "35.0", "", "0.01", "1580", "1800"),
    ("Sp12", "5.4", "12", "", "0.009", "0.009", "1520", "1690"),
    ("Sp13", "49.6", "13", "", "0.033", "0.033", "1310", "1440"),
    ("Sp14", "34.4", "14", "", "0.018", "0.018", "1645", "1800"),
    ("Sp15", "57.3", "15", "", "0.031", "0.031", "1715", "2020"),
    ("Sp16", "18", "16", "", "0.013", "0.013", "1690", "1830"),
    ("Sp17", "34.9", "17", "", "0.026", "0.026", "1615", "1800"),
    ("Sp18", "42.1", "18", "", "0.021", "0.021", "1850", "2020"),
    ("Sp19", "76.6", "19", "", "0.033", "0.033", "1655", "1830"),
    ("Sp20", "52.1", "20", "", "0.028", "0.028", "1710", "1965"),
]
RATHI_TABLE_2 = [
    ("Sp02", "93", "02", "", "0.050", "0.050", "1430", "1660"),
    ("Sp03", "69", "3,13,15", "46.0", "0.058", "0.027", "1240", "1480"),
    ("Sp4A", "121", "4A,4B", "86.0", "0.055", "0.047", "1325", "1520"),
    ("Sp4B", "20", "4A,4B", "14.0", "", "0.008", "1320", "1520"),
    ("Sp05", "86", "05,20", "47.0", "0.061", "0.029", "1345", "1580"),
    ("Sp06", "31", "06", "", "0.006", "0.006", "1470", "1550"),
    ("Sp07", "74", "07", "", "0.030", "0.030", "1560", "1720"),
    ("Sp08", "54", "08", "", "0.010", "0.010", "1530", "1620"),
    ("Sp09", "92", "09", "", "0.041", "0.041", "1550", "1740"),
    ("Sp11", "47", "11", "", "0.010", "0.010", "1070", "1160"),
    ("Sp13", "47", "3,13,15", "32.0", "", "0.019", "1225", "1480"),
    ("Sp15", "33", "3,13,15", "22.0", "", "0.013", "1190", "1480"),
    ("Sp16", "23", "16", "", "0.016", "0.016", "1165", "1330"),
    ("Sp17", "30", "17", "", "0.014", "0.014", "1130", "1280"),
    ("Sp20", "97", "05,20", "53.0", "", "0.032", "1285", "1580"),
]


def rathi_records():
    records = []
    tables = [
        ("Table 1", "Chandrabhaga watershed", RATHI_TABLE_1, "PDF page 4 (journal p. 421)"),
        ("Table 2", "Danda watershed", RATHI_TABLE_2, "PDF page 4 (journal p. 421)"),
    ]
    for table, watershed, rows, page in tables:
        group_area = {}
        for spring, _flow, clubbed, _share, area, *_ in rows:
            if area:
                group_area[clubbed] = area
        for spring, flow, clubbed, share, area, shed_area, elev_min, elev_max in rows:
            locator = f"Rathi 2021 {table}, {page}, {spring}"
            is_group = "," in clubbed
            if is_group:
                group_text = (
                    f"Clubbed springs {clubbed}; share of group maximum flow {share}%; "
                    f"group springshed area {group_area[clubbed]} km2"
                )
                area_status = "derived_by_source"
                area_note = "Group springshed split by the source in proportion to each spring's share of discharge."
            else:
                group_text = "Single-spring springshed"
                area_status = "delineated_estimate"
                area_note = ""
            values = {
                "source_area_name": f"{watershed}, Garhwal region, Uttarakhand",
                "spring_name": spring,
                "springshed_area_km2_source_value": (shed_area, area_status, area_note),
                "springshed_elevation_min_m_source_value": (elev_min, "delineated_estimate", "Minimum elevation of the delineated springshed, not the spring outlet."),
                "springshed_elevation_max_m_source_value": (elev_max, "delineated_estimate", ""),
                "spring_group_source_value": (group_text, "derived_by_source" if is_group else "descriptive", ""),
                "discharge_max_m3_per_day_source_value": (flow, "measured", "Annual average maximum flow; the text cites ten years of records (1999-2000 to 2009-10)."),
                "recharge_area_basis_source_value": (
                    "GIS surface flow-direction delineation with geology and stream/lineament limits, then adjusted so that "
                    "area follows an exponential relation with maximum spring flow",
                    "descriptive", "",
                ),
            }
            records.append({
                "prefix": "RAT",
                "source_id": "SRC-011",
                "source_dataset": f"Rathi et al. 2021 - {table} ({watershed})",
                "source_record_locator": locator,
                "source_reference": RATHI_REF,
                "default_locator": locator,
                "values": values,
                "value_status_summary": "Max flow measured; springshed area and elevations are delineated estimates; no spring coordinates or outlet elevation published.",
                "staging_quality_flag": (
                    "Verify: no coordinates published. Springshed areas were adjusted to fit the area-flow regression, so these "
                    "area-flow pairs are not independent validation data for that relation."
                ),
                "source_notes": "Transcribed from the published table. Spring numbers repeat between watersheds; use record_id, not spring_name, as the key.",
            })
    return records


# --------------------------------------------------------------------------- Chamba Spring Assessment Report
CHAMBA_ROWS = [
    # spring, location, lat, lon, area ha, elev range, spring elev, slope, aspect, lithology, discharge, hp discharge, aquifer text
    ("Balench", "Arakot region", "30.36", "78.37", "33.53", "1495–1807", "1710", "22.00", "Southwest",
     "Schistose quartzite & dolomitic limestone", "1.5–2", "3", "Fractured aquifer within quartzite and limestone"),
    ("Chorghadna", "Chopdiyal Gaon, Chamba", "30.38", "78.36", "43.55", "1757–2074", "1838", "19.86", "West",
     "Phyllite", "8–12", "12", "Fractured aquifer within phyllite"),
    ("Ganjrkhanal", "Uniyal Gaon, Kaddukhal", "30.40", "78.30", "53.67", "2299–2729", "2388", "17.97", "Southeast",
     "Phyllite", "8–15", "15", "Depression aquifer within phyllite"),
    ("Malani", "Chopdiyal Gaon, Chamba", "30.37", "78.37", "18.12", "1686–1970", "1774", "24.25", "Southwest",
     "Phyllite", "7–9", "9", "Depression-and-fractured aquifer within phyllite (combination type)"),
    ("Nimbujhard", "Gunogi, Chamba", "30.39", "78.36", "20.67", "1954–2117", "2018", "14.37", "Southwest",
     "Phyllite & dolomitic limestone", "4–6", "4", "Fractured aquifer within phyllite and limestone"),
    ("Paniyar Dhar", "Arakot region", "30.36", "78.38", "45.03", "1542–2030", "1725", "25.93", "South",
     "Dolomitic limestone", "1.5–2", "3", "Fractured aquifer within limestone"),
    ("Rasanulikhal", "Kanatal, Chamba", "30.42", "78.33", "19.35", "2161–2401", "2282", "21.71", "Southeast",
     "Phyllite", "~16", "16", "Fractured aquifer within phyllite"),
]
CHAMBA_POROSITY = {
    "Paniyar Dhar": "Primary pore-space porosity in limestone plus secondary porosity from fracturing/weathering",
}
CHAMBA_MATCHES = {
    "Ganjrkhanal": "HIM-SPR-0413 (Ganjarkhala, Kaddukhal; name and location similar - not confirmed)",
}


def chamba_records():
    records = []
    for (spring, location, lat, lon, area, elev_range, elev, slope, aspect, litho, discharge, hp, aquifer) in CHAMBA_ROWS:
        table_loc = f"Spring Assesment Report.docx, 'Summary of all Sources' table, row {spring}"
        detail_loc = f"Spring Assesment Report.docx, parameter table, column {spring}"
        values = {
            "source_area_name": f"{location}, Tehri-Garhwal, Uttarakhand",
            "district": ("Tehri Garhwal", "descriptive", "From the report heading 'Venue: Chamba, Tehri-Garhwal'."),
            "spring_name": f"{spring} Spring",
            "latitude_source_value": (lat, "approximate", "Printed to 2 decimals (about 1 km precision)."),
            "longitude_source_value": (lon, "approximate", "Printed to 2 decimals (about 1 km precision)."),
            "elevation_m_source_value": (elev, "approximate", "Text says 'approximately'."),
            "slope_degrees_source_value": (slope, "reported", "Average slope of the micro-watershed, not of the spring point."),
            "slope_aspect_source_value": (aspect, "reported", "Dominant aspect of the micro-watershed."),
            "lithology_source_value": (litho, "descriptive", ""),
            "spring_type_source_value": (f"Rock spring; {aquifer}", "descriptive", "", detail_loc),
            "geological_structure_source_value": ("Garhwal Group; structurally controlled by the Tons Thrust", "descriptive", "", detail_loc),
            "discharge_lpm_source_value": (discharge, "reported", "Date, season and method of measurement not stated."),
            "rainfall_source_value": ("~1220", "approximate", "Area rainfall (Jun-Sep monsoon); same value for all seven sites.", detail_loc),
            "catchment_area_ha_source_value": (area, "delineated_estimate", "Micro-watershed (surface catchment) area; the report does not call it a recharge area."),
            "catchment_elevation_range_m_source_value": (elev_range, "delineated_estimate", ""),
            "handpump_discharge_lpm_source_value": (hp, "reported", "Nearby Direct Injection handpump at higher elevation; date and method not stated."),
            "intervention_source_value": ("Direct Injection artificial recharge fitted at nearby handpumps (installation date not stated)", "descriptive", "", detail_loc),
            "recharge_area_basis_source_value": ("Micro-watershed (surface catchment); recharge area not delineated separately", "descriptive", ""),
        }
        if spring in CHAMBA_POROSITY:
            values["porosity_source_value"] = (CHAMBA_POROSITY[spring], "descriptive", "", detail_loc)
        else:
            values["porosity_source_value"] = ("Negligible primary porosity; secondary porosity via fractures, joints and bedding planes", "descriptive", "", detail_loc)
        if spring in CHAMBA_MATCHES:
            values["candidate_match_record_ids"] = CHAMBA_MATCHES[spring]
        flag = "Verify: coordinates are rounded to about 1 km; discharge dates and methods are not stated; catchment is a surface micro-watershed, not a confirmed recharge area."
        if location == "Arakot region":
            flag += " The report places this site in 'Arakot region' (an Arakot is in Uttarkashi) but its coordinates fall near Chamba; confirm the location with WATSAN."
        records.append({
            "prefix": "RDI",
            "source_id": "SRC-003",
            "source_dataset": "RDI/WATSAN Chamba Hydrogeological Assessment Report - summary table",
            "source_record_locator": table_loc,
            "source_reference": CHAMBA_REF,
            "default_locator": table_loc,
            "values": values,
            "value_status_summary": "Location and elevation approximate; discharge reported without date or method; areas are surface micro-watersheds.",
            "staging_quality_flag": flag,
            "source_notes": "Transcribed from the report's summary and parameter tables; thousands separators removed.",
        })
    return records


# --------------------------------------------------------------------------- SRHU DI site assessment reports
SRHU_TITLE = ("Swami Rama Himalayan University (RDI/WATSAN). Scientific Hydrogeological Assessment Report - Impact Assessment "
              "of Direct Injection-Based Aquifer Recharge Technique for Spring Revival")


def dms(degrees, minutes, seconds):
    return f"{degrees + minutes / 60 + seconds / 3600:.6f}"


# Coordinates are printed in degrees-minutes-seconds; they are stored here in decimal degrees, and the long
# table note keeps the printed form. The handpump coordinates go in intervention_source_value.
SRHU_SITES = [
    {
        "source_id": "SRC-027", "file": "Badera Geohydrology  report.pdf",
        "area": "Badeda village, Narendra Nagar block, Tehri Garhwal, Uttarakhand", "block": "Narendra Nagar",
        "village": "Badeda (Badera)", "spring": "Badeda Spring",
        "lat": (30, 10, 17.26), "lon": (78, 18, 46.42), "hp_lat": (30, 10, 24.21), "hp_lon": (78, 18, 46.25),
        "hp_name": "Badeda handpump (Kunjapuri; report: 'upper recharge zone of the Kunjapuri Spring catchment')",
        "spring_type": "Fracture-controlled contact spring; fractured to semi-confined carbonate aquifer of the Krol Group",
        "lithology": "Limestone, dolomite and shale (Krol Group); aquifer table adds quartzite and sandstone (Blaini Group)",
        "structure": "Neoproterozoic Krol Group; groundwater controlled by fractures, joints and bedding planes; "
                     "Highly Dissected Structural Hills and Valleys",
        "porosity": "Secondary porosity through fractures, joints and weathering (soil effective porosity 25-40 %)",
        "area_ha": "40.51", "area_loc": "Figure 10, Land Use / Land Cover Statistics table (total)",
        "area_check": "The outline drawn on the report's other maps measures 12.4 ha (scripts/trace_report_catchments.py); "
                      "the land-use map that gives 40.51 ha looks redrawn (repeated grid labels, UTM 43N), so prefer 12.4 ha.",
        "elev_range": "1452–1614", "elev_loc": "Section 3.1",
        "land_use": "Catchment: dense forest 48.4 %, open forest 16.0 %, agriculture/terrace 25.7 %, built-up 5.2 %, "
                    "barren 3.2 %, road 1.5 % (Sentinel-2, 2025; the text says 66.91 % forest)",
        "slope_aspect": "Slope 5–36° (12–28° around the handpump); mostly south- to southwest-facing",
        "link": "The report places the handpump upslope of the spring in the same shallow fractured aquifer "
                "('only a few metres apart'; the printed coordinates are about 215 m apart).",
    },
    {
        "source_id": "SRC-028", "file": "Domsi & Makhdet Geohydrology report.pdf",
        "area": "Dungsi & Makhdet villages, Jaunpur block, Tehri Garhwal, Uttarakhand", "block": "Jaunpur",
        "village": "Makhdet (Dungsi & Makhdet; also spelt Madkhet, Domsi)", "spring": "Makhdet Spring",
        "lat": (30, 28, 57.86), "lon": (78, 14, 4.83), "hp_lat": (30, 28, 53.30), "hp_lon": (78, 14, 12.10),
        "hp_name": "Dungsi (Domsi) handpump",
        "spring_type": "Fracture-controlled gravity spring; unconfined to semi-confined fractured hard-rock aquifer",
        "lithology": "Quartzite, phyllite, slate and schist (Jaunsar Group; the aquifer table says Jaunpur Group)",
        "structure": "Neoproterozoic Jaunsar Group, Lesser Himalaya; groundwater controlled by fractures, joints, "
                     "foliation and bedding planes; Highly Dissected Hills and Valleys",
        "porosity": "Secondary porosity through fractures, joints, foliation and weathering (soil effective porosity 20-35 %)",
        "area_ha": "91.07", "area_loc": "Section 3.9 (delineated catchment)",
        "area_check": "The outline on the report's geology map measures 94.3 ha (scripts/trace_report_catchments.py).",
        "elev_range": "1461–2076", "elev_loc": "Sections 3.1 and 6.7 (section 3.5 gives about 1500–2050 from contours)",
        "land_use": "Catchment: dense forest 40.8 %, open forest 25.4 %, agriculture/terrace 22.6 %, built-up 4.3 %, "
                    "barren 3.5 %, road 1.3 %, water 0.3 % (Sentinel-2, 2025)",
        "slope_aspect": "Slope 5 to over 37° (5–15° around the spring and handpump); spring and handpump on northwest-facing slopes",
        "link": "The report places the handpump upslope of the spring in the same springshed, with 'probable hydraulic "
                "connectivity' through the fractured aquifer.",
    },
]


def srhu_records():
    records = []
    for site in SRHU_SITES:
        loc = f"{site['file']}, section 1 (Location and Site Characteristics)"
        printed = lambda d, m, sec, h: f"Printed as {d}°{m}'{sec}\"{h}; converted to decimal degrees."
        hp = f"{dms(*site['hp_lat'])}, {dms(*site['hp_lon'])}"
        values = {
            "source_area_name": site["area"],
            "district": "Tehri Garhwal",
            "block": site["block"],
            "village": site["village"],
            "spring_name": site["spring"],
            "latitude_source_value": (dms(*site["lat"]), "reported", printed(*site["lat"], "N")),
            "longitude_source_value": (dms(*site["lon"]), "reported", printed(*site["lon"], "E")),
            "land_use_source_value": (site["land_use"], "delineated_estimate", "", f"{site['file']}, section 3.9"),
            "spring_type_source_value": (site["spring_type"], "descriptive", "", f"{site['file']}, section 2"),
            "lithology_source_value": (site["lithology"], "descriptive", "", f"{site['file']}, sections 2, 3.6 and Table 1"),
            "geological_structure_source_value": (site["structure"], "descriptive", "", f"{site['file']}, sections 3.6-3.7"),
            "porosity_source_value": (site["porosity"], "descriptive", "", f"{site['file']}, Table 1"),
            "seasonality_source_value": ("Perennial", "reported", "Section 4 lists 'presence of a perennial spring'.", f"{site['file']}, section 4"),
            "catchment_area_ha_source_value": (site["area_ha"], "delineated_estimate",
                                               "Surface catchment from CartoDEM 30 m; not a confirmed recharge area. " + site["area_check"],
                                               f"{site['file']}, {site['area_loc']}"),
            "catchment_elevation_range_m_source_value": (site["elev_range"], "delineated_estimate", "", f"{site['file']}, {site['elev_loc']}"),
            "recharge_area_slope_aspect_source_value": (site["slope_aspect"], "descriptive", "", f"{site['file']}, sections 3.3-3.4"),
            "recharge_area_basis_source_value": ("Surface catchment from CartoDEM 30 m with thematic layers; the handpump area is "
                                                 "called the upper recharge zone", "descriptive", "", f"{site['file']}, section 3"),
            "intervention_source_value": (f"Rooftop rainwater harvesting with direct injection through the existing {site['hp_name']} "
                                          f"at {hp}, plus catchment treatment (trenches, recharge pits, check dams). {site['link']}",
                                          "reported", f"Handpump printed as {site['hp_lat'][0]}°{site['hp_lat'][1]}'{site['hp_lat'][2]}\"N "
                                          f"{site['hp_lon'][0]}°{site['hp_lon'][1]}'{site['hp_lon'][2]}\"E.", f"{site['file']}, sections 1-2 and 5"),
        }
        records.append({
            "prefix": "RDI",
            "source_id": site["source_id"],
            "source_dataset": "RDI/WATSAN (SRHU) DI site hydrogeological assessment report",
            "source_record_locator": loc,
            "source_reference": f"{SRHU_TITLE}: {site['area']} ({site['file']}, undated)",
            "default_locator": loc,
            "values": values,
            "value_status_summary": "Coordinates printed to 0.01 second; no discharge or water quality; areas are surface catchments.",
            "staging_quality_flag": "Verify: no spring discharge is reported; the catchment is a surface delineation, not a recharge area; "
                                    "the handpump-spring link is the report's interpretation.",
            "source_notes": "Transcribed from the report text and the land use table; coordinates converted from degrees-minutes-seconds.",
        })
    return records


# --------------------------------------------------------------------------- Daniel et al. (2021)
def daniel_records():
    p15 = "Daniel 2021 Table 6, PDF page 15"
    p16 = "Daniel 2021 Section 5 text, PDF page 16"
    values = {
        "source_area_name": ("Dhanaulti Tehsil, Tehri-Garhwal district, Uttarakhand", "descriptive", "", "Daniel 2021 Section 5, PDF page 13"),
        "district": ("Tehri-Garhwal", "descriptive", "", "Daniel 2021 Section 5, PDF page 13"),
        "spring_name": ("Mathamali spring", "descriptive", "", "Daniel 2021 Section 5, PDF page 13"),
        "discharge_dependable_q75_lpm_source_value": (
            "Water year 2014: 5.7; 2015: 13.44; 2016: 19.45", "measured",
            "75% dependable flow from hourly discharge monitoring Feb 2014 - Feb 2018 (source's ref. [48]).", p16,
        ),
        "intervention_source_value": (
            "Gabion check dam, contour trenches, artificial ponds (khals), tree/shrub/grass planting since 2010-11 by Garhwal Vikas Kendra in the recharge area",
            "reported", "", p16,
        ),
        "vulnerability_index_source_value": (
            "Aggregated VI 11.5; normalised VI 2.3 (precipitation 6.4 and 5.7, LULC 0.4, population 1.0, livestock -2.0)",
            "derived_by_source", "Index relative to Uttarakhand/region averages (Eq. 1).", p15,
        ),
        "candidate_match_record_ids": ("ATL-SPR-0944 (Mathamali Dhara, Tehri-Garhwal; name match - not confirmed)", "descriptive", "", p15),
    }
    return [{
        "prefix": "DAN",
        "source_id": "SRC-012",
        "source_dataset": "Daniel et al. 2021 - Mathamali spring case study",
        "source_record_locator": f"{p15}; {p16}",
        "source_reference": DANIEL_REF,
        "default_locator": p16,
        "values": values,
        "value_status_summary": "Dependable flow measured (logger); vulnerability index computed by the source; no coordinates published.",
        "staging_quality_flag": "Verify: no coordinates or elevation in the paper; dependable-flow rise is attributed by the authors to interventions without a control comparison.",
        "source_notes": "Single case-study spring. Flows are 75% dependable flows, not average discharge.",
    }]


# --------------------------------------------------------------------------- Spring Atlas profile pages
# Water quality table columns: pH, TDS, Salinity, Chloride, TH, Total Iron, Nitrate, FC, Discharge (lpm).
ATLAS_PROFILES = [
    {
        "spring": "Dhargara Dhara", "page": 16, "village": "Raikholi", "block": "Bageshwar", "district": "Bageshwar",
        "lat": "29.74577", "lon": "79.80541", "elev": "1550", "rain": "1350",
        "wq": ("7.32", "320", "190", "10", "156", "Nil", "1", "320", "10.66"),
        "type": "Karst spring", "litho": "Dolomite",
        "structure": "Dip towards NE, average 30 degrees; strike NW-SE",
        "recharge_ha": "2.5", "rech_slope": "Southwest slope of the spring",
        "series": "Jul 2014-Jun 2015: rain 2226 mm, avg 10.66 lpm; Jul 2015-Jun 2016: rain 1448 mm, avg 13.13 lpm; Jul 2016-Jun 2017: rain 1774 mm, avg 16.44 lpm",
        "intervention": "Treated 2 of 2.5 ha; contour trench 350 m, percolation pits 80.06 cum, loose boulder check dam 14.5 m, source work; implementation Oct 2014 - Mar 2015",
        "match": "ATL-SPR-0558",
        "fc_note": "FC printed as 320 under a column headed (mg/l); unit unclear.",
    },
    {
        "spring": "Ghatgarh Dhara", "page": 20, "village": "Chattola", "block": "Ramgarh", "district": "Nainital",
        "lat": "29.46619", "lon": "79.58108", "elev": "1850", "rain": "1200",
        "wq": ("6.4", "110", "80", "20", "48", "NIL", "NIL", "YES", "2.26"),
        "type": "Spring from saturated unconsolidated colluvial deposit (primary aquifer); fractured schist may contribute", "litho": "Schist",
        "structure": "Strike NW-SE, dip towards NE, average 25 degrees; fracture sets N-S and NE-SW",
        "recharge_ha": "3", "rech_slope": "Recharge area slope 26.8%, aspect NNE",
        "series": "Jul 2013-Jun 2014: rain 1119 mm, avg 2.26 lpm; Jul 2014-Jun 2015: rain 1473 mm, avg 4.03 lpm; Jul 2015-Jun 2016: rain 216 mm, avg 1.77 lpm; Jul 2016-Jun 2017: rain 941 mm, avg 2.81 lpm",
        "intervention": "Treated 1.5 of 3.1 ha (treatment plan figure; recharge section says 3 ha); percolation pit 350 m, CWR tank 1, terrace levelling 534 sqm; implementation Aug 2014 - Mar 2015",
        "match": "ATL-SPR-0048",
    },
    {
        "spring": "Salkuli Naula", "page": 24, "village": "Salkuli", "block": "Ramgarh", "district": "Nainital",
        "lat": "29.50679", "lon": "79.56997", "elev": "1310", "rain": "750",
        "wq": ("7", "200", "125", "32", "96", "0.01", "1", "YES", "3.55"),
        "type": "Fracture spring", "litho": "Alternate layers of phyllite and quartzite",
        "structure": "Dip towards NE, average 40 degrees; strike NW-SE; fracture sets NE-SW and SE-NW",
        "recharge_ha": "5", "rech_slope": "Recharge area slope about 36.4%, aspect NW",
        "series": "Pre-implementation: avg 2.61 lpm with total rainfall 2037.8 mm; post-implementation: avg 2.48 lpm with rainfall 1017.7 mm; lean-season minimum 1.08 lpm (2015), 1.56 lpm (2016), 1.29 lpm (2017)",
        "intervention": "Treated 3 of 5 ha; RRH recharge pits 4, deep recharge pits 78, percolation pit 2.10 cum, protection wall 4.75 m, naula work; implementation Dec 2015 - Mar 2016",
        "match": "ATL-SPR-0034",
        "elev_note": "Altitude given for the village.",
    },
    {
        "spring": "Kulgarh Naula", "page": 28, "village": "Kulgarh", "gp": "Simra", "block": "", "district": "Nainital",
        "lat": "29.52465", "lon": "79.57412", "elev": "1140", "rain": "750",
        "wq": ("7.52", "170", "100", "16", "96", "3", "1", "YES", "30"),
        "type": "Fracture spring", "litho": "Alternate bands of phyllite and quartzite",
        "structure": "Dip towards NE, 15-50 degrees; strike 290N to 155N; fracture sets N-S and E-W",
        "recharge_ha": "7.92", "rech_slope": "Recharge area slope about 22%, aspect NWW",
        "series": "Lean-season minimum 6 lpm (Apr-Jun 2013), 9 lpm at implementation (Apr 2014), 6 lpm (lean season 2017); discharge/rainfall ratio 0.009 pre and 0.027 post",
        "intervention": "Treatment area 5.79 of 7.92 ha; sub-surface check dam 5.2 m, loose boulder check dam 20 m, contour trenches 1699 m, protection wall 9 m, percolation pit 30 cum, khal 174 cum, khal drainage 135 m, 500 plants; implementation May 2014 - Jul 2015",
        "match": "ATL-SPR-0029",
        "elev_note": "Altitude given for the village.",
    },
    {
        "spring": "Mouna Talla Dhara", "page": 32, "village": "Mouna", "block": "Ramgarh", "district": "Nainital",
        "lat": "29.52994", "lon": "79.65630", "elev": "1350", "rain": "1050",
        "wq": ("6.44", "110", "70", "16", "96", "0.01", "NIL", "YES", "7.55"),
        "type": "Fracture spring", "litho": "Alternate bands of phyllite and quartzite and gneiss",
        "structure": "Dip towards N, average 35 degrees; strike NE-SW; fracture sets N-S and E-W",
        "recharge_ha": "9", "rech_slope": "Recharge area slope 15.7%, aspect NNE",
        "series": "Lean-season minimum average 7.55 lpm (2013), 16 lpm (2014), 7 lpm (2015); 7.27 lpm pre-implementation vs 9.04 lpm post-implementation (2016); 15.02 lpm next monsoon",
        "intervention": "Treated 8 of 9 ha; deep recharge pits; implementation Nov 2015 - Feb 2016",
        "match": "ATL-SPR-0042",
        "elev_note": "Average elevation of the area.",
    },
    {
        "spring": "Dansil Naula", "page": 36, "village": "Losgyani", "block": "Ramgarh", "district": "Nainital",
        "lat": "29.46588", "lon": "79.57100", "elev": "2100", "rain": "1200",
        "wq": ("6.4", "110", "80", "20", "48", "NIL", "1", "YES", "0.68"),
        "type": "Fracture spring", "litho": "Alternating bands of phyllite and quartzite",
        "structure": "Bands run E-W, dip towards SE, about 30 degrees; fracture sets NE-SW and SE-NW",
        "recharge_ha": "5", "rech_slope": "Recharge area slope 45.8%, aspect SE",
        "series": "Pre-implementation minimum 0.68 lpm; 4.3 lpm in summer 2015; 2015-16 flow fell 55% in winter and 74% in summer after a 91% rainfall drop",
        "intervention": "Treated 3.5 of 5 ha; implementation Oct 2014 - Jan 2015",
        "match": "ATL-SPR-0012",
    },
    {
        "spring": "Basgaon School Naula", "page": 40, "village": "Basgaon", "block": "Ramgarh", "district": "Nainital",
        "lat": "29.50555", "lon": "79.55235", "elev": "1370", "rain": "750",
        "wq": ("6.9", "490", "340", "48", "240", "3", "1", "YES", "8.25"),
        "type": "Depression spring", "litho": "Quartzite, phyllite and dolomite with unconsolidated colluvium (main aquifer)",
        "structure": "",
        "recharge_ha": "4.08", "rech_slope": "Recharge area slope 30.9%, aspect NEE",
        "series": "Jul 2013-Jun 2014: rain 600 mm, avg 14.18 lpm; Jul 2014-Jun 2015: rain 808 mm, avg 26.15 lpm; Jul 2015-Jun 2016: rain 483 mm, avg 36.10 lpm",
        "intervention": "Treatment plan says recharge area 8.5 ha of which 4.08 ha treated; percolation pits, khals, check dams, naula repair, contour trenches, terrace levelling 2010 sqm; implementation Dec 2014 - May 2015",
        "match": "ATL-SPR-0032",
        "elev_note": "Average elevation of the village.",
        "rech_note": "Recharge section gives 4.08 ha total; treatment plan gives 8.5 ha total with 4.08 ha treated. Source is internally inconsistent.",
    },
    {
        "spring": "Para Naula", "page": 44, "village": "Harinagar", "block": "Ramgarh", "district": "Nainital",
        "lat": "29.47552", "lon": "79.59597", "elev": "1800", "rain": "1200",
        "wq": ("6.5", "210", "140", "32", "80", "NIL", "NIL", "YES", "2.48"),
        "type": "Fracture spring", "litho": "Alternate bands of phyllite and quartzite",
        "structure": "Dip towards NE, average 30 degrees; strike NW-SE; fracture sets N-S and SE-NW",
        "recharge_ha": "8", "rech_slope": "Recharge area slope 28.6%, aspect NNE",
        "series": "Declining through monitoring; 1.35 lpm in winter 2016; 1.56 lpm in winter 2017",
        "intervention": "Treated 4.5 of 8 ha (about 2-2.5 ha under reserve forest not treated); implementation Sep 2014 - May 2015",
        "match": "",
        "elev_note": "Average elevation of the area.",
    },
    {
        "spring": "Meherkhola Dhara", "page": 48, "village": "Meherkhola", "block": "Ramgarh", "district": "Nainital",
        "lat": "29.5297778", "lon": "79.65472", "elev": "1350", "rain": "1050",
        "wq": ("6.41", "50", "40", "16", "48", "0.01", "NIL", "YES", "6.83"),
        "type": "Fracture spring", "litho": "Alternate bands of phyllite, gneiss and quartzite",
        "structure": "Dip towards N, average 40 degrees; strike NW-SE; fracture sets N-S and NE-SW",
        "recharge_ha": "12", "rech_slope": "Recharge area slope 17.6%, aspect NE",
        "series": "Declining, especially peak discharge; rainfall fell by 1257 mm in Jul 2015-Jun 2016; lean-period discharge rose 0.31 lpm from 2016 to 2017",
        "intervention": "10 of 12 ha made available for treatment; implementation Jul 2014 - Mar 2015; source notes diversion at source and a hospital built in the recharge area",
        "match": "ATL-SPR-0040",
        "elev_note": "Average elevation of the area.",
    },
    {
        "spring": "Naghar Naula", "page": 52, "village": "Naghar", "block": "Bageshwar", "district": "Bageshwar",
        "lat": "29.78020", "lon": "79.77740", "elev": "1800", "rain": "1350",
        "wq": ("7.22", "360", "210", "40", "320", "0.01", "1", "YES", "1.76"),
        "type": "Karst spring", "litho": "Dolomite and slate",
        "structure": "Dip towards NE, average 40 degrees; strike NW-SE",
        "recharge_ha": "7", "rech_slope": "Recharge area slope about 21.2%, aspect NE",
        "series": "Lean-season average 1.76 lpm rose to 2.6 lpm in Jul 2014-Jun 2015; lean season 2017 1.6 lpm; annual average 10.66 lpm (2017) vs 2.23 lpm (2016)",
        "intervention": "Implementation Oct 2014 - Jul 2015; treatment-plan text (12 ha, 10 ha treated, Chapad village) appears copied from another profile",
        "match": "ATL-SPR-0560",
        "elev_note": "Average elevation of the area.",
        "rech_note": "Recharge section says about 7 ha; treatment plan says 12 ha. Source is internally inconsistent.",
    },
]


def atlas_records():
    records = []
    for p in ATLAS_PROFILES:
        start = p["page"]
        recon = f"Spring Atlas PDF page {start} (reconnaissance survey), {p['spring']}"
        hydro = f"Spring Atlas PDF page {start + 1} (hydrogeology), {p['spring']}"
        impl = f"Spring Atlas PDF page {start + 2} (implementation), {p['spring']}"
        impact = f"Spring Atlas PDF page {start + 3} (impacts), {p['spring']}"
        ph, tds, salinity, chloride, th, iron, nitrate, fc, discharge = p["wq"]
        wq_other = (f"Salinity {salinity} mg/l; chloride {chloride} mg/l; total hardness {th} mg/l; "
                    f"total iron {iron} mg/l; nitrate {nitrate} mg/l; faecal coliform {fc}")
        values = {
            "district": (p["district"], "descriptive", "", recon),
            "block": (p["block"], "descriptive", "", recon),
            "gram_panchayat": (p.get("gp", ""), "descriptive", "", recon),
            "village": (p["village"], "descriptive", "", recon),
            "spring_name": (p["spring"], "descriptive", "", recon),
            "latitude_source_value": (p["lat"], "reported", "", recon),
            "longitude_source_value": (p["lon"], "reported", "", recon),
            "elevation_m_source_value": (p["elev"], "approximate", p.get("elev_note", "Text says 'around'."), recon),
            "rainfall_source_value": (p["rain"], "approximate", "Average annual rainfall of the village.", recon),
            "ph_source_value": (ph, "reported", "Sampling date not stated.", recon),
            "tds_source_value": (tds, "reported", "Sampling date not stated.", recon),
            "water_quality_other_source_value": (wq_other, "reported", p.get("fc_note", "Sampling date not stated."), recon),
            "discharge_lpm_source_value": (discharge, "reported", "Value in the profile's water quality and discharge table; date not stated.", recon),
            "spring_type_source_value": (p["type"], "descriptive", "", hydro),
            "lithology_source_value": (p["litho"], "descriptive", "", hydro),
            "geological_structure_source_value": (p["structure"], "descriptive", "", hydro),
            "recharge_area_ha_source_value": (p["recharge_ha"], "delineated_estimate", p.get("rech_note", "Recharge area identified by hydrogeological survey."), hydro),
            "recharge_area_basis_source_value": ("Hydrogeological field survey (CHIRAG/ACWADAM springshed protocol)", "descriptive", "", hydro),
            "recharge_area_slope_aspect_source_value": (p["rech_slope"], "reported", "Slope of the recharge area, not of the spring point.", hydro),
            "discharge_annual_series_source_value": (p["series"], "measured", "From the profile's impact text/table; monitoring method not described.", impact),
            "intervention_source_value": (p["intervention"], "reported", "", impl),
        }
        if p["match"]:
            values["candidate_match_record_ids"] = (f"{p['match']} (Atlas annexure row with matching name/coordinates)", "descriptive", "", recon)
        records.append({
            "prefix": "ATP",
            "source_id": "SRC-008",
            "source_dataset": "Spring Atlas of Uttarakhand - representative spring profiles",
            "source_record_locator": f"Spring Atlas PDF pages {start}-{start + 3}; {p['spring']}",
            "source_reference": ATLAS_REF,
            "default_locator": recon,
            "values": values,
            "value_status_summary": "Coordinates and water quality reported without date; recharge area from field hydrogeology; discharge series from monitoring before and after recharge works.",
            "staging_quality_flag": "Verify: confirm against the cited PDF pages; sampling dates and monitoring methods are not given; pre/post comparisons have no control spring.",
            "source_notes": "Profile-page values. The same spring also appears in the Atlas annexure inventory (see candidate_match_record_ids); rows are not merged.",
        })
    return records


def _normalise(entry, default_locator):
    if isinstance(entry, str):
        return entry, "descriptive", "", default_locator
    value, status, note, *rest = entry
    return value, status, note, (rest[0] if rest else default_locator)


def build(common_columns, point_wkt):
    """Return (wide_records, long_records) for all literature sources."""
    raw = rathi_records() + chamba_records() + daniel_records() + atlas_records() + srhu_records()
    counters = {}
    wide, long_rows = [], []
    for item in raw:
        counters[item["prefix"]] = counters.get(item["prefix"], 0) + 1
        record_id = f"{item['prefix']}-SPR-{counters[item['prefix']]:04d}"
        row = {column: "" for column in common_columns}
        row.update({
            "record_id": record_id,
            "source_id": item["source_id"],
            "source_dataset": item["source_dataset"],
            "source_record_locator": item["source_record_locator"],
            "source_reference": item["source_reference"],
            "value_status_summary": item["value_status_summary"],
            "staging_quality_flag": item["staging_quality_flag"],
            "source_notes": item["source_notes"],
        })
        for field, entry in item["values"].items():
            if field not in row:
                raise KeyError(f"Unknown field {field} for {record_id}")
            value, status, note, locator = _normalise(entry, item["default_locator"])
            row[field] = value
            if value:
                long_rows.append({
                    "record_id": record_id,
                    "field": field,
                    "value_as_printed": value,
                    "unit": UNITS.get(field, ""),
                    "value_status": status,
                    "source_id": item["source_id"],
                    "source_locator": locator,
                    "note": note,
                })
        row["geometry_wkt"] = point_wkt(row["longitude_source_value"], row["latitude_source_value"])
        wide.append(row)
    return wide, long_rows
