#!/usr/bin/env python3
"""Pipeline-Cache-Report: Wie viel bringt der GitLab-Cache?

Fragt die letzten N Pipelines per GitLab-API ab, erkennt je Job anhand des Job-Logs, ob der
Cache getroffen (HIT) oder verfehlt (MISS) wurde, und vergleicht die Laufzeiten.
Ausgabe: CSV (+ Balkendiagramm als PNG, falls matplotlib installiert ist).

Beispiel:
  GITLAB_TOKEN=glpat-… python scripts/pipeline_cache_report.py --project 12345 --pipelines 20 --out reports
In einer Pipeline reicht CI_JOB_TOKEN bzw. ein Project-Access-Token (read_api).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HIT_MARKERS = ("Successfully extracted cache",)
MISS_MARKERS = ("No URL provided, cache will not be downloaded", "cache not found", "Failed to extract cache")
CACHE_JOBS = {"lint:ruff", "test:pytest"}  # Jobs mit pip-Cache


def detect_cache_status(trace: str) -> str:
    """Gibt 'HIT', 'MISS' oder 'NONE' (kein Cache-Schritt im Log) zurück."""
    if any(m in trace for m in HIT_MARKERS):
        return "HIT"
    if any(m in trace for m in MISS_MARKERS) or "Checking cache for" in trace:
        return "MISS"
    return "NONE"


def summarize(rows: list[dict]) -> dict[str, dict[str, float]]:
    """Durchschnittliche Laufzeit je Job und Cache-Status."""
    out: dict[str, dict[str, float]] = {}
    for status in ("HIT", "MISS"):
        durations: dict[str, list[float]] = {}
        for r in rows:
            if r["cache"] == status and r["duration"] is not None:
                durations.setdefault(r["job"], []).append(float(r["duration"]))
        for job, vals in durations.items():
            out.setdefault(job, {})[status] = round(statistics.mean(vals), 1)
    return out


class GitLab:
    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/") + "/api/v4"
        self.token = token

    def _req(self, path: str, raw: bool = False):
        req = urllib.request.Request(self.base + path, headers={"PRIVATE-TOKEN": self.token})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            body = resp.read()
        return body.decode("utf-8", "replace") if raw else json.loads(body)

    def pipelines(self, project: str, n: int):
        q = urllib.parse.urlencode({"per_page": n, "status": "success", "order_by": "id", "sort": "desc"})
        return self._req(f"/projects/{project}/pipelines?{q}")

    def jobs(self, project: str, pipeline_id: int):
        return self._req(f"/projects/{project}/pipelines/{pipeline_id}/jobs?per_page=100")

    def trace(self, project: str, job_id: int) -> str:
        return self._req(f"/projects/{project}/jobs/{job_id}/trace", raw=True)


def collect(gl: GitLab, project: str, n: int) -> list[dict]:
    rows = []
    for pipe in gl.pipelines(project, n):
        for job in gl.jobs(project, pipe["id"]):
            if job["name"] not in CACHE_JOBS or job["status"] != "success":
                continue
            rows.append(
                {
                    "pipeline": pipe["id"],
                    "job": job["name"],
                    "job_id": job["id"],
                    "duration": round(job["duration"], 1) if job.get("duration") else None,
                    "cache": detect_cache_status(gl.trace(project, job["id"])),
                    "finished_at": job.get("finished_at"),
                }
            )
    return rows


def write_outputs(rows: list[dict], summary: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "cache_report.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["pipeline", "job", "job_id", "duration", "cache", "finished_at"])
        w.writeheader()
        w.writerows(rows)
    try:
        import matplotlib  # noqa: PLC0415

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: PLC0415
    except ImportError:
        print("(matplotlib fehlt – nur CSV geschrieben; `pip install matplotlib` für das Diagramm)")
        return
    jobs = sorted(summary)
    x = range(len(jobs))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - 0.2 for i in x], [summary[j].get("MISS", 0) for j in jobs], 0.4, label="Cache MISS", color="#d64545")
    ax.bar([i + 0.2 for i in x], [summary[j].get("HIT", 0) for j in jobs], 0.4, label="Cache HIT", color="#1e9e5a")
    ax.set_xticks(list(x), jobs)
    ax.set_ylabel("Ø Laufzeit (s)")
    ax.set_title("GitLab-Cache: Laufzeit mit/ohne Treffer")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "cache_report.png", dpi=120)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.getenv("CI_PROJECT_ID"), help="Projekt-ID (Standard: $CI_PROJECT_ID)")
    ap.add_argument("--pipelines", type=int, default=20)
    ap.add_argument("--url", default=os.getenv("CI_SERVER_URL", "https://gitlab.com"))
    ap.add_argument("--out", type=Path, default=Path("reports"))
    args = ap.parse_args()
    token = os.getenv("GITLAB_TOKEN") or os.getenv("CI_JOB_TOKEN")
    if not args.project or not token:
        print("FEHLER: --project/CI_PROJECT_ID und GITLAB_TOKEN müssen gesetzt sein", file=sys.stderr)
        return 2
    rows = collect(GitLab(args.url, token), args.project, args.pipelines)
    summary = summarize(rows)
    write_outputs(rows, summary, args.out)
    print(f"{len(rows)} Job-Läufe ausgewertet → {args.out}/cache_report.csv")
    for job, d in sorted(summary.items()):
        miss, hit = d.get("MISS"), d.get("HIT")
        gain = f"  → Ersparnis {100 * (miss - hit) / miss:.0f} %" if miss and hit else ""
        print(f"  {job:14s} MISS Ø {miss}s | HIT Ø {hit}s{gain}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
