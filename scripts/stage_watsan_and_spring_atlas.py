"""Create reproducible CSV staging extracts for the WATSAN workbook and Spring Atlas PDF.

This script intentionally preserves source values as text. It does not clean,
deduplicate, correct, or infer source records.
"""

import csv
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import pdfplumber

import field_visit_spring_records as field_visit
import literature_spring_records as literature


ROOT = Path(__file__).resolve().parents[1]
RAW_WATSAN = ROOT / "data" / "00_raw" / "watsan" / "Discharge_Spring_Data.xlsx"
RAW_ATLAS = ROOT / "data" / "00_raw" / "spring_atlas" / "Spring_ATLAS_of_Uttarakhand.pdf"
RAW_HIMMOTTHAN = ROOT / "data" / "00_raw" / "himmotthan" / "Himmotthan_Geo-Locator.kml"
STAGED = ROOT / "data" / "01_staged"
WATSAN_DIR = STAGED / "watsan"
ATLAS_DIR = STAGED / "spring_atlas"
HIMMOTTHAN_DIR = STAGED / "himmotthan"
LITERATURE_DIR = STAGED / "literature"
COMMON_DIR = STAGED / "common"

COMMON_COLUMNS = [
    "record_id",
    "source_id",
    "source_dataset",
    "source_record_locator",
    "source_area_name",
    "district",
    "block",
    "gram_panchayat",
    "village",
    "spring_name",
    "latitude_source_value",
    "longitude_source_value",
    "elevation_m_source_value",
    "land_use_source_value",
    "slope_aspect_source_value",
    "slope_degrees_source_value",
    "lithology_source_value",
    "spring_type_source_value",
    "tds_source_value",
    "ph_source_value",
    "discharge_lpm_source_value",
    "rainfall_source_value",
    "seasonality_source_value",
    "rock_type_source_value",
    "geological_structure_source_value",
    "porosity_source_value",
    "permeability_source_value",
    "recharge_area_ha_source_value",
    "geometry_wkt",
    "staging_quality_flag",
    "source_notes",
] + literature.LITERATURE_COLUMNS

LONG_COLUMNS = [
    "record_id",
    "field",
    "value_as_printed",
    "unit",
    "value_status",
    "source_id",
    "source_locator",
    "note",
]


def text(value):
    if value is None:
        return ""
    return str(value).strip()


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, quoting=csv.QUOTE_ALL, lineterminator="\n", restval="")
        writer.writeheader()
        writer.writerows(rows)


def point_wkt(longitude, latitude):
    if not longitude or not latitude:
        return ""
    return f"POINT ({longitude} {latitude})"


def extract_watsan():
    sheets = pd.read_excel(RAW_WATSAN, sheet_name=None, dtype=str, keep_default_na=False)
    sheet_manifest = []
    for name, dataframe in sheets.items():
        output_path = WATSAN_DIR / "csv" / "source_sheets" / f"watsan_{name.lower().replace(' ', '_')}_source_v1.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(output_path, index=False, encoding="utf-8", quoting=csv.QUOTE_ALL)
        sheet_manifest.append({
            "source_sheet": name,
            "records": len(dataframe),
            "columns": len(dataframe.columns),
            "output_csv": str(output_path.relative_to(ROOT)).replace("\\", "/"),
        })

    all_parameter = sheets["All_Parameter"].fillna("")
    records = []
    for position, (_, row) in enumerate(all_parameter.iterrows(), start=2):
        latitude = text(row.get("Latitude"))
        longitude = text(row.get("Longitude"))
        records.append({
            "record_id": f"WAT-SPR-{position - 1:04d}",
            "source_id": "SRC-001",
            "source_dataset": "WATSAN Discharge Spring Data - All_Parameter",
            "source_record_locator": f"All_Parameter row {position}",
            "source_area_name": text(row.get("Area_name")),
            "district": "",
            "block": "",
            "gram_panchayat": "",
            "village": "",
            "spring_name": "",
            "latitude_source_value": latitude,
            "longitude_source_value": longitude,
            "elevation_m_source_value": text(row.get("elevation")),
            "land_use_source_value": text(row.get("lulc")),
            "slope_aspect_source_value": text(row.get("aspect")),
            "slope_degrees_source_value": text(row.get("slope_deg")),
            "lithology_source_value": "",
            "spring_type_source_value": text(row.get("spring_typology")),
            "tds_source_value": "",
            "ph_source_value": "",
            "discharge_lpm_source_value": text(row.get("discharge_lpm")),
            "rainfall_source_value": text(row.get("rainfall")),
            "seasonality_source_value": text(row.get("seasonality")),
            "rock_type_source_value": text(row.get("rock_type")),
            "geological_structure_source_value": text(row.get("Geological structure")),
            "porosity_source_value": text(row.get("Porosity")),
            "permeability_source_value": text(row.get("Permeability")),
            "recharge_area_ha_source_value": text(row.get("recharge_area_ha")),
            "geometry_wkt": point_wkt(longitude, latitude),
            "staging_quality_flag": "Verify: provenance, measurement status, labels, spatial coverage, and land-use coding have not been audited.",
            "source_notes": "Mapped from source sheet All_Parameter. Area_name is retained as a source area label, not assumed to be a spring name.",
        })

    write_csv(WATSAN_DIR / "csv" / "watsan_spring_records_common_v1.csv", COMMON_COLUMNS, records)
    return records, sheet_manifest


def join_words(words):
    if not words:
        return ""
    ordered = sorted(words, key=lambda word: word["x0"])
    result = ordered[0]["text"]
    previous_x1 = ordered[0]["x1"]
    for word in ordered[1:]:
        gap = word["x0"] - previous_x1
        result += ("" if gap <= 1.5 else " ") + word["text"]
        previous_x1 = word["x1"]
    return result.strip()


def classify_words(words):
    buckets = [[] for _ in range(7)]
    for word in words:
        x = word["x0"]
        index = 0 if x < 90 else 1 if x < 180 else 2 if x < 290 else 3 if x < 430 else 4 if x < 600 else 5 if x < 665 else 6 if x < 750 else 7
        if index == 7:
            buckets[6].append(word)
        else:
            buckets[index].append(word)
    return [join_words(bucket) for bucket in buckets]


def extract_spring_atlas():
    records = []
    with pdfplumber.open(RAW_ATLAS) as pdf:
        # PDF pages 57-82 are the annexure inventory. This is a layout-based extract.
        for page_number in range(57, 83):
            words = pdf.pages[page_number - 1].extract_words()
            lines = {}
            for word in words:
                key = round(word["top"] * 2) / 2
                lines.setdefault(key, []).append(word)
            for line_words in lines.values():
                values = classify_words(line_words)
                serial, district, gram_panchayat, village, spring_name, latitude, longitude_altitude = values
                if not serial.isdigit():
                    continue
                match = re.match(r"^(\S+)\s+(\S+)$", longitude_altitude)
                # Longitude and altitude are different x-buckets; preserve the fields independently below.
                longitude_words = [word for word in line_words if 665 <= word["x0"] < 750]
                altitude_words = [word for word in line_words if word["x0"] >= 750]
                longitude = join_words(longitude_words)
                altitude = join_words(altitude_words)
                if not (district and latitude and longitude):
                    continue
                flag = "Verify: extracted from PDF inventory table; confirm against source page before use."
                try:
                    lat_number = float(latitude)
                    lon_number = float(longitude)
                    if not (28 <= lat_number <= 32 and 76 <= lon_number <= 82):
                        flag = "Verify: extracted from PDF inventory table; coordinate lies outside expected Uttarakhand range and may be a source or extraction error."
                except ValueError:
                    flag = "Verify: extracted from PDF inventory table; coordinate is not parseable as a number."
                records.append({
                    "record_id": f"ATL-SPR-{int(serial):04d}",
                    "source_id": "SRC-008",
                    "source_dataset": "Spring Atlas of Uttarakhand - Annexure Spring Inventory",
                    "source_record_locator": f"PDF page {page_number}; S.No. {serial}",
                    "source_area_name": "",
                    "district": district,
                    "block": "",
                    "gram_panchayat": gram_panchayat,
                    "village": village,
                    "spring_name": spring_name,
                    "latitude_source_value": latitude,
                    "longitude_source_value": longitude,
                    "elevation_m_source_value": altitude,
                    "land_use_source_value": "",
                    "slope_aspect_source_value": "",
                    "slope_degrees_source_value": "",
                    "lithology_source_value": "",
                    "spring_type_source_value": "",
                    "tds_source_value": "",
                    "ph_source_value": "",
                    "discharge_lpm_source_value": "",
                    "rainfall_source_value": "",
                    "seasonality_source_value": "",
                    "rock_type_source_value": "",
                    "geological_structure_source_value": "",
                    "porosity_source_value": "",
                    "permeability_source_value": "",
                    "recharge_area_ha_source_value": "",
                    "geometry_wkt": point_wkt(longitude, latitude),
                    "staging_quality_flag": flag,
                    "source_notes": "Fields transcribed from the annexure inventory table. No profile-page measurements were inferred or added.",
                })

    if not records:
        raise RuntimeError("No Spring Atlas inventory records were extracted.")
    write_csv(ATLAS_DIR / "csv" / "spring_atlas_inventory_common_v1.csv", COMMON_COLUMNS, records)
    return records


def extract_himmotthan():
    namespace = {"k": "http://www.opengis.net/kml/2.2"}
    root = ET.parse(RAW_HIMMOTTHAN).getroot()
    spring_folder = next(
        folder for folder in root.findall(".//k:Folder", namespace)
        if (folder.findtext("k:name", default="", namespaces=namespace) or "").strip() == "Springs.xlsx"
    )
    records = []
    for feature_index, placemark in enumerate(spring_folder.findall(".//k:Placemark", namespace), start=1):
        attributes = {
            data.attrib.get("name", ""): text(data.findtext("k:value", default="", namespaces=namespace))
            for data in placemark.findall("./k:ExtendedData/k:Data", namespace)
        }
        coordinate_text = text(placemark.findtext(".//k:Point/k:coordinates", default="", namespaces=namespace))
        longitude, latitude = (coordinate_text.split(",") + ["", ""])[:2]
        records.append({
            "record_id": f"HIM-SPR-{feature_index:04d}",
            "source_id": "SRC-007",
            "source_dataset": "Himmotthan Geo-Locator - Springs.xlsx layer",
            "source_record_locator": f"KML Springs.xlsx Placemark {feature_index}",
            "source_area_name": "",
            "district": attributes.get("District", ""),
            "block": attributes.get("Block", ""),
            "gram_panchayat": "",
            "village": attributes.get("Village_Name", ""),
            "spring_name": text(placemark.findtext("k:name", default="", namespaces=namespace)),
            "latitude_source_value": text(latitude),
            "longitude_source_value": text(longitude),
            "elevation_m_source_value": attributes.get("Altitude", ""),
            "land_use_source_value": attributes.get("Land_use", ""),
            "slope_aspect_source_value": attributes.get("Slope_Aspect", ""),
            "slope_degrees_source_value": attributes.get("Slope", ""),
            "lithology_source_value": attributes.get("Lithology", ""),
            "spring_type_source_value": attributes.get("Spring_Type", ""),
            "tds_source_value": attributes.get("TDS", ""),
            "ph_source_value": attributes.get("pH", ""),
            "discharge_lpm_source_value": attributes.get("Discharge (LPM)", ""),
            "rainfall_source_value": "",
            "seasonality_source_value": "",
            "rock_type_source_value": "",
            "geological_structure_source_value": "",
            "porosity_source_value": "",
            "permeability_source_value": "",
            "recharge_area_ha_source_value": "",
            "geometry_wkt": point_wkt(text(longitude), text(latitude)),
            "staging_quality_flag": "Verify: supplied Himmotthan map export; confirm provenance, measurement conditions, and field relevance before analysis.",
            "source_notes": "Mapped from the KML Springs.xlsx layer. Source values retained without cleaning or deduplication.",
        })
    if not records:
        raise RuntimeError("No Himmotthan Springs.xlsx KML records were extracted.")
    write_csv(HIMMOTTHAN_DIR / "csv" / "himmotthan_spring_records_common_v1.csv", COMMON_COLUMNS, records)
    return records


def stage_literature():
    records, long_rows = literature.build(COMMON_COLUMNS, point_wkt)
    write_csv(LITERATURE_DIR / "csv" / "literature_spring_records_common_v1.csv", COMMON_COLUMNS, records)
    write_csv(LITERATURE_DIR / "csv" / "literature_spring_values_long_v1.csv", LONG_COLUMNS, long_rows)
    return records, long_rows


def main():
    watsan_records, sheet_manifest = extract_watsan()
    atlas_records = extract_spring_atlas()
    himmotthan_records = extract_himmotthan()
    literature_records, literature_values = stage_literature()
    field_records = field_visit.build(COMMON_COLUMNS, point_wkt)
    all_records = watsan_records + atlas_records + himmotthan_records + literature_records + field_records
    write_csv(COMMON_DIR / "csv" / "spring_records_common_v1.csv", COMMON_COLUMNS, all_records)
    metadata = {
        "common_schema_columns": COMMON_COLUMNS,
        "watsan_source_sheet_exports": sheet_manifest,
        "watsan_common_records": len(watsan_records),
        "spring_atlas_common_records": len(atlas_records),
        "himmotthan_common_records": len(himmotthan_records),
        "literature_common_records": len(literature_records),
        "literature_long_values": len(literature_values),
        "literature_records_by_source_dataset": {
            name: sum(1 for record in literature_records if record["source_dataset"] == name)
            for name in dict.fromkeys(record["source_dataset"] for record in literature_records)
        },
        "field_visit_common_records": len(field_records),
        "combined_common_records": len(all_records),
        "notes": [
            "All source values are retained as text in the common schema.",
            "The Spring Atlas extract is a PDF table transcription and remains Verify until checked against its cited page.",
            "The WATSAN records are not validated ground truth and must not be used for target-derived features or model training without the prescribed audit.",
            "Literature records (RAT, RDI, DAN, ATP prefixes) are transcribed from papers and reports; each value's source page/table and status is in data/01_staged/literature/csv/literature_spring_values_long_v1.csv.",
            "Literature columns are appended after source_notes and are blank for WATSAN, Spring Atlas annexure and Himmotthan rows.",
            "Field visit records (FLD prefix) are springs first seen on the October 2026 DoCC field visit; see data/01_staged/field_visit/README.md.",
        ],
    }
    metadata_dir = COMMON_DIR / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "spring_records_common_v1_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
