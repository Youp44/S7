"""
analysis.py - Vergelijkt de scenario's en maakt grafieken.

Functies:
    compare_degradation(res_without, res_with)  -> pandas DataFrame
    extrapolate_capacity(result, target_days)   -> (dagen, capaciteit_rel) indicatieve doorrekening
    plot_power_profiles(profiles)               -> figuur
    plot_degradation(res_without, res_with)     -> figuur
    plot_pack_currents(pack_results)            -> figuur
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def compare_degradation(res_without, res_with) -> pd.DataFrame:
    """Tabel met capaciteitsverlies per scenario aan het einde van de simulatie."""
    n = min(res_without["n_days_completed"], res_with["n_days_completed"])
    rows = []
    for res in (res_without, res_with):
        loss_pct = 100 * (1 - res["capacity_rel"][n - 1])
        rows.append({
            "scenario": res["scenario"],
            "dagen": n,
            "capaciteit_start_Ah": res["capacity_ah"][0],
            "capaciteit_eind_Ah": res["capacity_ah"][n - 1],
            "capaciteitsverlies_%": loss_pct,
            "verlies_per_dag_%": loss_pct / max(n - 1, 1),
            "LLI_%": res["lli_percent"][n - 1],
            "doorzet_Ah_per_cel": res["throughput_ah"][n - 1],
        })
    df = pd.DataFrame(rows).set_index("scenario")
    a, b = df["capaciteitsverlies_%"].iloc[0], df["capaciteitsverlies_%"].iloc[1]
    df.attrs["extra_verlies_door_epto_%"] = b - a
    df.attrs["relatief_meer_verlies_%"] = 100 * (b - a) / a if a > 0 else float("nan")
    return df


def extrapolate_capacity(result, target_days: int, fit_from_fraction: float = 0.5):
    """
    Indicatieve doorrekening naar bijv. 5 jaar (5*250 werkdagen) met een lineaire trend
    op de tweede helft van de gesimuleerde data. Let op: echte veroudering is niet lineair
    (eerst snel, later trager, en kan later weer versnellen). Gebruik dit als grove schatting.
    """
    days = result["days"].astype(float)
    cap = result["capacity_rel"]
    i0 = int(len(days) * fit_from_fraction)
    slope, intercept = np.polyfit(days[i0:], cap[i0:], 1)
    future = np.arange(1, target_days + 1)
    return future, intercept + slope * future


def plot_power_profiles(profiles: dict):
    """profiles = {'Zonder ePTO': (t, p), 'Met ePTO': (t, p)}"""
    fig, axes = plt.subplots(len(profiles), 1, figsize=(11, 3 * len(profiles)), sharex=True, sharey=True)
    axes = np.atleast_1d(axes)
    for ax, (name, (t, p)) in zip(axes, profiles.items()):
        ax.plot(t / 3600, p / 1000, lw=0.6)
        ax.set_ylabel("Vermogen accu [kW]")
        ax.set_title(name)
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("Tijd [uur]")
    fig.tight_layout()
    return fig


def plot_degradation(res_without, res_with):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for res in (res_without, res_with):
        axes[0].plot(res["days"], 100 * res["capacity_rel"], marker="o", ms=3, label=res["scenario"])
        axes[1].plot(res["days"], res["lli_percent"], marker="o", ms=3, label=res["scenario"])
    axes[0].set_ylabel("Capaciteit t.o.v. dag 1 [%]")
    axes[1].set_ylabel("Verlies aan cyclbaar lithium (LLI) [%]")
    for ax in axes:
        ax.set_xlabel("Werkdag")
        ax.grid(alpha=0.3)
        ax.legend()
    fig.tight_layout()
    return fig


def plot_pack_currents(pack_results: list):
    """Stroom door elke cel in het gesimuleerde module: laat de spreiding tussen cellen zien."""
    fig, axes = plt.subplots(len(pack_results), 1, figsize=(11, 3.2 * len(pack_results)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, res in zip(axes, pack_results):
        i_cells = np.asarray(res["output"]["Cell current [A]"])
        t_min = np.arange(i_cells.shape[0]) * res["dt_s"] / 60
        ax.plot(t_min, i_cells, lw=0.5, alpha=0.6)
        ax.set_ylabel("Celstroom [A]")
        ax.set_title(f"{res['scenario']} - {i_cells.shape[1]} cellen")
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("Tijd [min]")
    fig.tight_layout()
    return fig
