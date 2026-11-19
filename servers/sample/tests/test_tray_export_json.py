"""archive_tray_export_json on an undefined slot: warn, write no row, finish none.

The driver answers ``None`` for "nothing to export" (no tray, no slot, or a
null slot, ``archive_driver.py:549-559``). The endpoint wrapped that in
``DataModel``, whose ``data`` is ``dict[UUID, dict]``, so an operator no-op
became a 500 after ``ctx.begin`` and the re-queued action failed again on
resume. ``archive_tray_export_csv`` already writes nothing and finishes.
"""

import asyncio
import types
import uuid

from helao.core.error import ErrorCodes
from helao.helpers.premodels import Action
from helao.helpers.sample_positions import Positions
from helao.deploy.hte.servers.sample import sample_server
from helao.deploy.hte.servers.sample.archive_driver import Archive


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
    def __init__(self, action_params):
        self.action = Action(
            action_name="archive_tray_export_json", action_params=action_params
        )
        self.base = types.SimpleNamespace(dflt_file_conn_key=lambda: uuid.uuid4())
        self.enqueued = []

    def enqueue_data_nowait(self, datamodel, action=None):
        self.enqueued.append(datamodel)

    async def finish(self):
        return self.action


class _Ctx:
    def __init__(self, active):
        self.active = active

    async def begin(self, **kw):
        return self.active


def _app(monkeypatch, trays_dict):
    monkeypatch.setattr(sample_server, "ActionHost", _App)
    app = sample_server.makeApp("SAMPLE")
    stub = types.SimpleNamespace(
        positions=Positions(trays_dict=trays_dict), write_config=lambda: None
    )
    # the real driver method, bound to a stub that holds only the tray table
    stub.tray_export_json = types.MethodType(Archive.tray_export_json, stub)
    app.driver = stub
    return app


def test_undefined_slot_writes_no_row_and_finishes_none(monkeypatch):
    # tray 1 slot 1 is defined as null, exactly like adss3.yml tray 1 slots 1-3
    app = _app(monkeypatch, {1: {1: None}})
    active = _Active({"tray": 1, "slot": 1})
    result = asyncio.run(
        app.routes["archive_tray_export_json"](ctx=_Ctx(active), tray=1, slot=1)
    )
    assert active.enqueued == []
    assert active.action.error_code is ErrorCodes.none
    assert result["error_code"] == "none"
