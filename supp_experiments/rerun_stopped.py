"""
Repeat the three simulations that BeamDyn stopped ("solution does not converge"). An identical run stops
at the same step, so each case is repeated with two changes of the coupling numerics, in parallel:

  __r2 : InterpOrder = 2 (quadratic input/output interpolation, the setting of the original optimization)
  __c1 : InterpOrder = 1 and NumCrctn = 1 (one correction iteration; about twice the cost) - fallback

When the __r2 run of a case finishes normally, its __c1 fallback is terminated. The stopped runs keep
their directories; the repeats live in runs/<tag>__r2 and runs/<tag>__c1 until promote_rerun.py is used.

  python -u rerun_stopped.py            (stop: create a file named STOP_RERUN)
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import time

from run_queue import log
from supp_common import ROOT, RUNS, OPENFAST, FST, OUTB, metrics, read_text, set_param

CASES = ["val_U22_s1_default", "val_U14_s3_opt", "sweep_w2_0.250"]
VARIANTS = {"r2": {"InterpOrder": "2", "NumCrctn": "0"}, "c1": {"InterpOrder": "1", "NumCrctn": "1"}}
SKIP = ("metrics.json", "openfast_stdout.txt")
STOP = os.path.join(ROOT, "STOP_RERUN")


def prepare(tag, var):
    src, dst = os.path.join(RUNS, tag), os.path.join(RUNS, f"{tag}__{var}")
    os.makedirs(dst, exist_ok=True)
    for fn in os.listdir(src):
        if fn in SKIP or fn.endswith((".outb", ".out", ".sum", ".ech", ".chkp")):
            continue
        shutil.copy2(os.path.join(src, fn), os.path.join(dst, fn))
    for k, v in VARIANTS[var].items():
        set_param(os.path.join(dst, FST), k, v)
    return dst


def finish(run):
    d, tag, var = run["dir"], run["tag"], run["var"]
    run["fo"].close()
    txt = read_text(os.path.join(d, "openfast_stdout.txt"))
    res = dict(run["job"])
    res.update({"returncode": run["proc"].returncode, "wall_s": time.time() - run["t0"], "finished": dt.datetime.now().isoformat(),
                "numerics": {k: int(v) for k, v in VARIANTS[var].items()}, "rerun_of": tag, "variant": var})
    outb = os.path.join(d, OUTB)
    if run.get("killed"):
        res["status"] = "TERMINATED"
        log(f"{tag}__{var}: terminated ({run['killed']})")
    elif "terminated normally" in txt and os.path.exists(outb):
        res.update(metrics(outb))
        res["status"] = "OK"
        log(f"{tag}__{var}: OK  J={res['J_power_mse_kW2']:.1f} kW^2  speed RMSE={res['genspd_rmse_rpm']:.3f} rpm  wall={res['wall_s'] / 3600:.2f} h")
    else:
        res["status"] = "FAILED"
        res["error"] = [l.strip() for l in txt.splitlines() if "converge" in l or "error at simulation time" in l or "FATAL" in l][-4:]
        log(f"{tag}__{var}: FAILED after {res['wall_s'] / 3600:.2f} h: {res['error']}")
    with open(os.path.join(d, "metrics.json"), "w") as f:
        json.dump(res, f, indent=1)
    run["status"] = res["status"]


def main():
    jobs = {j["tag"]: j for j in json.load(open(os.path.join(ROOT, "jobs.json")))}
    runs = []
    for tag in CASES:
        for var in VARIANTS:
            d = prepare(tag, var)
            fo = open(os.path.join(d, "openfast_stdout.txt"), "w")
            p = subprocess.Popen([OPENFAST, FST], cwd=d, stdout=fo, stderr=subprocess.STDOUT)
            runs.append({"tag": tag, "var": var, "dir": d, "fo": fo, "proc": p, "t0": time.time(), "job": jobs[tag], "status": None})
            log(f"{tag}__{var}: started ({VARIANTS[var]})")
            time.sleep(2)
    with open(os.path.join(ROOT, "rerun.pid"), "w") as f:
        f.write(str(os.getpid()))
    while any(r["status"] is None for r in runs):
        time.sleep(30)
        if os.path.exists(STOP):
            for r in runs:
                if r["status"] is None and r["proc"].poll() is None:
                    r["killed"] = "STOP_RERUN"
                    r["proc"].terminate()
        for r in runs:
            if r["status"] is None and r["proc"].poll() is not None:
                finish(r)
                if r["var"] == "r2" and r["status"] == "OK":          # the fallback is no longer needed
                    for o in runs:
                        if o["tag"] == r["tag"] and o["var"] == "c1" and o["status"] is None and o["proc"].poll() is None:
                            o["killed"] = "quadratic-interpolation repeat finished"
                            o["proc"].terminate()
    summary = {f"{r['tag']}__{r['var']}": r["status"] for r in runs}
    log(f"rerun finished: {summary}")
    with open(os.path.join(ROOT, "RERUN_DONE"), "w") as f:
        json.dump(summary, f, indent=1)


if __name__ == "__main__":
    main()
