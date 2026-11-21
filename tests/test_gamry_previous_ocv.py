"""``previous_ocv__V`` on run_CV: the ecms3 ECSA reference inside one
experiment. The orchestrator copies a preceding OCV action's
``Ewe_V__mean_final`` into it; ``GamryExec._pre_exec`` adds it to every
potential the signal is built from, as ``versus_OCV`` does with a fresh OCV,
but without measuring. ``versus_previous_OCV`` must say so explicitly."""

import asyncio

import pytest

from helao.deploy.hte.servers.gamry import gamry_server2 as gs
from helao.deploy.hte.servers.gamry.technique import TECH_CA, TECH_CV, TECH_LSV
from helao.deploy.hte.tests.test_gamry_versus_ocv import CV_PARAMS, FakeDriver, _exec


def test_previous_ocv_shifts_every_potential_without_measuring(monkeypatch):
    params = {**CV_PARAMS, "versus_previous_OCV": True, "previous_ocv__V": 0.31}
    result, (_, signal_params, action_params), calls = _exec(
        TECH_CV, params, monkeypatch
    )
    assert result["error"] == gs.ErrorCodes.none
    assert calls == []  # no OCV measured
    assert signal_params["Vinit__V"] == pytest.approx(0.31)
    assert signal_params["Vapex1__V"] == pytest.approx(0.81)
    assert signal_params["Vapex2__V"] == pytest.approx(0.11)
    assert signal_params["Vfinal__V"] == pytest.approx(0.31)
    assert signal_params["AcqInterval__s"] == 0.02  # not a potential
    assert action_params["Vapex1__V"] == 0.5  # the request is recorded as sent


def test_flag_false_and_none_leaves_setup_args_identical_to_base(monkeypatch):
    _, base, _ = _exec(TECH_CV, dict(CV_PARAMS), monkeypatch)
    params = {**CV_PARAMS, "versus_previous_OCV": False, "previous_ocv__V": None}
    result, args, calls = _exec(TECH_CV, params, monkeypatch)
    assert result["error"] == gs.ErrorCodes.none and calls == []
    assert args[1] == base[1]


def _refused(monkeypatch, technique, extra):
    measured = []

    async def fake_ocv(active, driver, params):
        measured.append(params)
        return 0.25

    monkeypatch.setattr(gs, "measure_init_ocv", fake_ocv)
    ex = gs.GamryExec.__new__(gs.GamryExec)
    driver = FakeDriver()
    ex.active, ex.technique = None, technique
    ex.driver = driver  # type: ignore  # duck-typed GamryDriver
    ex.action_params = {**CV_PARAMS, **extra}
    ex.signal_params, ex.dtaq_params, ex.ierange = dict(CV_PARAMS), {}, "auto"
    assert asyncio.run(ex._pre_exec())["error"] == gs.ErrorCodes.setup
    assert driver.setup_args is None
    assert measured == []


@pytest.mark.parametrize(
    "extra",
    [
        {"versus_previous_OCV": True, "previous_ocv__V": 0.3, "versus_OCV": True},
        {"versus_previous_OCV": True},
        {"versus_previous_OCV": True, "previous_ocv__V": None},
        {"versus_previous_OCV": True, "previous_ocv__V": float("nan")},
        {"versus_previous_OCV": True, "previous_ocv__V": float("inf")},
        {"versus_previous_OCV": True, "previous_ocv__V": "0.3"},
        {"versus_previous_OCV": True, "previous_ocv__V": True},
        {"versus_previous_OCV": False, "previous_ocv__V": 0.3},
        {"previous_ocv__V": 0.3},
        {"versus_previous_OCV": False, "previous_ocv__V": float("nan")},
    ],
    ids=[
        "with-versus_OCV",
        "flag-absent-value",
        "flag-none",
        "nan",
        "inf",
        "str",
        "bool",
        "flag-false-value",
        "flag-default-value",
        "flag-false-nan",
    ],
)
def test_bad_previous_ocv_combinations_are_setup(monkeypatch, extra):
    _refused(monkeypatch, TECH_CV, extra)


@pytest.mark.parametrize("technique", [TECH_LSV, TECH_CA], ids=["LSV", "CA"])
@pytest.mark.parametrize(
    "extra",
    [
        {"previous_ocv__V": 0.3},
        {"versus_previous_OCV": True},
        {"versus_previous_OCV": True, "previous_ocv__V": 0.3},
    ],
    ids=["value", "flag", "both"],
)
def test_only_cv_takes_previous_ocv(monkeypatch, technique, extra):
    _refused(monkeypatch, technique, extra)
