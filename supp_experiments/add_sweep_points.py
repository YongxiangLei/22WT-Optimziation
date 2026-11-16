"""
sweep_w2_0.250 stopped at 122.6 s with a BeamDyn convergence error (2026-11-13 23:54). An identical run
would stop at the same instant, so two neighbouring values replace it: omega_pc(18 m/s) = 0.24 and 0.26.
The stop of 0.250 is recorded in its metrics.json (the queue did not record it because STOP existed).

  python add_sweep_points.py
"""
import datetime as dt
import json
import os

import prepare as pp
from supp_common import ROOT, RUNS, Plant, read_text

NEW = [0.24, 0.26]
jobs = json.load(open(os.path.join(ROOT, "jobs.json")))
tags = {j["tag"] for j in jobs}
ref = json.load(open(os.path.join(RUNS, "sweep_w2_0.100", "parameters.json")))["omega_pc"]
plant = Plant()
pos = max(i for i, j in enumerate(jobs) if j["group"] == "E1_sweep") + 1
for w2 in NEW:
    tag = f"sweep_w2_{w2:.3f}"
    if tag in tags:
        print(tag, "exists already")
        continue
    d = pp.base_run(tag)
    om = pp.controller(d, plant, [ref[0], w2, ref[2]])
    job = {"tag": tag, "group": "E1_sweep", "omega_pc": om, "tmax": 300.0, "wind": "tuning"}
    with open(os.path.join(d, "parameters.json"), "w") as f:
        json.dump(job, f, indent=1)
    jobs.insert(pos, job)
    pos += 1
    print("added", tag, om)
with open(os.path.join(ROOT, "jobs.json"), "w") as f:
    json.dump(jobs, f, indent=1)

tag = "sweep_w2_0.250"
d = os.path.join(RUNS, tag)
mfile = os.path.join(d, "metrics.json")
if not os.path.exists(mfile):
    txt = read_text(os.path.join(d, "openfast_stdout.txt"))
    res = dict(next(j for j in jobs if j["tag"] == tag))
    res.update({"returncode": 1, "finished": dt.datetime.fromtimestamp(os.path.getmtime(os.path.join(d, "openfast_stdout.txt"))).isoformat(),
                "numerics": {"InterpOrder": 1}, "status": "FAILED",
                "error": [l.strip() for l in txt.splitlines() if "converge" in l or "error at simulation time" in l or "FATAL" in l][-4:]})
    with open(mfile, "w") as f:
        json.dump(res, f, indent=1)
    print("recorded the solver stop of", tag, res["error"][-2:])
print(len(jobs), "jobs in jobs.json")
