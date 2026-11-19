"""get_loaded_positions must leave a JSON-serializable -act record.

``_tray_pos`` used ``(tray, slot, vial)`` tuple keys. JSON has no tuple keys,
and ``clean_dict`` (what writes ``-act.json``, meta_writer.py:111) raised for
any loaded vial, so the action could not finish.
"""

import asyncio
import types

from helao.core.models.sample import LiquidSample
from helao.helpers.premodels import Action
from helao.helpers.sample_positions import VT54, Positions
from helao.deploy.hte.servers.sample import sample_server

LABEL = "test__liquid__1"


class _App:
    """Captures the routes ``makeApp`` registers; stands in for ActionHost."""

    def __init__(self, *args, **kwargs):
        self.server_params = {}
        self.routes = {}
        self.driver = None

    def action(self, **kw):
        def deco(fn):
            self.routes[fn.__name__] = fn
            return fn

        return deco

    def post(self, path, **kw):
        return lambda fn: fn


class _Active:
    def __init__(self):
        self.action = Action(action_name="get_loaded_positions", action_params={})

    async def finish(self):
        return self.action


class _Ctx:
    def __init__(self, active):
        self.active = active

    async def begin(self, **kw):
        return self.active


def test_loaded_vial_serializes_with_string_key(monkeypatch):
    monkeypatch.setattr(sample_server, "ActionHost", _App)
    app = sample_server.makeApp("SAMPLE")
    vt = VT54()
    vt.vials[0] = True  # tray 1, slot 1, vial 1 loaded
    vt.samples[0] = LiquidSample(global_label=LABEL)
    app.driver = types.SimpleNamespace(positions=Positions(trays_dict={1: {1: vt}}))
    active = _Active()
    asyncio.run(app.routes["get_positions"](ctx=_Ctx(active)))
    clean = active.action.clean_dict()  # what the -act.json writer serializes
    assert clean["action_params"]["_tray_pos"] == {"1,1,1": LABEL}
