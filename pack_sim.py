"""
pack_sim.py - Simuleert een klein stuk pakket met liionpack (cellen met onderlinge verschillen).

Waarom? PyBaMM alleen rekent met 1 'gemiddelde' cel. In een echt pakket verschillen
cellen iets (capaciteit, weerstand) en dragen ze daardoor ongelijk veel stroom.
Cellen die meer stroom krijgen verouderen sneller. Liionpack laat dat zien.

Functies:
    select_work_window(time_s, power_w, start_min, duration_min) -> (t, p)
    run_pack_simulation(scenario_name, time_s, pack_power_w, pack, sim_spec) -> dict
    summarize_pack_result(result) -> dict met kerngetallen
"""
import liionpack as lp
import numpy as np
import pybamm

from config import PackSimSpec, PackSpec
from load_profiles import pack_power_to_module_current


def select_work_window(time_s, power_w, start_min: float, duration_min: float):
    """Knipt een stuk uit de werkdag (bijv. het eerste uur van de inzamelroute)."""
    dt = time_s[1] - time_s[0]
    i0 = int(start_min * 60 / dt)
    i1 = i0 + int(duration_min * 60 / dt)
    return time_s[i0:i1] - time_s[i0], power_w[i0:i1]


def run_pack_simulation(scenario_name, time_s, pack_power_w, pack: PackSpec, sim_spec: PackSimSpec,
                        initial_soc: float = 0.9, seed: int = 1):
    Ns, Np = sim_spec.n_series, sim_spec.n_parallel
    dt = float(time_s[1] - time_s[0])

    # Pakketvermogen -> stroom door dit kleine module (zelfde stroom per cel als in het echte pakket)
    module_current = pack_power_to_module_current(pack_power_w, pack, Ns, Np)

    # Netlist = het elektrische schema van het pakket (weerstanden, busbars, cellen)
    netlist = lp.setup_circuit(Np=Np, Ns=Ns, Rb=sim_spec.Rb, Rc=sim_spec.Rc,
                               Ri=sim_spec.Ri, V=4.0, I=float(module_current[0]))

    # Celvariatie: elke cel krijgt een iets andere interne weerstand (bijv. door productiespreiding
    # of ongelijke veroudering). Cellen met lage weerstand nemen meer stroom over.
    rng = np.random.default_rng(seed)
    ri_rows = netlist["desc"].str.startswith("Ri")
    n_cells = int(ri_rows.sum())
    scale = rng.normal(1.0, sim_spec.sigma_resistance, n_cells).clip(0.5, 1.5)
    netlist.loc[ri_rows, "value"] = netlist.loc[ri_rows, "value"].to_numpy() * scale

    pv = pybamm.ParameterValues("Chen2020")

    # Experiment: het stroomprofiel als 'drive cycle'; period = tijdstap van het profiel
    drive = np.column_stack([time_s, module_current])
    step = pybamm.step.current(drive)
    experiment = pybamm.Experiment([step], period=f"{int(dt)} seconds")

    output = lp.solve(
        netlist=netlist,
        sim_func=lp.basic_simulation,
        parameter_values=pv,
        experiment=experiment,
        initial_soc=initial_soc,
        output_variables=["Terminal voltage [V]", "Volume-averaged cell temperature [K]"],
    )
    return {"scenario": scenario_name, "output": output, "Ns": Ns, "Np": Np,
            "resistance_scale": scale, "dt_s": dt, "module_current": module_current}


def summarize_pack_result(result, cell_capacity_ah: float = 5.0):
    """Kerngetallen: hoe ongelijk is de stroomverdeling tussen parallelle cellen?"""
    out = result["output"]
    i_cells = np.asarray(out["Cell current [A]"])          # [tijdstappen, cellen]
    rms_per_cell = np.sqrt(np.mean(i_cells ** 2, axis=0))  # RMS-stroom ~ warmteontwikkeling
    return {
        "scenario": result["scenario"],
        "max_cell_current_A": float(np.max(np.abs(i_cells))),
        "max_c_rate": float(np.max(np.abs(i_cells)) / cell_capacity_ah),
        "rms_current_mean_A": float(rms_per_cell.mean()),
        "rms_current_spread_percent": float(100 * (rms_per_cell.max() - rms_per_cell.min())
                                            / rms_per_cell.mean()),
        "min_voltage_V": float(np.min(out["Terminal voltage [V]"])),
    }
