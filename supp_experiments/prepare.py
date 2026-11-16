"""
Prepare the supplementary experiments (no simulation is started here except TurbSim with --wind).

  python prepare.py check     # verify the gain-schedule reconstruction against the finished BO run
  python prepare.py wind      # write the TurbSim inputs and generate the validation wind fields
  python prepare.py runs      # build all run directories and jobs.json
  python prepare.py smoke     # 3-s test of one validation case

Experiments
  E1 sweep : omega_pc(18 m/s) swept beyond the BO bound, omega_pc(12), omega_pc(24) as in eval_018;
             tuning wind field, 300 s, objective window 100-300 s.
  E2 val   : default vs BO-best controller on unseen IEC Kaimal NTM (class B) wind fields at
             14, 18 and 22 m/s, 3 seeds each, 700 s, evaluation window 100-700 s.
  E3 rand  : 15 further uniform random candidates (draws 6-20 of the stream that produced the five
             initial BO candidates), tuning wind field, 300 s.
All new runs use InterpOrder = 1 (the finished run showed < 0.001 % effect on J and one BeamDyn
divergence with InterpOrder = 2).
"""
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from supp_common import (ROOT, SRC_RUNS, RUNS, WIND, SHARED, OPENFAST, TURBSIM, FST, DISCON, INFLOW, TOP_FILES,
                         U_PC, OMEGA_DEFAULT, OMEGA_BEST, RATED_RPM, Plant, set_param, write_discon,
                         read_discon_row)

TEMPLATE = os.path.join(SRC_RUNS, "template")
SWEEP_W2 = [0.10, 0.15, 0.25, 0.30, 0.35, 0.40, 0.50]
VAL_SPEEDS = [14, 18, 22]
VAL_SEEDS = [1, 2, 3]
VAL_TMAX = 700.0
PBOUNDS = [(0.1, 0.2), (0.1, 0.2), (0.1, 0.5)]
SEED = 42


def check():
    """Rebuild every gain schedule of the finished run and compare with the stored one."""
    plant = Plant()
    worst = 0.0
    for tag in sorted(os.listdir(SRC_RUNS)):
        g = os.path.join(SRC_RUNS, tag, "gain_schedule.json")
        p = os.path.join(SRC_RUNS, tag, "parameters.json")
        if not (os.path.exists(g) and os.path.exists(p)):
            continue
        ref = json.load(open(g))
        om = json.load(open(p))["omega_pc"]
        s = plant.schedule(om)
        e = max(float(np.max(np.abs(np.array(s[k]) - np.array(ref[k])))) for k in ("omega_pc", "zeta_pc", "Kp", "Ki"))
        # the DISCON rows are what the controller actually reads
        dk = max(float(np.max(np.abs(np.round(s["Kp"], 6) - read_discon_row(os.path.join(SRC_RUNS, tag, DISCON), "PC_GS_KP")))),
                 float(np.max(np.abs(np.round(s["Ki"], 6) - read_discon_row(os.path.join(SRC_RUNS, tag, DISCON), "PC_GS_KI")))))
        worst = max(worst, e, dk)
        print(f"{tag:28s} max |diff| schedule {e:.2e}   DISCON rows {dk:.2e}")
    print(f"worst difference: {worst:.2e}")
    if worst > 2e-6:
        sys.exit("gain-schedule reconstruction does NOT match the finished run")
    print("reconstruction OK")


# ----------------------------------------------------------------------------- wind fields
def wind_name(u, s):
    return f"U{u:02d}_s{s}"


def turbsim_seed(u, s):
    return 100000 * u + 100 * s + 7


def wave_seed(u, s):
    return 500000000 + 1000 * u + s


def write_turbsim_inp(u, s):
    """IEC 61400-1 Ed.3 Kaimal NTM class B, grid centred on the hub (170 m), 720 s periodic."""
    src = os.path.join(SRC_RUNS, "IEA-22-280-RWT", "Wind", "TurbSim.inp")
    d = os.path.join(WIND, wind_name(u, s))
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, wind_name(u, s) + ".inp")
    shutil.copy2(src, dst)
    for key, val in (("RandSeed1", str(turbsim_seed(u, s))), ("WrBHHTP", "False"), ("WrBLFF", "False"),
                     ("WrADTWR", "True"), ("NumGrid_Z", "29"), ("NumGrid_Y", "29"), ("TimeStep", "0.05"),
                     ("AnalysisTime", "720"), ("UsableTime", '"ALL"'), ("HubHt", "170"), ("GridHeight", "320"),
                     ("GridWidth", "320"), ("TurbModel", '"IECKAI"'), ("IECstandard", '"1-ED3"'),
                     ("IECturbc", '"B"'), ("IEC_WindType", '"NTM"'), ("WindProfileType", '"PL"'),
                     ("RefHt", "170"), ("URef", f"{float(u):.1f}"), ("PLExp", "0.14")):
        set_param(dst, key, val)
    return dst


def run_turbsim(inp):
    d = os.path.dirname(inp)
    bts = inp.replace(".inp", ".bts")
    if os.path.exists(bts) and os.path.getsize(bts) > 1e6:
        return inp, 0
    with open(os.path.join(d, "turbsim_stdout.txt"), "w") as fo:
        rc = subprocess.run([TURBSIM, os.path.basename(inp)], cwd=d, stdout=fo, stderr=subprocess.STDOUT).returncode
    return inp, rc


def wind():
    inps = [write_turbsim_inp(u, s) for u in VAL_SPEEDS for s in VAL_SEEDS]
    with ThreadPoolExecutor(max_workers=len(inps)) as ex:
        for inp, rc in ex.map(run_turbsim, inps):
            bts = inp.replace(".inp", ".bts")
            ok = os.path.exists(bts) and os.path.getsize(bts) > 1e6
            print(f"{os.path.basename(inp):14s} rc={rc}  bts={'%.0f MB' % (os.path.getsize(bts) / 1e6) if ok else 'MISSING'}")


# ----------------------------------------------------------------------------- run directories
def setup_shared():
    """Shared turbine folder (blades, BeamDyn, airfoils, Cp table, tuning wind field) next to the runs."""
    if os.path.isdir(SHARED):
        return
    shutil.copytree(os.path.join(SRC_RUNS, "IEA-22-280-RWT"), SHARED)
    bts = os.path.join(SHARED, "Wind", "TurbSim.bts").replace("\\", "/")
    set_param(os.path.join(SHARED, INFLOW), "FileName_BTS", f'"{bts}"')


def base_run(tag):
    d = os.path.join(RUNS, tag)
    os.makedirs(d, exist_ok=True)
    for fn in TOP_FILES:
        shutil.copy2(os.path.join(TEMPLATE, fn), os.path.join(d, fn))
    set_param(os.path.join(d, FST), "InterpOrder", "1")
    return d


def controller(d, plant, omegas=None, copy_from=None):
    if copy_from is not None:                      # existing controller file of the finished run, unchanged
        for fn in (DISCON, "gain_schedule.json"):
            shutil.copy2(os.path.join(SRC_RUNS, copy_from, fn), os.path.join(d, fn))
        return json.load(open(os.path.join(SRC_RUNS, copy_from, "parameters.json")))["omega_pc"]
    sched = plant.schedule(omegas)
    write_discon(d, sched)
    with open(os.path.join(d, "gain_schedule.json"), "w") as f:
        json.dump(sched, f, indent=1)
    return [float(x) for x in omegas]


def runs(only=None, tmax_override=None):
    plant = Plant()
    setup_shared()
    jobs = []

    # E1: sweep of omega_pc at 18 m/s
    for w2 in SWEEP_W2:
        tag = f"sweep_w2_{w2:.3f}"
        d = base_run(tag)
        om = controller(d, plant, [OMEGA_BEST[0], w2, OMEGA_BEST[2]])
        jobs.append({"tag": tag, "group": "E1_sweep", "omega_pc": om, "tmax": 300.0, "wind": "tuning"})

    # E3: random candidates 6-20 of the seed-42 stream (1-5 are eval_001..005 of the finished run)
    rng = np.random.RandomState(SEED)
    lo = np.array([b[0] for b in PBOUNDS]); hi = np.array([b[1] for b in PBOUNDS])
    pts = [lo + (hi - lo) * rng.uniform(size=3) for _ in range(20)]
    for i in range(5):                             # the stream must reproduce the finished run
        ref = json.load(open(os.path.join(SRC_RUNS, f"eval_{i + 1:03d}", "parameters.json")))["omega_pc"]
        if np.max(np.abs(np.array(ref) - pts[i])) > 1e-12:
            sys.exit(f"random stream does not reproduce eval_{i + 1:03d}")
    for i in range(5, 20):
        tag = f"rand_{i + 1:03d}"
        d = base_run(tag)
        om = controller(d, plant, pts[i])
        jobs.append({"tag": tag, "group": "E3_random", "omega_pc": om, "tmax": 300.0, "wind": "tuning"})

    # E2: validation on unseen wind fields
    v_gs = np.array(json.load(open(os.path.join(SRC_RUNS, "baseline", "gain_schedule.json")))["v"])
    ang = np.degrees(read_discon_row(os.path.join(SRC_RUNS, "baseline", DISCON), "PC_GS_angles"))
    for u in VAL_SPEEDS:
        pitch0 = float(np.interp(u, v_gs, ang))    # steady-state pitch from the gain-schedule table
        for s in VAL_SEEDS:
            bts = os.path.join(WIND, wind_name(u, s), wind_name(u, s) + ".bts").replace("\\", "/")
            for ctrl, src in (("default", "baseline"), ("opt", "eval_018")):
                tag = f"val_{wind_name(u, s)}_{ctrl}"
                d = base_run(tag)
                om = controller(d, plant, copy_from=src)
                shutil.copy2(os.path.join(SHARED, INFLOW), os.path.join(d, INFLOW))
                set_param(os.path.join(d, INFLOW), "FileName_BTS", f'"{bts}"')
                set_param(os.path.join(d, FST), "InflowFile", f'"{INFLOW}"')
                set_param(os.path.join(d, FST), "TMax", f"{VAL_TMAX}")
                ed = os.path.join(d, "IEA-22-280-RWT_ElastoDyn.dat")
                set_param(ed, "RotSpeed", f"{RATED_RPM:.4f}")
                for b in (1, 2, 3):
                    set_param(ed, f"BlPitch({b})", f"{pitch0:.3f}")
                set_param(os.path.join(d, "IEA-22-280-RWT_HydroDyn.dat"), "WaveSeed(1)", str(wave_seed(u, s)))
                jobs.append({"tag": tag, "group": "E2_validation", "omega_pc": om, "tmax": VAL_TMAX,
                             "wind": wind_name(u, s), "U": u, "seed": s, "controller": ctrl,
                             "pitch0_deg": pitch0, "turbsim_seed": turbsim_seed(u, s), "wave_seed": wave_seed(u, s)})

    for j in jobs:
        with open(os.path.join(RUNS, j["tag"], "parameters.json"), "w") as f:
            json.dump(j, f, indent=1)
    with open(os.path.join(ROOT, "jobs.json"), "w") as f:
        json.dump(jobs, f, indent=1)
    print(f"{len(jobs)} runs prepared:", {g: sum(1 for j in jobs if j['group'] == g) for g in sorted(set(j['group'] for j in jobs))})
    print("simulated time: %.0f s" % sum(j["tmax"] for j in jobs))


def smoke():
    """3-s run of one case (default: a validation case) in a scratch directory."""
    src = os.path.join(RUNS, sys.argv[2] if len(sys.argv) > 2 else "val_U22_s1_opt")
    d = os.path.join(RUNS, "_smoke")
    if os.path.isdir(d):
        shutil.rmtree(d)
    shutil.copytree(src, d)
    set_param(os.path.join(d, FST), "TMax", "15.0")    # long enough to pass the start-up transient
    with open(os.path.join(d, "openfast_stdout.txt"), "w") as fo:
        rc = subprocess.run([OPENFAST, FST], cwd=d, stdout=fo, stderr=subprocess.STDOUT).returncode
    txt = open(os.path.join(d, "openfast_stdout.txt"), errors="ignore").read()
    print("rc =", rc, "| terminated normally:", "terminated normally" in txt)
    for line in txt.splitlines():
        if any(k in line for k in ("grid", "Grid", "error", "Error", "ROSCO-v", "Processed")):
            print("   ", line.strip()[:150])


if __name__ == "__main__":
    os.makedirs(RUNS, exist_ok=True)
    os.makedirs(WIND, exist_ok=True)
    {"check": check, "wind": wind, "runs": runs, "smoke": smoke}[sys.argv[1]]()
