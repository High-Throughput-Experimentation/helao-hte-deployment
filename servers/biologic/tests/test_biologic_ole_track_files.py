"""BiologicExec registers the vendor files a backend's ``cleanup`` reports.

Only the OLE backend moves files into the action directory (``.mps``, ``.mpr``,
``.mpt``); the syncer uploads the record's ``files`` list, so each must be
tracked. eclib/eclib2 responses carry no ``files`` and must track nothing.
"""

import asyncio
from types import SimpleNamespace

from helao.core.drivers.helao_driver import (
    DriverResponse,
    DriverResponseType,
    DriverStatus,
)
from helao.core.error import ErrorCodes
from helao.deploy.hte.servers.biologic.biologic_server import BiologicExec


class _Driver:
    def __init__(self, data):
        self.data = data

    def cleanup(self, channel):
        return DriverResponse(
            response=DriverResponseType.success, status=DriverStatus.ok, data=self.data
        )


def _exec(data):
    calls = []

    async def track_file(file_type, file_path, samples, action=None):
        calls.append((file_type, file_path, samples))

    ex = object.__new__(BiologicExec)
    ex.driver = _Driver(data)
    ex.channel = 0
    ex.data_buffer = {}
    ex.action_params = {}
    ex.active = SimpleNamespace(
        action=SimpleNamespace(
            action_name="run_CA", action_params={}, samples_in=["sample"]
        ),
        track_file=track_file,
    )
    return ex, calls


def test_olecom_files_are_tracked_once_each_with_a_per_suffix_type():
    files = ["/run/CA.mps", "/run/run_01_CA.mpr", "/run/run_01_CA.mpt"]
    ex, calls = _exec({"files": files})
    out = asyncio.run(ex._post_exec())
    assert calls == [
        ("biologic_mps", "/run/CA.mps", ["sample"]),
        ("biologic_mpr", "/run/run_01_CA.mpr", ["sample"]),
        ("biologic_mpt", "/run/run_01_CA.mpt", ["sample"]),
    ]
    assert out["error"] == ErrorCodes.none


def test_an_eclib_shaped_cleanup_tracks_nothing():
    ex, calls = _exec({})
    asyncio.run(ex._post_exec())
    assert calls == []
