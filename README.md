# Batterijdegradatie vuilniswagen: met en zonder ePTO

Theoretisch simulatiemodel (PyBaMM en liionpack) dat de veroudering van de tractiebatterij van een elektrische vuilniswagen vergelijkt in twee scenario's:

- **Zonder ePTO**: de batterij levert alleen rijden en basisverbruik. De opbouw (lift en perskast) draait op een andere energiebron.
- **Met ePTO**: de opbouw haalt tijdens elke stop vermogen uit dezelfde batterij.

> **Let op:** er is nog geen echte klantdata. Alle getallen in `config.py` zijn aannames. Het model laat het *verschil tussen de scenario's* zien en bepaalt welke data we bij de klant moeten opvragen. Het is **geen voorspelling van de levensduur**.

## Doel

1. Inzicht geven in hoeveel extra belasting en degradatie ePTO-gebruik oplevert ten opzichte van een wagen zonder ePTO.
2. Een werkend raamwerk neerzetten waarin echte data later direct kan worden ingeladen.
3. Een concrete lijst met te vragen data opleveren voor het volgende klantcontact (zie onderaan).

## Projectstructuur

Elk bestand doet één ding. Het notebook roept alles aan.

| Bestand | Functie |
|---|---|
| `config.py` | Alle aannames en instellingen op één plek: pakket, dagcyclus, laden, degradatie- en pakketsimulatie. |
| `load_profiles.py` | Bouwt het vermogensprofiel van één werkdag, met en zonder ePTO. |
| `battery_model.py` | Het PyBaMM-celmodel met degradatie (SEI-groei, temperatuur, optioneel lithium plating). |
| `degradation_sim.py` | Simuleert meerdere werkdagen (rijden, nachtladen, rust) en leest het capaciteitsverlies uit. |
| `pack_sim.py` | Liionpack-simulatie van een klein deel van het pakket met onderling verschillende cellen. |
| `analysis.py` | Vergelijkingstabel, grafieken en een grove extrapolatie naar 5 jaar. |
| `run_analysis.ipynb` | Notebook dat alle onderdelen aanroept, met uitleg per stap. |
| `requirements.txt` | Vastgezette pakketversies. |

## Hoe het model werkt

### 1. Vermogensprofiel van één werkdag (`load_profiles.py`)

Een werkdag bestaat uit: transport heen, inzamelroute (stop-and-go), transport terug. De rit is in beide scenario's **identiek** (zelfde seed voor de willekeurige variatie). Alleen de ePTO-belasting verschilt.

Standaardaannames:

| Onderdeel | Waarde |
|---|---|
| Transport | 70 min in totaal, 35 kW |
| Inzamelroute | 5,5 uur |
| Rijden tussen adressen | 60 s, gemiddeld 18 kW, laatste kwart regeneratief remmen (-8 kW) |
| Stilstaan bij adres | 45 s |
| Basisverbruik (altijd aan) | 3 kW |
| ePTO lift | 12 kW gedurende 10 s per stop |
| ePTO perskast | 28 kW gedurende 20 s per stop |

Dit komt neer op circa 105 kWh per dag zonder ePTO en circa 141 kWh met ePTO.

Conventie: positief vermogen = ontladen, negatief = laden (regeneratie).

### 2. Pakketschaling

PyBaMM rekent met één cel. Het pakketvermogen wordt gelijk over alle cellen verdeeld.

Theoretisch pakket: **216 in serie x 52 parallel** (11.232 cellen, circa 202 kWh), cellen van het type LG M50 (5 Ah).

### 3. Degradatiesimulatie (`degradation_sim.py`, `battery_model.py`)

Elke gesimuleerde dag bestaat uit de werkdag, nachtladen (CC-CV, 22 kW depotlader, tot 4,10 V per cel) en een rustperiode. Het model berekent daarbij de groei van de SEI-laag, het laagje op de anode dat lithium opsluit en zo capaciteit kost. Er zijn drie rekenmodi:

| Modus | Model | Gebruik |
|---|---|---|
| `snel` | SPM + SEI, vaste temperatuur | Code testen (seconden) |
| `standaard` | SPMe + SEI + celtemperatuur | Aanbevolen voor echte runs |
| `uitgebreid` | SPMe + SEI + temperatuur + lithium plating | Traagst, niet doorgerekend in de tests |

Uitvoer per dag: capaciteit, relatieve capaciteit, verlies aan cyclbaar lithium (LLI) en doorgezette lading.

### 4. Pakketsimulatie (`pack_sim.py`)

Liionpack bouwt een elektrisch schema van een klein stuk pakket (standaard 8 in serie x 4 parallel) met busbar- en contactweerstanden. Elke cel krijgt een iets andere interne weerstand (10% spreiding). Zo wordt zichtbaar hoe ongelijk de stroom over parallelle cellen verdeeld wordt. Cellen met meer stroom verouderen sneller.

## Installatie

Gebruik een **eigen virtuele omgeving, buiten OneDrive en buiten de git-map**, zodat pakketten niet met andere projecten conflicteren:

```
python -m venv C:\venvs\epto_env
C:\venvs\epto_env\Scripts\python -m pip install --upgrade pip
C:\venvs\epto_env\Scripts\python -m pip install -r requirements.txt
C:\venvs\epto_env\Scripts\python -m ipykernel install --user --name epto_env --display-name "Python (epto_env)"
```

Kies daarna in VS Code bij **Select Kernel** de kernel `Python (epto_env)`.

**Waarom vaste versies?**

- Liionpack 0.4.0 werkt niet met nieuwere PyBaMM-versies, daarom `pybamm==24.11.2`.
- `casadi` moet exact `3.6.7` zijn. Een nieuwere versie geeft de fout *"DeSerialization of FunctionInternal failed"*.
- Gebruik geen `--force-reinstall`, dat kan bestaande pakketten beschadigen.

Controle in een notebookcel:

```python
import sys, pybamm, casadi
print(sys.executable)
print(pybamm.__version__, casadi.__version__)   # verwacht: 24.11.2 3.6.7
```

## Gebruik

1. Open `run_analysis.ipynb` en selecteer de kernel `Python (epto_env)`.
2. Laat `SNEL_TESTEN = True` staan voor een eerste run (3 dagen, modus `snel`, enkele seconden).
3. Zet `SNEL_TESTEN = False` voor de echte run (standaard 20 dagen, modus `standaard`). Reken op ruim een halfuur of langer voor beide scenario's samen. Laat dit bij voorkeur niet tijdens ander werk draaien.
4. Pas aannames aan in `config.py`, niet in de andere bestanden.

## Resultaten lezen

- **Vermogensprofielen**: bevestigen dat beide scenario's dezelfde rit hebben en alleen de ePTO-pieken verschillen.
- **Pakketstromen**: spreiding van de celstroom, de eerste aanwijzing voor ongelijke belasting.
- **Vergelijkingstabel**: capaciteitsverlies, verlies per dag, LLI en doorzet, per scenario.
- **Extrapolatie naar 5 jaar**: lineair en dus grof. Echte veroudering is niet lineair. Lees dit als richting, niet als uitkomst.

## Beperkingen

- Alle invoer is theoretisch; er is geen validatie tegen metingen.
- Het pakketvermogen wordt gelijk over de cellen verdeeld; temperatuurverschillen binnen het pakket zitten niet in de degradatiesimulatie.
- Koeling en verwarming van het pakket zijn niet gemodelleerd.
- Over korte simulaties (enkele dagen) is het absolute verschil tussen de scenario's erg klein. Het zegt dan vooral iets over de richting.
- Lithium plating zit alleen in de modus `uitgebreid`.
- Het model gaat uit van één celtype en één laadstrategie.

## Data om bij de klant op te vragen

Als echte data beschikbaar komt, vervang dan de aannames in `config.py` (en eventueel de profielopbouw in `load_profiles.py`):

- Accugrootte, celtype, configuratie (serie/parallel) en gebruikte SOC-window.
- Gelogd batterijvermogen of -stroom (CAN of telematica), idealiter met en zonder ePTO-gebruik.
- Aantal stops per route, ePTO-vermogen per bewegingsdeel (lift, pers) en de duur ervan.
- Route-eigenschappen: transportafstand, hoogteverschillen, werkdagen per jaar.
- Laadstrategie: laadvermogen, laadtijd en laadlimiet (bijvoorbeeld tot 90% of 100%).
- Omgevingstemperatuur en koelstrategie van het pakket.
- Indien mogelijk: gemeten capaciteit of SOH na enkele maanden, om het model te kalibreren.

## Git

Voeg een `.gitignore` toe zodat omgevingen en tijdelijke bestanden niet in de repository komen:

```
venv/
.venv/
env/
epto_env/
__pycache__/
.ipynb_checkpoints/
*.pyc
```
