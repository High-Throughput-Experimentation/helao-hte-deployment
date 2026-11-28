"""ADSS steps folded into the experiment that always followed them.

PAL_load_gas(set_valve, unload_previous), load(reference_position_name) and
clean_cell(move_first) must emit exactly the old step experiments' actions, in
order, so the fold changes record grouping only.
"""

import pytest

from helao.deploy.hte.experiments import ADSS_exp as A
from helao.helpers.premodels import Experiment

MASK = ("uuid", "timestamp", "time", "experiment", "action_order")


def _flat(fn, **kw):
    exp = Experiment(experiment_name=fn.__name__, experiment_params={})
    out = []
    for a in fn(exp, **kw):
        d = a.model_dump(mode="json")
        out.append({k: v for k, v in d.items() if not any(m in k for m in MASK)})
    return out


@pytest.mark.parametrize("gas,no", [("N2", 1), ("O2", 2)])
@pytest.mark.parametrize("valve", [False, True])
@pytest.mark.parametrize("unload", [False, True])
def test_load_gas_is_valve_unload_load(gas, no, valve, unload):
    want = _flat(A.ADSS_sub_gasvalve_N2flow, open=gas == "N2") if valve else []
    want += _flat(A.ADSS_sub_unload_gas_only) if unload else []
    want += _flat(A.ADSS_sub_PAL_load_gas, bubbled_gas=gas, reservoir_gas_sample_no=no)
    got = _flat(
        A.ADSS_sub_PAL_load_gas,
        bubbled_gas=gas,
        reservoir_gas_sample_no=no,
        set_valve=valve,
        unload_previous=unload,
    )
    assert got == want


def test_load_moves_to_reference_first():
    kw = dict(solid_plate_id=7, solid_sample_no=1, liquid_sample_no=3)
    want = _flat(A.ADSS_sub_move_to_ref_measurement, reference_position_name="r2")
    want += _flat(A.ADSS_sub_load, **kw)
    assert _flat(A.ADSS_sub_load, reference_position_name="r2", **kw) == want


def test_clean_cell_moves_first():
    kw = dict(Clean_volume_ul=12000, DrainWait_s=5, ReturnLineWait_s=6)
    want = _flat(A.ADSS_sub_move_to_clean_cell) + _flat(A.ADSS_sub_clean_cell, **kw)
    assert _flat(A.ADSS_sub_clean_cell, move_first=True, **kw) == want
