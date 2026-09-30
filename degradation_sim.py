"""
degradation_sim.py - Simuleert N werkdagen (rijden + nachtladen) en leest de degradatie uit.

Functies:
    build_day_experiment(power_cell_w, time_s, charging, pack, n_days) -> pybamm.Experiment
    run_degradation(scenario_name, time_s, pack_power_w, ...)          -> dict met resultaten
"""
import time as _time

import numpy as np
import pybamm

from battery_model import build_degradation_model, build_parameter_values
from config import ChargingSpec, PackSpec
from load_profiles import pack_power_to_cell_power, resample_profile


def build_day_experiment(time_s, power_cell_w, charging: ChargingSpec, pack: PackSpec, n_days: int):
    """Eén dag = werkdag (vermogensprofiel) + CC-CV nachtlading + rust. Herhaald n_days keer."""
    drive_cycle = np.column_stack([time_s, power_cell_w])
    work = pybamm.step.power(drive_cycle, duration=float(time_s[-1]))

    # Laadstroom per cel afgeleid van de depotlader (P = I * V)
    charge_current_a = charging.depot_charger_kw * 1000 / pack.n_cells / pack.cell_nominal_voltage

    day = (
        work,
        f"Charge at {charge_current_a:.3f} A until {charging.charge_voltage_limit_v} V",
        f"Hold at {charging.charge_voltage_limit_v} V until {charging.cutoff_current_a} A",
        f"Rest for {charging.rest_minutes} minutes",
    )
    return pybamm.Experiment([day] * n_days)


def run_degradation(scenario_name, time_s, pack_power_w, pack: PackSpec, charging: ChargingSpec,
                    n_days: int, ambient_c: float, parameter_set: str = "OKane2022",
                    solver_dt_s: int = 30, mode: str = "standaard"):
    """Draait de simulatie en geeft een dict terug met per dag de capaciteit en SEI-verlies."""
    # Grover profiel = veel sneller rekenen; energie blijft gelijk (zie resample_profile)
    time_s, pack_power_w = resample_profile(time_s, pack_power_w, solver_dt_s)
    model = build_degradation_model(mode)
    pv = build_parameter_values(ambient_c, parameter_set)
    power_cell = pack_power_to_cell_power(pack_power_w, pack)
    experiment = build_day_experiment(time_s, power_cell, charging, pack, n_days)

    sim = pybamm.Simulation(model, parameter_values=pv, experiment=experiment)
    t0 = _time.time()
    sol = sim.solve(calc_esoh=True)
    runtime = _time.time() - t0

    sv = sol.summary_variables
    cap = np.asarray(sv["Capacity [A.h]"])
    n = len(cap)
    result = {
        "scenario": scenario_name,
        "n_days_completed": n,
        "days": np.arange(1, n + 1),
        "capacity_ah": cap,
        "capacity_rel": cap / cap[0],
        "lli_percent": np.asarray(sv["Loss of lithium inventory [%]"]),
        "throughput_ah": np.asarray(sv["Throughput capacity [A.h]"]),
        "runtime_s": runtime,
        "solution": sol,
    }
    # Aantal dagen kan lager zijn dan gevraagd als de accu een spanningsgrens raakt
    if n < n_days:
        print(f"[{scenario_name}] Let op: slechts {n} van {n_days} dagen voltooid "
              f"(waarschijnlijk spanningsgrens geraakt - profiel te zwaar voor de accu).")
    return result
