import json
import sqlite3
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(obj):
    return json.dumps(obj, ensure_ascii=False, allow_nan=False)


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS site_versions(id INTEGER PRIMARY KEY,site_id TEXT REFERENCES sites(id),data TEXT NOT NULL,saved_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS visits(id TEXT PRIMARY KEY,site_id TEXT NOT NULL REFERENCES sites(id),status TEXT NOT NULL CHECK(status IN ('draft','submitted')),visit_date TEXT,data TEXT NOT NULL,supersedes TEXT REFERENCES visits(id),created_at TEXT NOT NULL,saved_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_visit_correction ON visits(supersedes) WHERE supersedes IS NOT NULL AND status='submitted';
CREATE INDEX IF NOT EXISTS site_visits ON visits(site_id,visit_date);
CREATE TABLE IF NOT EXISTS attachments(id TEXT PRIMARY KEY,site_id TEXT NOT NULL REFERENCES sites(id),visit_id TEXT REFERENCES visits(id),data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS weather_cache(coords_key TEXT PRIMARY KEY,data TEXT NOT NULL,raw_json TEXT NOT NULL,sha256 TEXT NOT NULL,fetched_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS weather_jobs(site_id TEXT PRIMARY KEY REFERENCES sites(id),data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY,request_hash TEXT NOT NULL,response TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_records(id TEXT PRIMARY KEY,site_id TEXT REFERENCES sites(id),visit_id TEXT REFERENCES visits(id),data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_observations(id TEXT PRIMARY KEY,site_id TEXT REFERENCES sites(id),data TEXT NOT NULL);
"""
# Public source checkout starts empty; field records stay local.
STARTERS = []


class Store:
    def __init__(self, path, seed=True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO meta VALUES('schema_version','2')")
            if db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] != "2":
                raise ValueError("Unsupported database version. Keep a backup before changing versions.")
            if seed and not db.execute("SELECT value FROM meta WHERE key='starter_names'").fetchone():
                for sid, name, village in STARTERS:
                    site = {
                        "id": sid,
                        "name": name,
                        "spring_name": name,
                        "village": village,
                        "district": "",
                        "handpump_name": "",
                        "latitude": None,
                        "longitude": None,
                        "gps_later": True,
                        "setup_complete": False,
                        "registered_at": now(),
                        "updated_at": now(),
                        "note": "Name kept from the earlier project discussion. Complete the site details before adding visits.",
                    }
                    db.execute("INSERT OR IGNORE INTO sites VALUES(?,?)", (sid, encode(site)))
                db.execute("INSERT INTO meta VALUES('starter_names','1')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def state(self):
        with self.connect() as db:
            result = {
                t: [json.loads(r["data"]) for r in db.execute(f"SELECT data FROM {t} ORDER BY rowid")]
                for t in ("sites", "visits", "attachments", "weather_jobs", "evidence_records", "source_observations")
            }
            # Every list on the dashboard follows site order, so keep it A to Z by name.
            result["sites"].sort(key=lambda s: (s.get("name") or s.get("spring_name") or "").strip().lower())
            result["weather"] = {
                r["coords_key"]: json.loads(r["data"])
                for r in db.execute("SELECT coords_key,data FROM weather_cache")
            }
        return result

    def site(self, sid):
        return next((s for s in self.state()["sites"] if s["id"] == sid), None)

    def save_site(self, site):
        with self.connect() as db:
            db.execute(
                "INSERT INTO sites VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (site["id"], encode(site)),
            )
            db.execute(
                "INSERT INTO site_versions(site_id,data,saved_at) VALUES(?,?,?)",
                (site["id"], encode(site), now()),
            )
        return site

    def save_visit(self, v, key=None, request_hash=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if key:
                row = db.execute("SELECT request_hash,response FROM requests WHERE key=?", (key,)).fetchone()
                if row:
                    if row["request_hash"] != request_hash:
                        raise ValueError("This save key was already used for different information.")
                    return json.loads(row["response"])
            old = db.execute("SELECT status FROM visits WHERE id=?", (v["id"],)).fetchone()
            if old and old["status"] == "submitted":
                raise ValueError(
                    "Saved visits are kept unchanged. Use Correct this visit to add a new version."
                )
            db.execute(
                "INSERT INTO visits VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET site_id=excluded.site_id,status=excluded.status,visit_date=excluded.visit_date,data=excluded.data,supersedes=excluded.supersedes,saved_at=excluded.saved_at",
                (
                    v["id"],
                    v["site_id"],
                    v["status"],
                    v.get("visit_date"),
                    encode(v),
                    v.get("supersedes"),
                    v["created_at"],
                    v["saved_at"],
                ),
            )
            if key:
                db.execute("INSERT INTO requests VALUES(?,?,?)", (key, request_hash, encode(v)))
        return v

    def job(self, sid, data):
        with self.connect() as db:
            db.execute(
                "INSERT INTO weather_jobs VALUES(?,?) ON CONFLICT(site_id) DO UPDATE SET data=excluded.data",
                (sid, encode({"site_id": sid, **data})),
            )

    def weather(self, key, data, raw, sha):
        with self.connect() as db:
            db.execute(
                "INSERT INTO weather_cache VALUES(?,?,?,?,?) ON CONFLICT(coords_key) DO UPDATE SET data=excluded.data,raw_json=excluded.raw_json,sha256=excluded.sha256,fetched_at=excluded.fetched_at",
                (key, encode(data), raw, sha, now()),
            )

    def attachment(self, a):
        with self.connect() as db:
            db.execute(
                "INSERT INTO attachments VALUES(?,?,?,?)",
                (a["id"], a["site_id"], a.get("visit_id"), encode(a)),
            )

    def evidence(self, e):
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO evidence_records VALUES(?,?,?,?)",
                (e["id"], e["site_id"], e.get("visit_id"), encode(e)),
            )

    def backup(self, path):
        with self.connect() as src, closing(sqlite3.connect(path)) as dst:
            src.backup(dst)

    def import_records(self, digest, sites, visits, evidence, observations):
        """Load the WATSAN DI data file. Imported visits, evidence and observations are replaced as a set.
        A site edited in the portal keeps the portal version; portal visits are never touched. Imported sites no
        longer in the file are removed."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM meta WHERE key='watsan_import'").fetchone()
            if row and row["value"] == digest:
                return False
            new_ids = {v["id"] for v in visits}
            referenced = {r[0] for r in db.execute("SELECT supersedes FROM visits WHERE supersedes IS NOT NULL")}
            stale = [
                r["id"]
                for r in db.execute("SELECT id,data FROM visits")
                if json.loads(r["data"]).get("imported") and r["id"] not in new_ids and r["id"] not in referenced
            ]
            db.execute("DELETE FROM evidence_records WHERE id LIKE 'wdi-%'")
            db.execute("DELETE FROM source_observations")
            for vid in stale:
                db.execute("DELETE FROM visits WHERE id=?", (vid,))
            # An imported site that left the data file (e.g. Makhdet, DI not installed yet) goes too, unless the
            # team edited it or recorded visits for it in the portal.
            new_sites = {s["id"] for s in sites}
            portal_visit_sites = {r["site_id"] for r in db.execute("SELECT site_id,data FROM visits")
                                  if not json.loads(r["data"]).get("imported")}
            for r in db.execute("SELECT id,data FROM sites").fetchall():
                if (json.loads(r["data"]).get("imported") and r["id"] not in new_sites
                        and r["id"] not in portal_visit_sites):
                    for table in ("attachments", "evidence_records", "source_observations",
                                  "weather_jobs", "site_versions", "visits", "sites"):
                        db.execute(f"DELETE FROM {table} WHERE {'id' if table == 'sites' else 'site_id'}=?",
                                   (r["id"],))
            for site in sites:
                old = db.execute("SELECT data FROM sites WHERE id=?", (site["id"],)).fetchone()
                if old and not json.loads(old["data"]).get("imported"):
                    continue
                db.execute(
                    "INSERT INTO sites VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                    (site["id"], encode(site)),
                )
            for v in visits:
                db.execute(
                    "INSERT INTO visits VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                    "visit_date=excluded.visit_date,data=excluded.data,saved_at=excluded.saved_at",
                    (v["id"], v["site_id"], v["status"], v["visit_date"], encode(v), None, v["created_at"], v["saved_at"]),
                )
            for e in evidence:
                db.execute(
                    "INSERT OR REPLACE INTO evidence_records VALUES(?,?,?,?)",
                    (e["id"], e["site_id"], e.get("visit_id"), encode(e)),
                )
            for o in observations:
                db.execute("INSERT INTO source_observations VALUES(?,?,?)", (o["id"], o["site_id"], encode(o)))
            db.execute(
                "INSERT INTO meta VALUES('watsan_import',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (digest,),
            )
        return True
