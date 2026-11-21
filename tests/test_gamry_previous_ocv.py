"""``previous_ocv__V`` on run_CV: the ecms3 ECSA reference inside one
experiment. The orchestrator copies a preceding OCV action's
``Ewe_V__mean_final`` into it; ``GamryExec._pre_exec`` adds it to every
potential the signal is built from, as ``versus_OCV`` does with a fresh OCV,
but without measuring."""

import asyncio

import pytest

from helao.deploy.hte.servers.gamry import gamry_server2 as gs
from helao.deploy.hte.servers.gamry.technique import TECH_CV
from helao.deploy.hte.tests.test_gamry_versus_ocv import CV_PARAMS, FakeDriver, _exec


def test_previous_ocv_shifts_every_potential_without_measuring(monkeypatch):
    params = {**CV_PARAMS, "previous_ocv__V": 0.31}
    result, (_, signal_params, action_params), calls = _exec(
        TECH_CV, params, monkeypatch
    )
    assert result["error"] == gs.ErrorCodes.none
    assert calls == []  # no OCV measured
    assert signal_params["Vinit__V"] == pytest.approx(0.31)
    assert signal_params["Vapex1__V"] == pytest.approx(0.81)
    assert signal_params["Vapex2__V"] == pytest.approx(0.11)
    assert signal_params["AcqInterval__s"] == 0.02  # not a potential
    assert action_params["Vapex1__V"] == 0.5  # the request is recorded as sent


def test_previous_ocv_none_changes_nothing(monkeypatch):
    params = {**CV_PARAMS, "previous_ocv__V": None}
    result, (_, signal_params, _), calls = _exec(TECH_CV, params, monkeypatch)
    assert result["error"] == gs.ErrorCodes.none
    assert calls == [] and signal_params["Vapex1__V"] == 0.5


@pytest.mark.parametrize(
    "extra",
    [
        {"previous_ocv__V": 0.3, "versus_OCV": True},
        {"previous_ocv__V": float("nan")},
        {"previous_ocv__V": float("inf")},
        {"previous_ocv__V": "0.3"},
        {"previous_ocv__V": True},
    ],
    ids=["with-versus_OCV", "nan", "inf", "str", "bool"],
)
def test_previous_ocv_with_versus_ocv_or_non_finite_is_setup(monkeypatch, extra):
    measured = []

    async def fake_ocv(active, driver, params):
        measured.append(params)
        return 0.25

    monkeypatch.setattr(gs, "measure_init_ocv", fake_ocv)
    ex = gs.GamryExec.__new__(gs.GamryExec)
    driver = FakeDriver()
    ex.active, ex.technique = None, TECH_CV
    ex.driver = driver  # type: ignore  # duck-typed GamryDriver
    ex.action_params = {**CV_PARAMS, **extra}
    ex.signal_params, ex.dtaq_params, ex.ierange = dict(CV_PARAMS), {}, "auto"
    assert asyncio.run(ex._pre_exec())["error"] == gs.ErrorCodes.setup
    assert driver.setup_args is None
    assert measured == []
