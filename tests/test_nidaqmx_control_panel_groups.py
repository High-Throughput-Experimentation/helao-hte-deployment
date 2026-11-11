"""The nidaqmx control panel resolves through /control's resolver and lists the pump and gas-valve groups."""

from helao.ui.shared.discovery import resolve_panel_module


def test_nidaqmx_control_panel_lists_pump_and_gasvalve_groups():
    module = resolve_panel_module("nidaqmx_control")
    groups = [getattr(g, "name", g) for g in module.DO_GROUPS]
    assert "dev_pump" in groups and "dev_gasvalve" in groups
