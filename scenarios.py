"""
scenarios.py - Routes en ePTO-gebruik als losse bouwstenen, gecombineerd tot scenario's.

Idee: een scenario = een ROUTE (hoe de wagen rijdt) x een EPTO-GEBRUIK (hoe de opbouw de accu belast).
Zo vergelijk je routes onderling en ePTO-varianten per route, zonder iets dubbel in te typen.

Uitbreiden:
- Nieuwe route?       Voeg een regel toe aan ROUTES.
- Nieuw ePTO-gebruik? Voeg een regel toe aan EPTO_GEBRUIK.
De scenario's (SCENARIOS) worden daarna vanzelf aangemaakt. Alle waarden zijn THEORETISCHE aannames.

Gebruik in het notebook:
    from scenarios import SCENARIOS, BASIS_VAN, selecteer
"""
from dataclasses import replace

from config import DUTY

# --------------------------------------------------------------------------------------------
# 1. ROUTES - overschrijft de rij-velden van DutyCycleSpec (config.py)
#    Tip: kies tijden als veelvoud van DUTY.dt_s (10 s), anders worden ze afgerond.
# --------------------------------------------------------------------------------------------
ROUTES = {
    # Veel korte stukjes rijden en veel stops, korte aanrijtijd
    "Route 1 (stad)": replace(
        DUTY,
        transit_minutes_total=40.0, transit_power_kw=30.0,
        collection_hours=5.5,
        drive_segment_s=40.0, drive_power_kw=15.0, regen_power_kw=-8.0,
        stop_segment_s=50.0,
    ),
    # Minder stops, langere stukken rijden, lange aanrijtijd naar het rayon
    "Route 2 (buitengebied)": replace(
        DUTY,
        transit_minutes_total=90.0, transit_power_kw=35.0,
        collection_hours=5.0,
        drive_segment_s=120.0, drive_power_kw=18.0, regen_power_kw=-8.0,
        stop_segment_s=40.0,
    ),
}

# --------------------------------------------------------------------------------------------
# 2. EPTO-GEBRUIK - overschrijft de ePTO-velden van DutyCycleSpec
#    None = geen ePTO op de batterij. {} = standaardwaarden uit config.py.
#    Standaard perskast: 28 kW x 20 s = 560 kW*s per stop.
#    "hoge piek" en "lage piek" hebben dezelfde energie als standaard, maar een andere vorm:
#    zo scheid je het effect van ENERGIE van het effect van VERMOGENSPIEKEN.
# --------------------------------------------------------------------------------------------
EPTO_GEBRUIK = {
    "Zonder ePTO":      None,
    "ePTO standaard":   {},
    "ePTO pers":   {"epto_compact_kw": 56.0, "epto_compact_s": 30.0},  # 56 kW x 30 s
    "ePTO arm-lift":   {"epto_compact_kw": 18.0, "epto_compact_s": 15.0},  # 18 kW x 15 s
    "ePTO totaal":   {"epto_compact_kw": 74.0, "epto_compact_s": 20.0},  # 18 kW x 30 s
}


# --------------------------------------------------------------------------------------------
# 3. Combineren (hier hoef je niets te wijzigen)
# --------------------------------------------------------------------------------------------
def _maak_scenarios():
    scenarios, basis_van = {}, {}
    for route_naam, route in ROUTES.items():
        for epto_naam, epto in EPTO_GEBRUIK.items():
            naam = f"{route_naam} | {epto_naam}"
            scenarios[naam] = (route, False) if epto is None else (replace(route, **epto), True)
            basis_van[naam] = f"{route_naam} | Zonder ePTO"   # vergelijkingsbasis binnen dezelfde route
    return scenarios, basis_van


SCENARIOS, BASIS_VAN = _maak_scenarios()


def selecteer(routes=None, epto=None):
    """
    Kies een deel van de scenario's, bijv. selecteer(routes=["Route 1 (stad)"], epto=["ePTO standaard"]).
    None = alles. De basis ('Zonder ePTO') van elke gekozen route wordt automatisch meegenomen.
    """
    def gekozen(naam):
        route_naam, epto_naam = naam.split(" | ")
        return (routes is None or route_naam in routes) and (epto is None or epto_naam in epto)

    namen = {n for n in SCENARIOS if gekozen(n)}
    namen |= {BASIS_VAN[n] for n in list(namen)}
    return {n: SCENARIOS[n] for n in SCENARIOS if n in namen}   # volgorde van SCENARIOS behouden