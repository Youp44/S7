"""
config.py - Alle aannames en instellingen op één plek.

Alles hier is THEORETISCH: er is nog geen echte klantdata. Zodra er data is,
pas je alleen deze waarden (en eventueel load_profiles.py) aan.
"""
from dataclasses import dataclass, field


@dataclass
class PackSpec:
    """Theoretisch batterijpakket van de vuilniswagen."""
    n_series: int = 216          # cellen in serie  -> ca. 216 * 3.7 V = ~800 V
    n_parallel: int = 52         # parallelle strings
    cell_capacity_ah: float = 5.0   # LG M50 (zit in de PyBaMM-parameterset)
    cell_nominal_voltage: float = 3.6

    @property
    def n_cells(self) -> int:
        return self.n_series * self.n_parallel

    @property
    def pack_energy_kwh(self) -> float:
        return self.n_cells * self.cell_capacity_ah * self.cell_nominal_voltage / 1000


@dataclass
class DutyCycleSpec:
    """Aannames voor één werkdag van de vuilniswagen (vermogens in kW aan de accu)."""
    dt_s: int = 10                    # tijdresolutie van het profiel
    seed: int = 42                    # zodat elke run hetzelfde profiel geeft

    # Transport (heen/terug naar route en naar afvalverwerker)
    transit_minutes_total: float = 70.0
    transit_power_kw: float = 35.0

    # Inzamelroute (stop-and-go)
    collection_hours: float = 5.5
    drive_segment_s: float = 60.0     # rijden tussen twee adressen
    drive_power_kw: float = 18.0      # gemiddeld tractievermogen tijdens rijden
    regen_power_kw: float = -8.0      # gemiddeld regeneratief remmen (negatief = laden)
    stop_segment_s: float = 45.0      # stilstaan bij adres

    # Basisverbruik (koeling, verlichting, DC/DC, ...) - altijd aan
    auxiliary_power_kw: float = 3.0

    # ePTO (opbouw: lift + perskast) - alleen tijdens stops
    epto_lift_kw: float = 12.0
    epto_lift_s: float = 10.0
    epto_compact_kw: float = 28.0
    epto_compact_s: float = 20.0


@dataclass
class ChargingSpec:
    """Nachtelijk laden in de depot."""
    depot_charger_kw: float = 22.0     # AC-lader
    charge_voltage_limit_v: float = 4.10   # laden tot ~95% SOC (laat ruimte voor regen)
    cutoff_current_a: float = 0.05
    rest_minutes: int = 60


@dataclass
class DegradationSpec:
    """Instellingen van de degradatiesimulatie."""
    n_days: int = 20                  # aantal gesimuleerde werkdagen (meer = trager)
    solver_dt_s: int = 30             # profiel wordt hiernaartoe gemiddeld (sneller rekenen)
    ambient_temperature_c: float = 15.0
    parameter_set: str = "OKane2022"  # PyBaMM-set voor SEI + lithium plating + LAM
    mode: str = "standaard"           # "snel", "standaard" of "uitgebreid" (zie battery_model.py)


@dataclass
class PackSimSpec:
    """Instellingen van de liionpack-simulatie (pakket met onderlinge verschillen)."""
    n_series: int = 8                 # klein representatief stukje pakket
    n_parallel: int = 4
    duration_minutes: int = 60        # lengte van de gesimuleerde werkperiode
    Rb: float = 1e-4                  # busbar-weerstand [Ohm]
    Rc: float = 1e-2                  # contactweerstand [Ohm]
    Ri: float = 5e-2                  # interne weerstand-spreiding, gemiddelde [Ohm]
    sigma_resistance: float = 0.10    # 10% spreiding in interne weerstand tussen cellen


PACK = PackSpec()
DUTY = DutyCycleSpec()
CHARGING = ChargingSpec()
DEGRADATION = DegradationSpec()
PACK_SIM = PackSimSpec()
