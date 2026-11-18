"""A flow meter (no setpoint) on the same hub as controllers is still published.

An Alicat meter reports 5 status values; ``FlowMeter.get_status`` drops the
``setpoint`` key for it. ``get_device_status`` used to drop any dict without a
setpoint, so a meter (AutoGDE MFM on hub channel A) was never published and
logged "unexpected dict" on every poll.
"""

import helao.deploy.hte.servers.mfc.alicat_driver as alicat

CONFIG = {
    "devices": {
        "MFM": {"port": "COM3", "unit_id": "A"},
        "CO2": {"port": "COM3", "unit_id": "B"},
    }
}
BASE = {"pressure": 14.7, "temperature": 22.0, "volumetric_flow": 3.0}


class _Fc:
    def __init__(self, status):
        self.status = status

    def get_status(self):
        return dict(self.status)


def _driver():
    drv = alicat.AliCatMFC(config=CONFIG)
    drv.fcs = {
        "MFM": _Fc({**BASE, "mass_flow": 2.9, "gas": "CO2", "control_point": None}),
        "CO2": _Fc(
            {
                **BASE,
                "mass_flow": 3.0,
                "setpoint": 3.0,
                "gas": "CO2",
                "control_point": "mass flow",
            }
        ),
    }
    return drv


def test_meter_status_is_published_with_a_null_setpoint():
    status = _driver().get_device_status("MFM")
    assert status is not None
    assert status["mass_flow"] == 2.9 and status["setpoint"] is None


def test_controller_status_unchanged():
    status = _driver().get_device_status("CO2")
    assert status["setpoint"] == 3.0 and status["control_point"] == "mass flow"


def test_poller_publishes_meter_and_controller():
    poller = alicat.AliCatMFCPoller.__new__(alicat.AliCatMFCPoller)
    poller.driver = _driver()
    assert set(poller.get_data().data) == {"MFM", "CO2"}


def test_a_garbled_status_is_still_dropped():
    drv = _driver()
    drv.fcs["MFM"] = _Fc({"gas": "CO2"})
    assert drv.get_device_status("MFM") is None
