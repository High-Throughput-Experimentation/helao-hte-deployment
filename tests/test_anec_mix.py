"""ANEC sampling: the mixing experiments are their _nomixing twins with mix=True.

ANEC_sub_aliquot and ANEC_sub_GC_preparation stay published as aliases so queued
runs resolve; mix=True prepends the two flow reversals, mix=False emits none.
"""

import pytest

from helao.deploy.hte.experiments import ANEC_exp as A
from helao.helpers.premodels import Experiment

MASK = ("uuid", "timestamp", "time", "experiment", "action_order")
PAIRS = [
    (A.ANEC_sub_aliquot, A.ANEC_sub_aliquot_nomixing),
    (A.ANEC_sub_GC_preparation, A.ANEC_sub_GC_headspacealiquot_nomixing),
]


def _flat(fn, **kw):
    exp = Experiment(experiment_name=fn.__name__, experiment_params={})
    out = []
    for a in fn(exp, **kw):
        d = a.model_dump(mode="json")
        out.append({k: v for k, v in d.items() if not any(m in k for m in MASK)})
    return out


@pytest.mark.parametrize("alias,base", PAIRS)
def test_alias_is_base_with_mixing(alias, base):
    assert alias.__name__ in A.EXPERIMENTS
    mixed = _flat(base, mix=True, volume_ul_GC=150)
    assert _flat(alias, volume_ul_GC=150) == mixed
    plain = _flat(base, volume_ul_GC=150)
    assert mixed[len(mixed) - len(plain) :] == plain
    reversals = [
        a for a in mixed[: len(mixed) - len(plain)] if a["action_name"] == "pump"
    ]
    assert [a["action_params"]["on"] for a in reversals] == [1, 0, 1, 0]
