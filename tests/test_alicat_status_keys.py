"""``FlowMeter.get_status`` must not change ``status_keys`` between replies.

A controller reply's field count can vary (a truncated read, a totalizer reply,
an unlisted status flag). Each reply is keyed on its own; one odd reply must
not re-key every later one.
"""

import helao.deploy.hte.servers.mfc.alicat_driver as alicat

BASE_KEYS = [
    "pressure",
    "temperature",
    "volumetric_flow",
    "mass_flow",
    "setpoint",
    "gas",
]
# Fields after the unit id, in order: pressure, temperature, volumetric flow,
# mass flow, setpoint, gas (the FlowMeter.__init__ status_keys order).
R6 = "B +014.70 +022.00 +003.00 +002.90 +003.00 CO2"
R5 = "B +014.70 +022.00 +003.00 +002.90 CO2"
R7 = "B +014.70 +022.00 +003.00 +002.90 +003.00 +010.00 CO2"
R2 = "B +014.70 +003.00"


def _fc(replies):
    fc = object.__new__(alicat.FlowController)
    fc.address, fc.port, fc.open = "B", "X", True
    fc.control_point = "mass flow"
    fc.status_keys = list(BASE_KEYS)
    it = iter(replies)
    fc._write_and_read = lambda command, retries=2: next(it)
    return fc


def test_short_reply_does_not_drop_setpoint_from_later_replies():
    fc = _fc([R6, R5, R6])
    fc.get_status(), fc.get_status()
    third = fc.get_status()
    assert third["setpoint"] == 3.0  # 5th field of R6
    assert third["gas"] == "CO2"
    assert fc.status_keys == BASE_KEYS


def test_long_reply_does_not_rekey_later_replies():
    fc = _fc([R6, R7, R6])
    fc.get_status(), fc.get_status()
    third = fc.get_status()
    assert third["gas"] == "CO2"
    assert "total flow" not in third
    assert fc.status_keys == BASE_KEYS


def test_two_field_reply_does_not_rekey_later_replies():
    # Review Focus RF1: the len(values) == 2 branch inserts "setpoint" at index 1.
    fc = _fc([R2, R6])
    first = fc.get_status()
    assert first["pressure"] == 14.7 and first["setpoint"] == 3.0
    second = fc.get_status()
    assert second["setpoint"] == 3.0 and second["gas"] == "CO2"
    assert fc.status_keys == BASE_KEYS
