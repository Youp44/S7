"""
load_profiles.py - Maakt het theoretische vermogensprofiel van één werkdag.

Functies:
    build_daily_power_profile(duty, with_epto) -> (tijd [s], vermogen pakket [W])
    pack_power_to_cell_power(power_w, pack)    -> vermogen per cel [W]
    pack_power_to_module_current(...)          -> stroom voor een klein module [A]

Sign-conventie PyBaMM: positief = ontladen (accu levert), negatief = laden (regen).
"""
import numpy as np

from config import DutyCycleSpec, PackSpec


def build_daily_power_profile(duty: DutyCycleSpec, with_epto: bool):
    """
    Bouwt één werkdag: transport heen -> inzamelroute -> transport naar
    afvalverwerker/terug. De rij-delen zijn IDENTIEK voor beide scenario's
    (zelfde seed). Het enige verschil is de ePTO-belasting tijdens de stops.
    """
    rng = np.random.default_rng(duty.seed)   # zelfde 'toevalligheden' in beide scenario's
    dt = duty.dt_s
    blocks = []

    def transit(minutes):
        n = int(minutes * 60 / dt)
        noise = rng.normal(0, 4_000, n)      # kleine variaties (heuvels, verkeer)
        return duty.transit_power_kw * 1000 + noise + duty.auxiliary_power_kw * 1000

    half = duty.transit_minutes_total / 2
    blocks.append(transit(half))

    # Inzamelroute
    n_cycles = int(duty.collection_hours * 3600 / (duty.drive_segment_s + duty.stop_segment_s))
    for _ in range(n_cycles):
        # rijden: eerst optrekken (positief), daarna remmen (negatief = regen)
        n_drive = int(duty.drive_segment_s / dt)
        drive = np.full(n_drive, duty.drive_power_kw * 1000.0)
        drive[-max(1, n_drive // 4):] = duty.regen_power_kw * 1000.0   # laatste kwart = remmen
        drive = drive + rng.normal(0, 2_000, n_drive) + duty.auxiliary_power_kw * 1000

        # stilstaan bij adres: alleen basisverbruik, plus ePTO als die aan staat
        n_stop = int(duty.stop_segment_s / dt)
        stop = np.full(n_stop, duty.auxiliary_power_kw * 1000.0)
        if with_epto:
            n_lift = max(1, int(duty.epto_lift_s / dt))
            n_comp = max(1, int(duty.epto_compact_s / dt))
            stop[:n_lift] += duty.epto_lift_kw * 1000
            stop[n_lift:n_lift + n_comp] += duty.epto_compact_kw * 1000
        blocks.extend([drive, stop])

    blocks.append(transit(half))

    power = np.concatenate(blocks)
    time = np.arange(len(power)) * dt
    return time, power


def pack_power_to_cell_power(power_pack_w: np.ndarray, pack: PackSpec) -> np.ndarray:
    """Deelt het pakketvermogen gelijk over alle cellen (eerste benadering)."""
    return power_pack_w / pack.n_cells


def pack_power_to_module_current(power_pack_w, pack: PackSpec, n_series, n_parallel, v_cell=3.7):
    """
    Zet pakketvermogen om naar stroom voor een klein deel van het pakket
    (bijv. 8s4p) voor de liionpack-simulatie. Benadering met een vaste celspanning.
    """
    power_cell = pack_power_to_cell_power(power_pack_w, pack)
    current_cell = power_cell / v_cell
    return current_cell * n_parallel      # stroom door de hele module


def daily_energy_kwh(time_s, power_w) -> dict:
    """Handige controle: hoeveel energie wordt er verbruikt/teruggewonnen?"""
    dt = np.diff(time_s, prepend=time_s[0] - (time_s[1] - time_s[0]))
    e = power_w * dt / 3.6e6
    return {
        "verbruikt_kWh": float(e[e > 0].sum()),
        "regen_kWh": float(-e[e < 0].sum()),
        "netto_kWh": float(e.sum()),
    }


def resample_profile(time_s, power_w, new_dt_s):
    """
    Maakt het profiel grover (bijv. van 10 s naar 30 s) door te middelen.
    Middelen behoudt de energie, dus het totale verbruik blijft kloppen,
    maar de simulatie wordt veel sneller.
    """
    old_dt = time_s[1] - time_s[0]
    k = int(round(new_dt_s / old_dt))
    if k <= 1:
        return time_s, power_w
    n = len(power_w) // k * k
    p_new = power_w[:n].reshape(-1, k).mean(axis=1)
    t_new = np.arange(len(p_new)) * float(new_dt_s)
    return t_new, p_new
