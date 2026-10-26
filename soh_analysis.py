"""SOH-verkenning voor een elektrische vuilniswagen met e-PTO.

Plaats dit bestand naast config.py en (later) weekdata.csv in S7-main.
Start in Spyder met F5. Dit is een DATA-analyse, nog geen PyBaMM-fit.

Vereiste CSV-kolommen:
 timestamp, soc, battery_voltage_v, battery_current_a
Optioneel: epto_power_kw, battery_temperature_c
SOC is in procenten (0..100). Positieve batterijSTROOM = ontladen.
Eenheid stroom: A, spanning: V, e-PTO: kW.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

try:
    from config import PACK
    REFERENCE_KWH = PACK.pack_energy_kwh  # theoretische referentie uit project
except ImportError:
    REFERENCE_KWH = 202.176  # alleen fallback, niet als gemeten capaciteit interpreteren

CSV_FILE = Path(__file__).resolve().parent / 'weekdata.csv'
MIN_SOC_DROP_PCT = 10.0   # minimaal 10 procentpunt SOC-daling per segment
MAX_GAP_SECONDS = 300     # gaten > 5 minuten splitsen segmenten
SOC_RISE_TOLERANCE = 0.3  # kleine meetruis tolereren


def load_data(path):
    if not path.exists():
        raise FileNotFoundError(
            f'Geen weekdata gevonden: {path}\n'
            'Zet weekdata.csv in dezelfde map als soh_analysis.py.')
    df = pd.read_csv(path, sep=None, engine='python')
    required = ['timestamp', 'soc', 'battery_voltage_v', 'battery_current_a']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f'Ontbrekende kolommen: {missing}. Beschikbaar: {list(df.columns)}')
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    for col in required[1:] + [c for c in ('epto_power_kw', 'battery_temperature_c') if c in df]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=required).sort_values('timestamp').drop_duplicates('timestamp').reset_index(drop=True)
    if len(df) < 3:
        raise ValueError('Te weinig geldige meetpunten.')
    if not df['soc'].between(0, 100).all():
        raise ValueError('SOC moet in procenten tussen 0 en 100 staan.')
    df['dt_s'] = df['timestamp'].diff().dt.total_seconds()
    # Intervalenergie met gemiddeld vermogen van de twee meetpunten (trapeziumregel)
    df['battery_power_kw'] = df['battery_voltage_v'] * df['battery_current_a'] / 1000
    prev_p = df['battery_power_kw'].shift(1)
    valid = df['dt_s'].between(0, MAX_GAP_SECONDS, inclusive='both')
    df['interval_energy_kwh'] = np.where(valid, (df['battery_power_kw'] + prev_p) / 2 * df['dt_s'] / 3600, np.nan)
    return df


def find_discharge_segments(df):
    """Schat energiecapaciteit alleen uit aaneengesloten ontlaadsegmenten.

    Sluit laden, grote datagaten en stijgende SOC uit. De schatting blijft
    gevoelig voor SOC-kalibratie, temperatuur, meetruis en bruikbaar SOC-venster.
    """
    segments = []
    start = None
    energy = 0.0

    def finish(end_idx):
        nonlocal start, energy
        if start is not None and end_idx > start:
            soc_drop = float(df.loc[start, 'soc'] - df.loc[end_idx, 'soc'])
            if soc_drop >= MIN_SOC_DROP_PCT and energy > 0:
                segments.append({
                    'begin': df.loc[start, 'timestamp'],
                    'einde': df.loc[end_idx, 'timestamp'],
                    'soc_daling_pctpunt': soc_drop,
                    'ontladen_kwh': energy,
                    'geschatte_capaciteit_kwh': energy / (soc_drop / 100),
                })
        start, energy = None, 0.0

    for i in range(1, len(df)):
        row, prev = df.iloc[i], df.iloc[i - 1]
        valid = (pd.notna(row['interval_energy_kwh'])
                 and row['interval_energy_kwh'] > 0
                 and row['soc'] <= prev['soc'] + SOC_RISE_TOLERANCE)
        if not valid:
            finish(i - 1)
            continue
        if start is None:
            start = i - 1
            energy = 0.0
        energy += float(row['interval_energy_kwh'])
    finish(len(df) - 1)
    return pd.DataFrame(segments)


def main():
    df = load_data(CSV_FILE)
    print(f'Meetpunten: {len(df)} | {df.timestamp.min()} tot {df.timestamp.max()}')
    print('Let op: positief stroomteken moet ONTLADEN betekenen!')
    print(f'Theoretische referentiecapaciteit: {REFERENCE_KWH:.2f} kWh')
    discharged = df['interval_energy_kwh'].clip(lower=0).sum()
    charged = -df['interval_energy_kwh'].clip(upper=0).sum()
    print(f'Ontladen energie (geldige intervallen): {discharged:.2f} kWh')
    print(f'Geladen energie (geldige intervallen): {charged:.2f} kWh')
    if 'epto_power_kw' in df:
        dt_h = df['dt_s'].where(df['dt_s'].between(0, MAX_GAP_SECONDS), 0) / 3600
        epto_kwh = (df['epto_power_kw'].clip(lower=0).fillna(0) * dt_h).sum()
        print(f'e-PTO-energie (indicatief): {epto_kwh:.2f} kWh')
        print('Tel e-PTO niet nogmaals bij batterijvermogen op: dat kan dubbeltellen.')

    segments = find_discharge_segments(df)
    if segments.empty:
        print('\nGeen geschikt ontlaadsegment met voldoende SOC-daling gevonden.')
        print('SOH kan met deze meetdata nog niet verantwoord worden geschat.')
    else:
        print('\nCapaciteitsschattingen per ontlaadsegment:')
        print(segments.to_string(index=False))
        segments.to_csv(CSV_FILE.parent / 'soh_segmenten.csv', index=False)
        capacity = float(segments['geschatte_capaciteit_kwh'].median())
        print(f'\nMediane geschatte bruikbare energiecapaciteit: {capacity:.1f} kWh')
        print(f'Indicatieve energieratio t.o.v. theoretische referentie: {100 * capacity / REFERENCE_KWH:.1f}%')
        print('Dit is GEEN gevalideerde SOH: vergelijk met dezelfde meetcondities en nieuwstaat.')

    fig, axes = plt.subplots(3 if 'epto_power_kw' in df else 2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(df['timestamp'], df['soc'])
    axes[0].set_ylabel('SOC [%]')
    axes[1].plot(df['timestamp'], df['battery_power_kw'])
    axes[1].set_ylabel('Batterij [kW]')
    if 'epto_power_kw' in df:
        axes[2].plot(df['timestamp'], df['epto_power_kw'])
        axes[2].set_ylabel('e-PTO [kW]')
    axes[-1].set_xlabel('Tijd')
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.suptitle('Vuilniswagen – weekdata en e-PTO')
    fig.tight_layout()
    plt.show()


if __name__ == '__main__':
    main()
