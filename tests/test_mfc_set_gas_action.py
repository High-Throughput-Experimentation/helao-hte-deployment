"""MFC set_gas is an orchestrator action (/<server>/set_gas); the private
/set_gas the panel uses stays as it was. No Alicat hardware: the driver is
stubbed at set_gas and the app at the two decorators mfc_dyn_endpoints uses."""

import asyncio
from enum import StrEnum
from types import SimpleNamespace

from helao.deploy.hte.servers.mfc.mfc_server import mfc_dyn_endpoints


class _Driver:
    dev_mfcs = StrEnum("dev_mfcs", {"CO2": "CO2", "N2O2": "N2O2"})

    def __init__(self):
        self.calls = []

    async def set_gas(self, device_name, gas):
        self.calls.append((device_name, gas))


class _App:
    """Records what mfc_dyn_endpoints registers: path -> (tags, handler)."""

    def __init__(self):
        self.driver = _Driver()
        self.server = SimpleNamespace(server_name="MFC")
        self.server_params = {"devices": {"CO2": {}, "N2O2": {}}}
        self.helao_cfg = {"servers": {}}
        self.routes = {}

    def post(self, path, tags=None, **kwargs):
        def register(fn):
            self.routes[path] = (tags or [], fn)
            return fn

        return register

    def action(self, **kwargs):
        """Like ActionHost.action: the path is derived from the handler name."""
        return lambda fn: self.post(
            f"/{self.server.server_name}/{fn.__name__}", tags=["action"]
        )(fn)


class _Ctx:
    def __init__(self, params):
        self.abbr = None
        self.active = SimpleNamespace(
            action=SimpleNamespace(action_params=params), finish=self._finish
        )

    async def begin(self, action_abbr=None):
        self.abbr = action_abbr
        return self.active

    async def _finish(self):
        return SimpleNamespace(as_dict=lambda: {"finished": True})


def _app():
    app = _App()
    asyncio.run(mfc_dyn_endpoints(app))
    return app


def test_set_gas_is_an_action_and_the_private_post_stays():
    app = _app()
    assert app.routes["/MFC/set_gas"][0] == ["action"]
    assert app.routes["/set_gas"][0] == ["private"]


def test_the_set_gas_action_selects_the_gas_on_the_named_device():
    app = _app()
    ctx = _Ctx({"device_name": "N2O2", "gas": "O2"})
    out = asyncio.run(app.routes["/MFC/set_gas"][1](ctx))
    assert app.driver.calls == [("N2O2", "O2")]
    assert ctx.abbr == "set_gas"
    assert out == {"finished": True}


def test_the_private_set_gas_still_calls_the_driver():
    app = _app()
    asyncio.run(app.routes["/set_gas"][1](device_name="CO2", gas="N2"))
    assert app.driver.calls == [("CO2", "N2")]
