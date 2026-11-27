"""Sequences that read state nothing in them set.

* ECHEUVIS_CA_led never calibrates, so its CA spectra must use the operator's
  spec_int_time_ms, not a calibrated_int_time_ms global left by an earlier run.
* HISPEC_EIS_only must not open with a bare HISPEC_sub_startup, which loads the
  experiment's default solid (plate 4534, sample 1).
"""

from helao.deploy.hte.experiments import ECHEUVIS_exp
from helao.deploy.hte.sequences import ECHEUVIS_seq, HISPEC_seq
from helao.helpers.premodels import Experiment


def _spec_actions(**params):
    fn = ECHEUVIS_exp.ECHEUVIS_sub_CA_led
    exp = Experiment(experiment_name=fn.__name__, experiment_params={})
    return [a for a in fn(exp, **params) if a.action_name == "acquire_spec_extrig"]


def test_ca_led_default_reads_calibrated_global():
    spec = _spec_actions()
    assert spec
    for a in spec:
        assert a.from_global_act_params.get("calibrated_int_time_ms") == "int_time"
        assert "int_time" not in a.action_params


def test_ca_led_uncalibrated_uses_operator_int_time():
    spec = _spec_actions(use_calibrated_int_time=False, spec_int_time_ms=42)
    assert spec
    for a in spec:
        assert "calibrated_int_time_ms" not in a.from_global_act_params
        assert a.action_params["int_time"] == 42


def test_ca_led_sequence_does_not_read_calibration():
    exps = ECHEUVIS_seq.ECHEUVIS_CA_led()
    names = [e.experiment_name for e in exps]
    assert not any(
        e.experiment_params.get("calibrate_intensity") for e in exps
    ), "sequence calibrates now: use_calibrated_int_time=False may be wrong"
    ca = [e for e in exps if e.experiment_name == "ECHEUVIS_sub_CA_led"]
    assert ca and "ECHEUVIS_sub_CA_led" in names
    assert all(e.experiment_params["use_calibrated_int_time"] is False for e in ca)


def test_eis_only_loads_only_requested_samples():
    exps = HISPEC_seq.HISPEC_EIS_only(plate_id=7, plate_sample_no_list=[3, 5])
    names = [e.experiment_name for e in exps]
    assert "HISPEC_sub_startup" not in names
    loads = [
        (e.experiment_params["solid_plate_id"], e.experiment_params["solid_sample_no"])
        for e in exps
        if "solid_sample_no" in e.experiment_params
    ]
    assert loads == [(7, 3), (7, 5)]
