"""WE_versus="ocv" on the ANEC/ECMS CA/CV/LSV experiments.

"ocv" leaves potentials untouched and asks the Gamry endpoint to measure OCV
first (versus_OCV=True + OCV_duration__s). "ref"/"rhe" plans carry neither key.
Exception: ECMS_sub_CV measures nothing; it offsets by the supplied previous_ocv__V.
"""

import inspect
import math

import pytest

from helao.core.models.echem_params import ref_offset
from helao.deploy.hte.experiments import ANEC_exp, ECMS_exp
from helao.deploy.hte.sequences import ANEC_seq, ECMS_seq
from helao.helpers.premodels import Experiment

POT = {
    "WE_potential__V": -0.7,
    "WE_potential_init__V": -0.1,
    "WE_potential_apex1__V": -0.9,
    "WE_potential_apex2__V": -0.4,
    "WE_potential_final__V": -0.3,
}
VKEY = {
    "WE_potential__V": "Vval__V",
    "WE_potential_init__V": "Vinit__V",
    "WE_potential_apex1__V": "Vapex1__V",
    "WE_potential_apex2__V": "Vapex2__V",
    "WE_potential_final__V": "Vfinal__V",
}
CASES = [
    (ANEC_exp.ANEC_sub_CA, "run_CA"),
    (ANEC_exp.ANEC_sub_photo_CA, "run_CA"),
    (ANEC_exp.ANEC_sub_CV, "run_CV"),
    (ANEC_exp.ANEC_sub_photo_CV, "run_CV"),
    (ANEC_exp.ANEC_sub_photo_LSV, "run_LSV"),
    (ECMS_exp.ECMS_sub_CA, "run_CA"),
    (ECMS_exp.ECMS_sub_CA_CO2flow, "run_CA"),
]


def _pstat_params(fn, endpoint, **kw):
    import inspect

    accepted = inspect.signature(fn).parameters
    kw = {k: v for k, v in {**POT, **kw}.items() if k in accepted}
    exp = Experiment(experiment_name=fn.__name__, experiment_params={})
    acts = fn(exp, **kw)
    (act,) = [a for a in acts if a.action_name == endpoint]
    return kw, act.action_params


@pytest.mark.parametrize("fn,endpoint", CASES, ids=[c[0].__name__ for c in CASES])
def test_ocv_sets_versus_ocv_and_keeps_potentials(fn, endpoint):
    kw, params = _pstat_params(fn, endpoint, WE_versus="ocv", OCV_duration__s=7.0)
    assert params["versus_OCV"] is True
    assert params["OCV_duration__s"] == 7.0
    for name, key in VKEY.items():
        if name in kw and key in params:
            assert params[key] == kw[name]


@pytest.mark.parametrize("fn,endpoint", CASES, ids=[c[0].__name__ for c in CASES])
@pytest.mark.parametrize("versus", ["ref", "rhe"])
def test_ref_rhe_have_no_ocv_keys(fn, endpoint, versus):
    _, params = _pstat_params(fn, endpoint, WE_versus=versus)
    assert "versus_OCV" not in params and "OCV_duration__s" not in params


def test_ref_rhe_exact_params():
    kw = {"WE_potential__V": -0.7, "ref_offset__V": 0.1, "pH": 7.0}
    _, ref = _pstat_params(ANEC_exp.ANEC_sub_CA, "run_CA", WE_versus="ref", **kw)
    _, rhe = _pstat_params(ANEC_exp.ANEC_sub_CA, "run_CA", WE_versus="rhe", **kw)
    base = {"Tval__s": 0.1, "AcqInterval__s": 0.01, "IErange": "auto"}
    assert ref == {"Vval__V": pytest.approx(-0.8), **base}
    assert rhe == {
        "Vval__V": pytest.approx(-0.8 - 0.059 * 7.0 - ref_offset("leakless")),
        **base,
    }


def test_unknown_versus_raises_value_error_naming_values():
    with pytest.raises(ValueError, match="ref, rhe, ocv"):
        _pstat_params(ANEC_exp.ANEC_sub_CA, "run_CA", WE_versus="bogus")


def test_ecms_initiation_ecsa_expands_at_defaults():
    for e in ECMS_seq.ECMS_initiation_ECSA():
        fn = getattr(ECMS_exp, e.experiment_name)
        params = dict(e.experiment_params)
        # what the orchestrator's from_global_exp_params fold-in supplies
        for key, dest in (e.from_global_exp_params or {}).items():
            params[dest] = 0.1
        fn(
            Experiment(experiment_name=e.experiment_name, experiment_params={}),
            **params,
        )


def test_ecms_series_ca_expands_with_ocv():
    for e in ECMS_seq.ECMS_series_CA(WE_versus="ocv"):
        fn = getattr(ECMS_exp, e.experiment_name)
        fn(
            Experiment(experiment_name=e.experiment_name, experiment_params={}),
            **e.experiment_params,
        )


def _expand_pstat(seq_fn, endpoint, **kw):
    """PSTAT action params of every ``endpoint`` action the sequence plans."""
    out = []
    for e in seq_fn(**kw):
        fn = getattr(
            ANEC_exp if e.experiment_name.startswith("ANEC") else ECMS_exp,
            e.experiment_name,
        )
        exp = Experiment(experiment_name=e.experiment_name, experiment_params={})
        out += [
            a.action_params
            for a in fn(exp, **e.experiment_params)
            if a.action_name == endpoint
        ]
    return out


def test_ecms_cv_ocv_offsets_by_previous_ocv_and_measures_nothing():
    """ECMS_sub_CV no longer measures OCV; "ocv" adds the supplied previous_ocv__V."""
    kw, params = _pstat_params(
        ECMS_exp.ECMS_sub_CV, "run_CV", WE_versus="ocv", previous_ocv__V=0.25
    )
    for name, key in VKEY.items():
        if name in kw and key in params:
            assert params[key] == pytest.approx(kw[name] + 0.25)
    assert "versus_OCV" not in params and "OCV_duration__s" not in params


def test_ecms_cv_ocv_refuses_without_previous_ocv():
    """A CV must never run on a default OCV: "ocv" with no previous_ocv__V raises."""
    with pytest.raises(ValueError, match="previous_ocv__V"):
        _pstat_params(ECMS_exp.ECMS_sub_CV, "run_CV", WE_versus="ocv")


@pytest.mark.parametrize("bad", [math.nan, math.inf, "unset", True])
def test_ecms_cv_ocv_refuses_unusable_previous_ocv(bad):
    """The "unset" sentinel left by ECMS_sub_OCV (OCV never published) must not run."""
    with pytest.raises(ValueError, match="previous_ocv__V"):
        _pstat_params(
            ECMS_exp.ECMS_sub_CV, "run_CV", WE_versus="ocv", previous_ocv__V=bad
        )
    _pstat_params(ECMS_exp.ECMS_sub_CV, "run_CV", WE_versus="ref", previous_ocv__V=bad)


def test_ecms_ocv_resets_global_to_unset_before_measuring():
    """A stale Ewe_V__mean_final from an earlier sequence is overwritten first."""
    acts = ECMS_exp.ECMS_sub_OCV(Experiment(experiment_name="x", experiment_params={}))
    names = [a.action_name for a in acts]
    assert names.index("add_global_param") < names.index("run_OCV")
    (g,) = [a for a in acts if a.action_name == "add_global_param"]
    assert g.action_params == {
        "param_name": "Ewe_V__mean_final",
        "param_value": "unset",
    }


def test_ecms_cv_ref_ignores_previous_ocv():
    kw, ref = _pstat_params(
        ECMS_exp.ECMS_sub_CV, "run_CV", WE_versus="ref", previous_ocv__V=0.25
    )
    assert ref["Vinit__V"] == kw["WE_potential_init__V"]
    assert "versus_OCV" not in ref and "OCV_duration__s" not in ref


@pytest.mark.parametrize(
    "seq_fn,endpoint",
    [
        (ECMS_seq.ECMS_series_CA, "run_CA"),
        (ANEC_seq.ANEC_series_CA, "run_CA"),
        (ANEC_seq.ANEC_repeat_CV, "run_CV"),
    ],
    ids=lambda v: getattr(v, "__name__", v),
)
def test_sequence_forwards_ocv_duration_to_pstat(seq_fn, endpoint):
    params = _expand_pstat(seq_fn, endpoint, WE_versus="ocv", OCV_duration__s=7.0)
    assert params
    for p in params:
        assert p["versus_OCV"] is True and p["OCV_duration__s"] == 7.0


CV_SEQS = [
    ECMS_seq.ECMS_repeat_CV,
    ECMS_seq.ECMS_repeat_CV_recirculation,
    ECMS_seq.ECMS_repeat_CV_recirculation_mixedreactant,
    ECMS_seq.ECMS_CV_recirculation_mixedreactant,
]


@pytest.mark.parametrize("seq_fn", CV_SEQS, ids=lambda f: f.__name__)
def test_cv_sequences_ocv_runs_one_ocv_and_wires_previous_ocv(seq_fn):
    kw = (
        {"num_repeats": 2}
        if "num_repeats" in inspect.signature(seq_fn).parameters
        else {}
    )
    planned = list(
        seq_fn(
            WE_versus="ocv",
            OCV_duration__s=7.0,
            OCV_acquisition_period__s=0.3,
            **kw,
        )
    )
    (ocv,) = [e for e in planned if e.experiment_name == "ECMS_sub_OCV"]
    assert ocv.experiment_params == {
        "OCV_duration__s": 7.0,
        "OCV_acquisition_period__s": 0.3,
    }
    names = [e.experiment_name for e in planned]
    assert names.count("ECMS_sub_OCV") == 1
    first_cv = names.index("ECMS_sub_CV")
    assert names.index("ECMS_sub_OCV") < first_cv
    cvs = [e for e in planned if e.experiment_name == "ECMS_sub_CV"]
    assert len(cvs) >= 2
    for e in cvs:
        assert e.from_global_exp_params == {"Ewe_V__mean_final": "previous_ocv__V"}


@pytest.mark.parametrize("seq_fn", CV_SEQS, ids=lambda f: f.__name__)
def test_cv_sequences_ref_runs_no_ocv(seq_fn):
    planned = list(seq_fn(WE_versus="ref"))
    assert "ECMS_sub_OCV" not in [e.experiment_name for e in planned]
    for e in planned:
        if e.experiment_name == "ECMS_sub_CV":
            assert not e.from_global_exp_params


def test_ecsa_ocv_mode_measures_ocv_even_if_versus_ocv_false():
    """WE_versus="ocv" must never run CVs on a stale global OCV."""
    planned = list(ECMS_seq.ECMS_initiation_ECSA(WE_versus="ocv", versus_OCV=False))
    names = [e.experiment_name for e in planned]
    assert names.count("ECMS_sub_OCV") == 1
    assert names.index("ECMS_sub_OCV") < names.index("ECMS_sub_CV")
