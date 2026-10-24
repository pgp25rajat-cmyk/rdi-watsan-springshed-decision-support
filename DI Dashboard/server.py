"""DI Dashboard: site setup, portal field visits and approved automatic rainfall."""

import argparse, base64, csv, hashlib, io, json, logging, mimetypes, os, sqlite3, tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
from uuid import uuid4
from backend.store import Store, encode, now
from backend.rules import Invalid, validate_site, validate_visit, assess
from backend.weather import RainfallWorker
from backend import watsan_import

HERE = Path(__file__).resolve().parent
log = logging.getLogger("di.dashboard")


def handler(store, worker=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.info(fmt, *args)

        def send(self, data, status=200, mime="application/json", name=None):
            raw = encode(data).encode() if mime == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if name:
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            if path == "/api/v2/health":
                return self.send({"application": "di-dashboard", "version": "2.0", "status": "ok"})
            if path == "/api/v2/state":
                state = store.state()
                state["assessment"] = assess(state)
                return self.send(state)
            if path == "/api/v2/export.json":
                return self.send(
                    encode(store.state()).encode(),
                    mime="application/json; charset=utf-8",
                    name="di-dashboard.json",
                )
            if path == "/api/v2/export.csv":
                out = io.StringIO()
                w = csv.writer(out)
                w.writerow(
                    [
                        "site_id",
                        "visit_id",
                        "visit_date",
                        "visitor",
                        "status",
                        "season",
                        "spring_flow_lpm",
                        "pump_status",
                        "di_status",
                        "notes",
                        "details_json",
                    ]
                )
                for v in store.state()["visits"]:
                    vals = [
                        v["site_id"],
                        v["id"],
                        v.get("visit_date"),
                        v.get("visitor"),
                        v["status"],
                        v.get("season"),
                        (v.get("spring") or {}).get("flow_lpm"),
                        (v.get("pump") or {}).get("status"),
                        (v.get("di") or {}).get("status"),
                        v.get("notes"),
                        encode(v),
                    ]
                    w.writerow(
                        [
                            (
                                "'" + x
                                if isinstance(x, str) and x.startswith(("=", "+", "-", "@", "\r", "\t"))
                                else x
                            )
                            for x in vals
                        ]
                    )
                return self.send(
                    ("\ufeff" + out.getvalue()).encode(), mime="text/csv; charset=utf-8", name="di-visits.csv"
                )
            if path == "/api/v2/backup":
                folder = HERE / "runtime/backups"
                folder.mkdir(exist_ok=True, parents=True)
                fd, tmp = tempfile.mkstemp(dir=folder, suffix=".sqlite")
                os.close(fd)
                try:
                    store.backup(tmp)
                    raw = Path(tmp).read_bytes()
                finally:
                    Path(tmp).unlink(missing_ok=True)
                return self.send(raw, mime="application/octet-stream", name="di-dashboard.sqlite")
            if path.startswith("/api/v2/attachments/"):
                a = next((a for a in store.state()["attachments"] if a["id"] == path.split("/")[-1]), None)
                if not a:
                    return self.send({"error": "File not found."}, 404)
                file = (HERE / a["path"]).resolve()
                if (
                    not any(
                        file.is_relative_to(root.resolve())
                        for root in (HERE / "runtime/attachments", HERE / "data/00_raw")
                    )
                    or not file.is_file()
                ):
                    return self.send({"error": "File not found."}, 404)
                return self.send(
                    file.read_bytes(), mime=mimetypes.guess_type(file.name)[0] or "application/octet-stream"
                )
            if path == "/" or path == "/dashboard":
                self.send_response(302)
                self.send_header("Location", "/dashboard/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            root = (HERE / "dist").resolve()
            # the page is built for /dashboard/ (vite base), so it can also be served inside the spring tool
            file = (root / path.removeprefix("/dashboard").lstrip("/")).resolve()
            if not file.is_relative_to(root):
                return self.send({"error": "Page not found."}, 404)
            if not file.is_file():
                file = root / "index.html"
            if not file.exists():
                return self.send({"error": "Build the dashboard first."}, 503)
            return self.send(
                file.read_bytes(), mime=mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            )

        def do_POST(self):
            origin = self.headers.get("Origin")
            if origin and origin != f'http://{self.headers.get("Host")}':
                return self.send({"error": "Please save from the dashboard page."}, 403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                parsed = urlparse(self.path)
                if parsed.path == "/api/v2/attachments/binary":
                    if not 0 < length <= 25 * 1024 * 1024:
                        self.close_connection = True
                        return self.send(
                            {"error": "Choose a file up to 25 MB. Your visit draft has been kept."}, 413
                        )
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise Invalid("The file upload was interrupted. Retry the file; your draft is saved.")
                    b = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                    return self.save_file(b, raw)
                if not 0 < length <= 16 * 1024 * 1024:
                    raise Invalid("Choose a smaller file (up to 10 MB).")
                b = json.loads(self.rfile.read(length))
                path = urlparse(self.path).path
                if not isinstance(b, dict):
                    raise Invalid("The submitted details are incomplete.")
                if path == "/api/v2/sites" or path.startswith("/api/v2/sites/"):
                    sid = path.split("/")[-1] if path != "/api/v2/sites" else None
                    old = store.site(sid) if sid else None
                    if sid and not old:
                        return self.send({"error": "Site not found."}, 404)
                    site = validate_site(b, old)
                    store.save_site(site)
                    if worker:
                        worker.notify()
                    return self.send(site, 200 if old else 201)
                if path == "/api/v2/visits":
                    submit = b.pop("submit", False)
                    if not isinstance(submit, bool):
                        raise Invalid("Check the save action.")
                    key = self.headers.get("Idempotency-Key")
                    fingerprint = hashlib.sha256(encode({"body": b, "submit": submit}).encode()).hexdigest()
                    if submit and not key:
                        raise Invalid("Please retry the save.")
                    if key:
                        with store.connect() as db:
                            existing = db.execute(
                                "SELECT request_hash,response FROM requests WHERE key=?", (key,)
                            ).fetchone()
                        if existing:
                            if existing["request_hash"] != fingerprint:
                                raise Invalid("This save key was already used for a different visit.")
                            return self.send(json.loads(existing["response"]))
                    visit = validate_visit(b, store.state(), submit)
                    result = store.save_visit(visit, key, fingerprint)
                    if submit:
                        for asset in ("spring", "pump", "di"):
                            store.evidence(
                                {
                                    "id": "portal-" + result["id"] + "-" + asset,
                                    "site_id": result["site_id"],
                                    "visit_id": result["id"],
                                    "asset": "handpump" if asset == "pump" else asset,
                                    "field": asset + " field entry",
                                    "value": result[asset],
                                    "basis": "portal_entry",
                                    "review_status": "entered_by_team",
                                    "source_excerpt": "Entered through the field visit form by "
                                    + result["visitor"]
                                    + ". Raw readings and conditions are kept in the visit.",
                                    "saved_at": now(),
                                }
                            )
                    if worker and submit:
                        worker.notify()
                    return self.send(result, 201)
                if path == "/api/v2/attachments":
                    raw = base64.b64decode(b.get("base64", ""), validate=True)
                    return self.save_file(b, raw)
                return self.send({"error": "Page not found."}, 404)
            except (Invalid, ValueError, KeyError, TypeError) as exc:
                return self.send({"error": str(exc)}, 422)
            except sqlite3.IntegrityError:
                return self.send(
                    {"error": "This visit already has a correction. Refresh and open the latest version."},
                    409,
                )
            except Exception:
                log.exception("Could not save")
                return self.send(
                    {"error": "Could not save. Your entries are still on this page. Please retry."}, 500
                )

        def save_file(self, b, raw):
            state = store.state()
            sid = b.get("site_id")
            vid = b.get("visit_id") or None
            site = next((s for s in state["sites"] if s["id"] == sid), None)
            if not site:
                raise Invalid("Choose a site for this file.")
            if vid and not any(v["id"] == vid and v["site_id"] == sid for v in state["visits"]):
                raise Invalid("Save the visit draft before attaching a file.")
            name = Path(str(b.get("name", ""))).name
            ext = Path(name).suffix.lower()
            kind = b.get("kind", "visit_support")
            asset = b.get("asset", "village")
            if ext not in (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".docx", ".txt"):
                raise Invalid("Use a photo, PDF, document or text note. Rainfall is fetched automatically.")
            if kind == "site_photo" and ext not in (".jpg", ".jpeg", ".png", ".webp"):
                raise Invalid("Use a JPG, PNG or WebP image for the site photo.")
            if not raw or len(raw) > 25 * 1024 * 1024:
                raise Invalid("Choose a supporting file up to 25 MB.")
            sha = hashlib.sha256(raw).hexdigest()
            existing = next(
                (
                    a
                    for a in state["attachments"]
                    if a.get("sha256") == sha
                    and a["site_id"] == sid
                    and a.get("visit_id") == vid
                    and a.get("kind", "visit_support") == kind
                ),
                None,
            )
            if existing:
                return self.send(existing)
            aid = "file-" + uuid4().hex[:14]
            folder = HERE / "runtime/attachments"
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / (aid + ext)
            dest.write_bytes(raw)
            a = {
                "id": aid,
                "site_id": sid,
                "visit_id": vid,
                "name": name,
                "path": str(dest.relative_to(HERE)),
                "sha256": sha,
                "size_bytes": len(raw),
                "saved_at": now(),
                "kind": kind,
                "asset": asset,
                "purpose": "Supporting file only. Not read or used in calculations.",
            }
            store.attachment(a)
            store.evidence(
                {
                    "id": "evidence-" + aid,
                    "site_id": sid,
                    "visit_id": vid,
                    "attachment_id": aid,
                    "asset": asset,
                    "field": "supporting_file",
                    "value": name,
                    "basis": "portal_attachment",
                    "review_status": "supporting_only",
                    "source_excerpt": "File added by the team. No information extracted from its contents.",
                    "saved_at": now(),
                }
            )
            if kind == "site_photo":
                store.save_site(
                    {
                        **site,
                        "photo_id": aid,
                        "photo_url": None,
                        "photo_caption": b.get("caption") or "Site photograph supplied by the team.",
                        "updated_at": now(),
                    }
                )
            return self.send(a, 201)

    return Handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8769)
    p.add_argument("--db", default=str(HERE / "runtime/di-dashboard.sqlite"))
    p.add_argument("--no-weather", action="store_true")
    p.add_argument("--data", default=str(watsan_import.DEFAULT_DIR), help="WATSAN DI sites data folder")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    store = Store(args.db)
    if watsan_import.load(store, args.data):
        log.info("Loaded the WATSAN DI sites data file from %s", args.data)
    worker = None if args.no_weather else RainfallWorker(store)
    if worker:
        worker.start()
    service = ThreadingHTTPServer(("127.0.0.1", args.port), handler(store, worker))
    log.info("DI Dashboard: http://127.0.0.1:%s", args.port)
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if worker:
            worker.stop()
        service.server_close()


if __name__ == "__main__":
    main()
