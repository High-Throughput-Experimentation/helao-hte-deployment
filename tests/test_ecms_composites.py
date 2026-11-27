"""ECMS_sub_fill / ECMS_sub_empty_cell are the published step experiments in order.

The sequences used to queue those steps one experiment each; the composites must
emit exactly the same actions so the move changes record grouping only. The step
experiments stay published (restored queues re-pair by name).
"""

import pytest

from helao.deploy.hte.experiments import ECMS_exp as E
from helao.helpers.premodels import Experiment

MASK = ("uuid", "timestamp", "time", "experiment", "action_order")


def _flat(fn, **kw):
    exp = Experiment(experiment_name=fn.__name__, experiment_params={})
    out = []
    for a in fn(exp, **kw):
        d = a.model_dump(mode="json")
        out.append({k: v for k, v in d.items() if not any(m in k for m in MASK)})
    return out


FILL = dict(
    liquid_backward_time=7,
    reservoir_liquid_sample_no=3,
    volume_ul_cell_liquid=600,
)
PURGE = dict(
    CO2equilibrium_duration=11,
    flowrate_sccm=4.0,
    flow_ramp_sccm=0.5,
    MS_baseline_duration=22,
)


@pytest.mark.parametrize("recirc", [False, True])
@pytest.mark.parametrize("vacuum", [False, True])
@pytest.mark.parametrize("start", [False, True])
def test_fill_is_its_steps(recirc, vacuum, start):
    want = []
    if recirc:
        want += _flat(
            E.ECMS_sub_electrolyte_fill_recirculationreservoir, liquid_fill_time=5
        )
    if vacuum:
        want += _flat(E.ECMS_sub_prevacuum_cell, vacuum_time=6)
    cell = (
        E.ECMS_sub_electrolyte_fill_cell_recirculation
        if recirc
        else E.ECMS_sub_electrolyte_fill_cell
    )
    want += _flat(cell, **FILL)
    want += _flat(E.ECMS_sub_headspace_purge_and_CO2baseline, **PURGE)
    if start:
        want += _flat(E.ECMS_sub_electrolyte_recirculation_on)
    got = _flat(
        E.ECMS_sub_fill,
        recirculation=recirc,
        prevacuum=vacuum,
        start_recirculation=start,
        liquid_fill_time=5,
        vacuum_time=6,
        **FILL,
        **PURGE,
    )
    assert got == want


@pytest.mark.parametrize("stop", [False, True])
@pytest.mark.parametrize("recirc,cleans", [(False, 0), (True, 0), (True, 2)])
def test_empty_cell_is_its_steps(stop, recirc, cleans):
    want = _flat(E.ECMS_sub_electrolyte_recirculation_off) if stop else []
    want += _flat(E.ECMS_sub_normal_state)
    if recirc:
        want += _flat(
            E.ECMS_sub_drain_recirculation, tube_clear_time=8, liquid_drain_time=9
        )
        want += _flat(
            E.ECMS_sub_clean_cell_recirculation,
            cleaning_times=cleans,
            liquid_fill_time=5,
            tube_clear_time=8,
            liquid_drain_time=9,
            **FILL,
        )
    else:
        want += _flat(E.ECMS_sub_drain, liquid_drain_time=9)
    got = _flat(
        E.ECMS_sub_empty_cell,
        recirculation=recirc,
        stop_recirculation=stop,
        cleaning_times=cleans,
        tube_clear_time=8,
        liquid_drain_time=9,
        liquid_fill_time=5,
        **FILL,
    )
    assert got == want


def test_empty_cell_refuses_rinse_without_recirculation():
    with pytest.raises(ValueError):
        _flat(E.ECMS_sub_empty_cell, cleaning_times=1)


def test_step_experiments_stay_published():
    steps = {
        "ECMS_sub_electrolyte_fill_recirculationreservoir",
        "ECMS_sub_prevacuum_cell",
        "ECMS_sub_electrolyte_fill_cell",
        "ECMS_sub_electrolyte_fill_cell_recirculation",
        "ECMS_sub_headspace_purge_and_CO2baseline",
        "ECMS_sub_electrolyte_recirculation_on",
        "ECMS_sub_electrolyte_recirculation_off",
        "ECMS_sub_normal_state",
        "ECMS_sub_drain",
        "ECMS_sub_drain_recirculation",
        "ECMS_sub_clean_cell_recirculation",
    }
    assert steps <= set(E.EXPERIMENTS)
    assert {"ECMS_sub_fill", "ECMS_sub_empty_cell"} <= set(E.EXPERIMENTS)
