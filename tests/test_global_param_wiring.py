"""Every global an experiment reads is published by an earlier experiment.

A sequence passes values between experiments through orchestrator globals:
an action's ``to_global_params`` publishes, a later experiment's
``from_global_exp_params`` reads. A key nobody in the sequence publishes is
filled from whatever an unrelated earlier run left behind (HISPEC_EIS_only's
PEIS read ``Ewe_V__mean_final`` while its OCV published ``HISPEC_OCV``).
"""

import importlib
import inspect
import pkgutil

import pytest

from helao.deploy.hte import experiments, sequences
from helao.helpers.premodels import Experiment


def _mods(pkg):
    return [
        importlib.import_module(f"{pkg.__name__}.{m.name}")
        for m in pkgutil.iter_modules(pkg.__path__)
    ]


EXPS = {
    n: getattr(m, n) for m in _mods(experiments) for n in getattr(m, "EXPERIMENTS", [])
}
CASES = [
    (m.__name__.rsplit(".", 1)[1], n, flip)
    for m in _mods(sequences)
    for n in getattr(m, "SEQUENCES", [])
    for flip in [None]
    + [
        p.name
        for p in inspect.signature(getattr(m, n)).parameters.values()
        if isinstance(p.default, bool)
    ]
]


# Globals deliberately carried over from an earlier sequence (owner ruling
# 2026-11-19): the reader is meant to use the last value any run published.
CARRIED_OVER = {
    # target CO2 comes from the last headspace_purge_and_measure reading
    ("CCSI_Solution_co2maintainconcentration", "mean_co2_ppm"),
    # without the z motor the intensity calibration is not repeated per run
    ("ECHEUVIS_multiCA_led", "calibrated_int_time_ms"),
}


def _published(fn, em):
    """Global keys the experiment's actions publish."""
    args = inspect.getfullargspec(fn).args
    params = dict(em.experiment_params)
    for target in (em.from_global_exp_params or {}).values():
        params.setdefault(target, 0.0)  # the orchestrator folds these in first
    exp = Experiment(
        experiment_name=em.experiment_name, experiment_params=em.experiment_params
    )
    keys = set()
    for a in fn(exp, **{k: v for k, v in params.items() if k in args}) or []:
        tgp = a.to_global_params or []
        keys |= set(tgp.values()) if isinstance(tgp, dict) else set(tgp)
        if a.action_name == "add_global_param":
            keys.add(a.action_params.get("param_name"))
    return keys


@pytest.mark.parametrize("mod,seq,flip", CASES, ids=lambda v: str(v))
def test_globals_read_are_published_earlier(mod, seq, flip):
    fn = getattr(importlib.import_module(f"{sequences.__name__}.{mod}"), seq)
    kw = (
        {}
        if flip is None
        else {flip: not inspect.signature(fn).parameters[flip].default}
    )
    published, missing = set(), []
    for em in fn(**kw):
        for key in em.from_global_exp_params or {}:
            if key not in published and (seq, key) not in CARRIED_OVER:
                missing.append(f"{em.experiment_name} reads {key!r}")
        f = EXPS.get(em.experiment_name)
        if f is not None:
            published |= _published(f, em)
    assert not missing, missing


def test_carried_over_entries_are_still_read():
    read = {
        (n, key)
        for m in _mods(sequences)
        for n in getattr(m, "SEQUENCES", [])
        for em in getattr(m, n)()
        for key in em.from_global_exp_params or {}
    }
    assert CARRIED_OVER <= read
