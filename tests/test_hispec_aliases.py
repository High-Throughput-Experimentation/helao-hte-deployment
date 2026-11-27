"""HISPEC housekeeping experiments are published aliases of the ECHE/ECHEUVIS ones.

HISPEC sequences queue the shared names; the HISPEC names stay published so
restored queues still resolve, and must keep emitting the shared actions.
"""

import inspect

import pytest

from helao.deploy.hte.experiments import ECHE_exp, ECHEUVIS_exp, HISPEC_exp
from helao.deploy.hte.sequences import HISPEC_seq
from helao.helpers.premodels import Experiment

MASK = ("uuid", "timestamp", "time", "experiment", "action_order")
ALIASES = {
    "HISPEC_sub_unloadall_customs": ECHE_exp.ECHE_sub_unloadall_customs,
    "HISPEC_sub_startup": ECHE_exp.ECHE_sub_startup,
    "HISPEC_sub_shutdown": ECHE_exp.ECHE_sub_shutdown,
    "HISPEC_sub_load_solid": ECHE_exp.ECHE_sub_load_solid,
    "HISPEC_sub_add_liquid": ECHE_exp.ECHE_sub_add_liquid,
    "HISPEC_sub_engage": ECHEUVIS_exp.ECHEUVIS_sub_engage,
    "HISPEC_sub_disengage": ECHEUVIS_exp.ECHEUVIS_sub_disengage,
}


def _flat(fn, **kw):
    exp = Experiment(experiment_name=fn.__name__, experiment_params={})
    out = []
    for a in fn(exp, **kw):
        d = a.model_dump(mode="json")
        out.append({k: v for k, v in d.items() if not any(m in k for m in MASK)})
    return out


def _varied(fn):
    kw = {}
    for k, p in inspect.signature(fn).parameters.items():
        if isinstance(p.default, bool):
            kw[k] = not p.default
        elif isinstance(p.default, (int, float)):
            kw[k] = p.default + 3
    return kw


@pytest.mark.parametrize("name", sorted(ALIASES))
def test_alias_emits_shared_actions(name):
    alias, target = getattr(HISPEC_exp, name), ALIASES[name]
    assert name in HISPEC_exp.EXPERIMENTS
    assert _flat(alias) == _flat(target)
    assert _flat(alias, **_varied(alias)) == _flat(target, **_varied(alias))


@pytest.mark.parametrize("use_z_motor", [False, True])
@pytest.mark.parametrize("seq", HISPEC_seq.SEQUENCES)
def test_sequences_queue_shared_names(seq, use_z_motor):
    names = {
        e.experiment_name for e in getattr(HISPEC_seq, seq)(use_z_motor=use_z_motor)
    }
    assert not names & set(ALIASES)
