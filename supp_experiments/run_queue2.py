"""
Second queue that takes over the simulations the first queue (run_queue.py) has not started yet and
runs them on the idle cores, without interrupting the simulations the first queue is still running.

  python -u run_queue2.py --cap 16 --wait-pid <pid of the first queue>

 * The first queue must have been told to stop starting runs (file STOP) before this one is started.
 * Runs that the first queue is still executing (taken from supp.log) are left alone, and so are runs
   that already have a metrics.json (finished, or stopped by a solver error: those are not repeated).
 * A new run starts whenever fewer than --cap OpenFAST processes exist on the machine, so the cores
   freed by the first queue are picked up automatically.
 * Stop file of this queue: STOP2 (stop.ps1 writes both).
 * At the end it waits for the first queue to exit, runs postprocess_supp.py and writes DONE.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import threading
import time

import run_queue as rq
from supp_common import ROOT, RUNS

STOP2 = os.path.join(ROOT, "STOP2")
rq.STOP = STOP2                       # run_job of this process obeys STOP2, not STOP
log = rq.log


def tasklist(flt):
    return subprocess.run(["tasklist", "/FI", flt, "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout


def n_openfast():
    return sum(1 for l in tasklist("IMAGENAME eq openfast.exe").splitlines() if l.lower().startswith('"openfast.exe"'))


def pid_alive(pid):
    return f'"{pid}"' in tasklist(f"PID eq {pid}")


def running_in_first_queue():
    lines = open(os.path.join(ROOT, "supp.log"), encoding="utf-8", errors="ignore").read().splitlines()
    start = max(i for i, l in enumerate(lines) if "queue started:" in l)
    state = {}
    for l in lines[start + 1:]:
        m = re.match(r"^\S+ \S+  (\S+): (started|OK|FAILED)", l)
        if m:
            state[m.group(1)] = m.group(2)
    return sorted(t for t, s in state.items() if s == "started")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=16, help="maximum number of OpenFAST processes on the machine")
    ap.add_argument("--wait-pid", required=True, help="pid(s) of the queues that are still running, e.g. 6096,31596")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    wait_pids = [int(x) for x in re.split(r"[,; ]+", a.wait_pid) if x]

    def others_alive():
        return [p for p in wait_pids if pid_alive(p)]
    jobs = json.load(open(os.path.join(ROOT, "jobs.json")))
    jobs.sort(key=lambda j: -j["tmax"])
    busy = running_in_first_queue()
    pending = [j for j in jobs if j["tag"] not in busy and not os.path.exists(os.path.join(RUNS, j["tag"], "metrics.json"))]
    print("running in the first queue:", busy)
    print("taken over:", [j["tag"] for j in pending])
    print("OpenFAST processes now:", n_openfast(), " other queues alive:", others_alive(), "of", wait_pids,
          " STOP present:", os.path.exists(os.path.join(ROOT, "STOP")))
    if a.dry:
        return
    if not os.path.exists(os.path.join(ROOT, "STOP")) and others_alive():
        sys.exit("STOP is missing: the first queue would start the same runs. Nothing started.")
    if len(busy) != n_openfast():
        sys.exit("the runs marked as started in supp.log do not match the OpenFAST processes. Nothing started.")
    with open(os.path.join(ROOT, "queue.pid"), "w") as f:
        f.write(str(os.getpid()))
    log(f"takeover queue (pid {os.getpid()}) started: {len(pending)} jobs, at most {a.cap} OpenFAST processes in total")
    threads, stopped = [], False
    while pending:
        if os.path.exists(STOP2):
            log(f"queue 2: STOP2 found, {len(pending)} jobs not started")
            stopped = True
            break
        if n_openfast() < a.cap:
            t = threading.Thread(target=rq.run_job, args=(pending.pop(0),))
            t.start()
            threads.append(t)
            time.sleep(10)            # let the new process appear before counting again
        else:
            time.sleep(30)
    for t in threads:
        t.join()
    while others_alive():             # the earlier queues are still running their last simulations
        time.sleep(30)
    n = {"OK": 0, "FAILED": 0, "MISSING": 0}
    for j in jobs:
        p = os.path.join(RUNS, j["tag"], "metrics.json")
        s = json.load(open(p)).get("status", "MISSING") if os.path.exists(p) else "MISSING"
        n[s if s in n else "MISSING"] += 1
    log(f"queue finished (both queues): {n}")
    if not stopped and not os.path.exists(STOP2):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "postprocess_supp.py")], cwd=ROOT,
                           capture_output=True, text=True)
        with open(os.path.join(ROOT, "postprocess_console.txt"), "w", encoding="utf-8") as f:
            f.write(p.stdout + "\n" + p.stderr)
        log(f"postprocess_supp.py: exit={p.returncode}")
        with open(os.path.join(ROOT, "DONE"), "w") as f:
            f.write(dt.datetime.now().isoformat())


if __name__ == "__main__":
    main()
