import pytest

from helao.core.drivers.helao_driver import DriverResponseType, DriverStatus
from helao.deploy.hte.servers.galil_io.galil_io_driver import Galil
from helao.deploy.hte.servers.galil_motion.tests.fake_gclib import Wire, install

CFG = {"galil_ip_str": "10.0.0.5", "dev_do": {"do1": 1}}


@pytest.mark.parametrize("api", ["1", "2"])
def test_io_connect_binds_channel(monkeypatch, api):
    wire = Wire()
    install(monkeypatch, api, wire)
    drv = Galil(config={**CFG, "gclib_api": api})
    resp = drv.connect()
    assert resp.response == DriverResponseType.success
    assert drv.galil_enabled is True
    assert drv.galilcmd == drv._channel.command
    assert drv.galilprgdownload == drv._channel.download_program
    assert wire.calls == [("open", "10.0.0.5")]


@pytest.mark.parametrize("api", ["1", "2"])
def test_io_disconnect_closes(monkeypatch, api):
    wire = Wire()
    install(monkeypatch, api, wire)
    drv = Galil(config={**CFG, "gclib_api": api})
    drv.connect()
    assert drv.disconnect().response == DriverResponseType.success
    assert wire.calls[-1] == ("close",)
    assert drv.galil_enabled is False


@pytest.mark.parametrize("api", ["1", "2"])
def test_io_disconnect_before_connect(monkeypatch, api):
    install(monkeypatch, api, Wire())
    drv = Galil(config={**CFG, "gclib_api": api})
    assert drv.disconnect().response == DriverResponseType.success


def test_io_connect_wrong_wrapper_reports_failure(monkeypatch, caplog):
    install(monkeypatch, "1", Wire())
    drv = Galil(config={**CFG, "gclib_api": "2", "connect_retry_wait_s": 0})
    resp = drv.connect()
    assert resp.response == DriverResponseType.failed
    assert resp.status == DriverStatus.error
    assert drv.galil_enabled is False


def test_io_no_ip_is_uninitialized(monkeypatch):
    install(monkeypatch, "2", Wire())
    drv = Galil(config={"gclib_api": "2"})
    resp = drv.connect()
    assert resp.status == DriverStatus.uninitialized


def test_io_unknown_api_fails_construction():
    with pytest.raises(ValueError, match="gclib_api"):
        Galil(config={**CFG, "gclib_api": "x"})


@pytest.mark.parametrize("api", ["1", "2"])
def test_io_connect_retries_a_failed_open(monkeypatch, api):
    """galil_io and galil_motion open one controller within a second of each
    other at launch; the loser's first attempt can fail."""
    wire = Wire()
    install(monkeypatch, api, wire)
    drv = Galil(config={**CFG, "gclib_api": api, "connect_retry_wait_s": 0})
    real_open, calls = drv._channel.open, []

    def _flaky_open(addr):
        calls.append(addr)
        if len(calls) == 1:
            raise RuntimeError("controller busy")
        return real_open(addr)

    monkeypatch.setattr(drv._channel, "open", _flaky_open)
    resp = drv.connect()
    assert resp.response == DriverResponseType.success
    assert drv.galil_enabled is True and len(calls) == 2
