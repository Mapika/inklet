"""Shared loading for ATLAS Figure 5 (HEPData record ins2104706, table 5 and 6).

Each HEPData table gives, per particle, the mass, the value kappa_F m_F / vev
(or sqrt(kappa_V) m_V / vev) and the coupling modifier kappa, each with an
asymmetric uncertainty. Nothing here is recomputed from the couplings; the
values are read as published.
"""
import re
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
WITHOUT_KC = HERE / "data" / "figure_5_without_kc.yaml"   # kappa_c = kappa_t, p = 56 %
WITH_KC = HERE / "data" / "figure_5_with_kc.yaml"         # kappa_c free, p = 65 %

NAMES = {"t": "t", "Z": "Z", "W": "W", "b": "b", "tau": "τ", "mu": "μ", "c": "c"}
VEV = 246.0   # GeV; the caption's value, and the one the table values are computed with
Y_TOP = "$\\kappa_{F}\\frac{m_{F}}{\\text{vev}}$ or $\\sqrt{\\kappa_{V}}\\frac{m_{V}}{\\text{vev}}$"


def _errors(cell):
    """(value, down, up) with the asymmetric errors as positive distances."""
    err = cell["errors"][0]["asymerror"]
    return cell["value"], -err["minus"], err["plus"]


def load(path):
    """One dict per particle: name, mass, top (kappa m / vev) and kappa, each (value, down, up)."""
    doc = yaml.safe_load(Path(path).read_text())
    labels = [re.search(r"kappa_\{\\?(\w+)\}", v["value"]).group(1)
              for v in doc["independent_variables"][0]["values"]]
    masses = [v["value"] for v in doc["dependent_variables"][0]["values"]]
    top = [_errors(v) for v in doc["dependent_variables"][1]["values"]]
    kappa = [_errors(v) for v in doc["dependent_variables"][2]["values"]]
    return [dict(name=NAMES[lab], mass=m, top=t, kappa=k)
            for lab, m, t, k in zip(labels, masses, top, kappa)]


def by_name(rows):
    return {r["name"]: r for r in rows}
