"""ECHE_sub_CA/CV/CP carry the LED cycle; the *_led names are published aliases.

A technique with an illumination_source runs the LED cycle and sends the TTL
params; without one it runs dark and sends neither, as before the merge.
"""

import pytest

from helao.deploy.hte.experiments import ECHE_exp as E
from helao.helpers.premodels import Experiment

MASK = ("uuid", "timestamp", "time", "experiment", "action_order")
LED = dict(
    illumination_source="doric_led2",
    toggle_dark_time_init=1.0,
    toggle_illum_duty=0.25,
    toggle_illum_period=4.0,
    gamrychannelwait=2,
    gamrychannelsend=3,
)
TECH = [
    (E.ECHE_sub_CA, E.ECHE_sub_CA_led, "run_CA"),
    (E.ECHE_sub_CV, E.ECHE_sub_CV_led, "run_CV"),
    (E.ECHE_sub_CP, E.ECHE_sub_CP_led, "run_CP"),
]


def _run(fn, **kw):
    exp = Experiment(experiment_name=fn.__name__, experiment_params={})
    return list(fn(exp, **kw))


def _flat(actions):
    out = []
    for a in actions:
        d = a.model_dump(mode="json")
        out.append({k: v for k, v in d.items() if not any(m in k for m in MASK)})
    return out


@pytest.mark.parametrize("plain,alias,endpoint", TECH)
def test_dark_sends_no_led_or_ttl(plain, alias, endpoint):
    acts = _run(plain)
    assert [a.action_name for a in acts] == ["archive_custom_query_sample", endpoint]
    assert not {"TTLwait", "TTLsend"} & set(acts[1].action_params)


@pytest.mark.parametrize("plain,alias,endpoint", TECH)
def test_lit_runs_cycle_with_ttl(plain, alias, endpoint):
    acts = _run(plain, **LED)
    names = [a.action_name for a in acts]
    assert names == [
        "archive_custom_query_sample",
        "set_digital_cycle",
        endpoint,
        "stop_digital_cycle",
    ]
    assert acts[1].action_params["out_name"] == "doric_led2"
    assert acts[2].action_params["TTLwait"] == 2
    assert acts[2].action_params["TTLsend"] == 3


@pytest.mark.parametrize("plain,alias,endpoint", TECH)
def test_alias_is_plain_lit_by_default(plain, alias, endpoint):
    assert alias.__name__ in E.EXPERIMENTS
    assert _flat(_run(alias)) == _flat(_run(plain, illumination_source="doric_led1"))
    assert _flat(_run(alias, **LED)) == _flat(_run(plain, **LED))
