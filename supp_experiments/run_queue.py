"""
Run the prepared supplementary simulations with a fixed number of parallel workers.

  python -u run_queue.py [--workers N]

 * Jobs come from jobs.json (written by prepare.py); longest simulations start first.
 * A run with metrics.json (status OK) is skipped, so the queue can be stopped and restarted.
 * Create a file named STOP in this folder to let running simulations finish without starting new ones
   (stop.ps1 does this and can also terminate the running simulations).
 * Progress is appended to supp.log; DONE is written when every job has been processed.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from supp_common import ROOT, RUNS, OPENFAST, FST, OUTB, metrics, read_text

STOP = os.path.join(ROOT, "STOP")


def log(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(os.path.join(ROOT, "supp.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_job(job):
    tag = job["tag"]
    d = os.path.join(RUNS, tag)
    mfile = os.path.join(d, "metrics.json")
    if os.path.exists(mfile):
        try:
            old = json.load(open(mfile))
            # A run that OpenFAST stopped with a solver error would stop at the same instant again, so it is
            # not repeated either (delete its metrics.json to force a new attempt).
            if old.get("status") in ("OK", "FAILED"):
                return old
        except (json.JSONDecodeError, OSError):
            pass
    if os.path.exists(STOP):
        return {"tag": tag, "status": "SKIPPED"}
    log(f"{tag}: started (TMax {job['tmax']:.0f} s)")
    t0 = time.time()
    with open(os.path.join(d, "openfast_stdout.txt"), "w") as fo:
        rc = subprocess.run([OPENFAST, FST], cwd=d, stdout=fo, stderr=subprocess.STDOUT).returncode
    wall = time.time() - t0
    txt = read_text(os.path.join(d, "openfast_stdout.txt"))
    res = dict(job)
    res.update({"returncode": rc, "wall_s": wall, "finished": dt.datetime.now().isoformat(),
                "numerics": {"InterpOrder": 1}})
    outb = os.path.join(d, OUTB)
    if "terminated normally" in txt and os.path.exists(outb):
        res.update(metrics(outb))
        res["status"] = "OK"
        log(f"{tag}: OK  J={res['J_power_mse_kW2']:.1f} kW^2  speed RMSE={res['genspd_rmse_rpm']:.3f} rpm  "
            f"wall={wall / 3600:.2f} h")
    else:
        res["status"] = "FAILED"
        res["error"] = [l.strip() for l in txt.splitlines()
                        if "converge" in l or "error at simulation time" in l or "FATAL" in l][-4:]
        log(f"{tag}: FAILED after {wall / 3600:.2f} h: {res['error']}")
    if not (res["status"] == "FAILED" and os.path.exists(STOP)):     # a killed run is not recorded as a failure
        with open(mfile, "w") as f:
            json.dump(res, f, indent=1)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    jobs = json.load(open(os.path.join(ROOT, "jobs.json")))
    jobs.sort(key=lambda j: -j["tmax"])
    with open(os.path.join(ROOT, "queue.pid"), "w") as f:
        f.write(str(os.getpid()))
    for marker in ("DONE",):
        if os.path.exists(os.path.join(ROOT, marker)):
            os.remove(os.path.join(ROOT, marker))
    log(f"queue started: {len(jobs)} jobs, {a.workers} workers, pid {os.getpid()}")
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        res = list(ex.map(run_job, jobs))
    n = {s: sum(1 for r in res if r.get("status") == s) for s in ("OK", "FAILED", "SKIPPED")}
    log(f"queue finished: {n}")
    if n["SKIPPED"] == 0:
        p = subprocess.run([sys.executable, os.path.join(ROOT, "postprocess_supp.py")], cwd=ROOT,
                           capture_output=True, text=True)
        with open(os.path.join(ROOT, "postprocess_console.txt"), "w", encoding="utf-8") as f:
            f.write(p.stdout + "\n" + p.stderr)
        log(f"postprocess_supp.py: exit={p.returncode}")
        with open(os.path.join(ROOT, "DONE"), "w") as f:
            f.write(dt.datetime.now().isoformat())


if __name__ == "__main__":
    main()
