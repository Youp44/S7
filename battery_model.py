"""
battery_model.py - Bouwt het PyBaMM-celmodel met degradatie.

Functies:
    build_degradation_model(mode)                    -> pybamm model
    build_parameter_values(ambient_c, parameter_set) -> pybamm.ParameterValues

Uitleg:
- PyBaMM rekent met 1 cel. Het pakket schalen we in load_profiles.py.
- 'SEI' = laagje dat op de anode groeit en lithium 'opsluit' (=capaciteitsverlies).
- 'lithium plating' = metallisch lithium op de anode, vooral bij laden/kou.
- 'thermal: lumped' = celtemperatuur wordt meegerekend (warmer = meer SEI-groei).

Rekenmodi (snel -> uitgebreid):
- "snel"      : SPM  + SEI, celtemperatuur constant.        Goed om de code te testen.
- "standaard" : SPMe + SEI + celtemperatuur (aanbevolen).   Vangt het effect van extra warmte door ePTO.
- "uitgebreid": SPMe + SEI + temperatuur + lithium plating. Traagst.
"""
import pybamm

MODES = ("snel", "standaard", "uitgebreid")


def build_degradation_model(mode: str = "standaard"):
    if mode not in MODES:
        raise ValueError(f"mode moet een van {MODES} zijn")

    if mode == "snel":
        return pybamm.lithium_ion.SPM({"SEI": "solvent-diffusion limited"})

    options = {
        "thermal": "lumped",
        "SEI": "solvent-diffusion limited",
        "SEI porosity change": "true",
    }
    if mode == "uitgebreid":
        options["lithium plating"] = "partially reversible"
        options["lithium plating porosity change"] = "true"
    # SPMe = snel genoeg voor dagen/weken simuleren; DFN is nauwkeuriger maar veel trager.
    return pybamm.lithium_ion.SPMe(options)


def build_parameter_values(ambient_c: float = 15.0, parameter_set: str = "OKane2022"):
    pv = pybamm.ParameterValues(parameter_set)
    ambient_k = 273.15 + ambient_c
    pv.update(
        {
            "Ambient temperature [K]": ambient_k,
            "Initial temperature [K]": ambient_k,
        },
        check_already_exists=False,
    )
    return pv
