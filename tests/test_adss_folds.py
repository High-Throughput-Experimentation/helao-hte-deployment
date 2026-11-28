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


def test_ca_photo_is_ca_illuminated():
    kw = dict(CA_potential=0.4, CA_duration_sec=30, led_wavelength="450")
    assert "ADSS_sub_CA_photo" in A.EXPERIMENTS
    lit = _flat(A.ADSS_sub_CA, illumination=True, **kw)
    assert _flat(A.ADSS_sub_CA_photo, **kw) == lit
    assert lit != _flat(A.ADSS_sub_CA, **kw)
    techniques = {a.get("technique_name") for a in lit} - {None}
    assert "CA_photo" in techniques


@pytest.mark.parametrize("led", [False, True])
@pytest.mark.parametrize("aliquot_tf", [False, True])
def test_ca_cell_ocvs_follow_aliquot_tf(led, aliquot_tf):
    from helao.deploy.hte.sequences import ADSS_seq

    exps = ADSS_seq.ADSS_CA_cell_1potential(led_illumination=led, aliquot_tf=aliquot_tf)
    ocvs = [e for e in exps if e.experiment_name.startswith("ADSS_sub_OCV")]
    assert len(ocvs) == 2
    assert all(e.experiment_params["aliquot_insitu"] is aliquot_tf for e in ocvs)
