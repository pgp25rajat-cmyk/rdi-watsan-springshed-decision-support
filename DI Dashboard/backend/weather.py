"""Automatic rainfall context. User explicitly approved Open-Meteo coordinate requests.

Only latitude, longitude, model, dates and timezone leave this computer.
No site names, people, visit notes or files are sent.
"""

import hashlib, json, logging, threading, os, ssl, subprocess
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError
from .rules import coords_key, today, number, rainfall_location
from .store import now

log = logging.getLogger("di.rainfall")
SOURCE_URL = "https://open-meteo.com/en/docs/historical-weather-api"
ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"


def fetch_raw(request, opener=urlopen):
    try:
        with opener(request, timeout=18) as response:
            return response.read(8 * 1024 * 1024).decode("utf-8")
    except URLError as exc:
        # Bundled Python may have a different trust store from Windows. Keep HTTPS
        # validation enabled and use Windows' validated HTTPS client in that case.
        if (
            os.name != "nt"
            or opener is not urlopen
            or not isinstance(exc.reason, ssl.SSLCertVerificationError)
        ):
            raise
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(Path(__file__).with_name("fetch_weather.ps1")),
                "-Url",
                request.full_url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise ValueError("Windows could not download rainfall with certificate validation.")
        if len(result.stdout) > 8 * 1024 * 1024:
            raise ValueError("Rainfall response is too large.")
        return result.stdout


def decode_weather(raw, site, start, end):
    obj = json.loads(raw)
    if obj.get("error"):
        raise ValueError(obj.get("reason", "The rainfall provider could not complete this request."))
    daily = obj.get("daily", {})
    dates = daily.get("time", [])
    values = daily.get("rain_sum", [])
    if not dates or len(dates) != len(values) or obj.get("daily_units", {}).get("rain_sum") != "mm":
        raise ValueError("Rainfall data is incomplete or uses an unexpected unit.")
    previous = None
    clean = []
    for d, value in zip(dates, values):
        parsed = date.fromisoformat(d)
        if not start <= parsed <= end or (previous and parsed <= previous):
            raise ValueError("Rainfall dates are invalid or out of order.")
        previous = parsed
        clean.append(None if value is None else number(value, "Rainfall", 0, 10000))
    if not any(x is not None for x in clean):
        raise ValueError("No rainfall values are available for this period yet.")
    return {
        "coords_key": coords_key(site),
        "provider": "Open-Meteo / ERA5",
        "source_url": SOURCE_URL,
        "request_latitude": site["latitude"],
        "request_longitude": site["longitude"],
        "grid_latitude": obj.get("latitude"),
        "grid_longitude": obj.get("longitude"),
        "model": "ERA5",
        "resolution": "about 25 km",
        "timezone": obj.get("timezone"),
        "dates": dates,
        "rain_mm": clean,
        "fetched_at": now(),
        "unit": "mm",
        "meaning": "Rainfall estimated for the surrounding area. Mountain rainfall can differ at the site.",
    }


class RainfallWorker:
    def __init__(self, store, opener=urlopen):
        self.store = store
        self.opener = opener
        self.wake = threading.Event()
        self.stopping = threading.Event()

    def start(self):
        self.thread = threading.Thread(target=self.loop, daemon=True, name="rainfall-refresh")
        self.thread.start()

    def notify(self):
        self.wake.set()

    def stop(self):
        self.stopping.set()
        self.wake.set()

    def loop(self):
        while not self.stopping.is_set():
            try:
                self.refresh_due()
            except Exception:
                log.exception("Rainfall update failed")
            self.wake.wait(60)
            self.wake.clear()

    def refresh_due(self, force_id=None):
        state = self.store.state()
        jobs = {j["site_id"]: j for j in state["weather_jobs"]}
        for site in state["sites"]:
            site = rainfall_location(site)
            if self.stopping.is_set():
                return
            if force_id and force_id != site["id"]:
                continue
            key = coords_key(site)
            if not key:
                if jobs.get(site["id"], {}).get("status") != "needs_gps":
                    self.store.job(
                        site["id"],
                        {
                            "status": "needs_gps",
                            "message": "Add the site GPS to get rainfall automatically.",
                            "checked_at": now(),
                        },
                    )
                continue
            cache = state["weather"].get(key)
            job = jobs.get(site["id"], {})
            if (
                cache
                and (datetime.now(timezone.utc) - datetime.fromisoformat(cache["fetched_at"])).total_seconds()
                < 86400
                and not force_id
            ):
                if job.get("status") != "ready" or job.get("coords_key") != key:
                    self.store.job(
                        site["id"],
                        {
                            "status": "ready",
                            "coords_key": key,
                            "message": "Rainfall is up to date.",
                            "checked_at": now(),
                        },
                    )
                continue
            if (
                not force_id
                and job.get("status") == "failed"
                and job.get("coords_key") == key
                and (datetime.now(timezone.utc) - datetime.fromisoformat(job["checked_at"])).total_seconds()
                < 3600
            ):
                continue
            self.store.job(
                site["id"],
                {
                    "status": "loading",
                    "coords_key": key,
                    "message": "Getting rainfall for this location…",
                    "checked_at": now(),
                },
            )
            try:
                end = today() - timedelta(days=7)
                oldest = min(
                    [
                        date.fromisoformat(v["visit_date"])
                        for v in state["visits"]
                        if v["site_id"] == site["id"] and v["status"] == "submitted"
                    ]
                    or [today()]
                )
                start = max(
                    date(1940, 1, 1), min(today() - timedelta(days=730), oldest - timedelta(days=400))
                )
                query = urlencode(
                    {
                        "latitude": site["latitude"],
                        "longitude": site["longitude"],
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "daily": "rain_sum",
                        "models": "era5",
                        "timezone": "Asia/Kolkata",
                    }
                )
                raw = fetch_raw(
                    Request(ENDPOINT + "?" + query, headers={"User-Agent": "WATSAN-DI-Dashboard/2.0"}),
                    self.opener,
                )
                data = decode_weather(raw, site, start, end)
                self.store.weather(key, data, raw, hashlib.sha256(raw.encode()).hexdigest())
                state["weather"][key] = data
                self.store.job(
                    site["id"],
                    {
                        "status": "ready",
                        "coords_key": key,
                        "message": "Rainfall saved. It will update automatically.",
                        "checked_at": now(),
                    },
                )
            except Exception as exc:
                log.warning("Rainfall unavailable for %s: %s", site["id"], exc)
                self.store.job(
                    site["id"],
                    {
                        "status": "failed",
                        "coords_key": key,
                        "message": "Rainfall could not be updated. Saved data is still shown, if available. The app will retry.",
                        "checked_at": now(),
                        "technical_reason": str(exc)[:500],
                    },
                )
