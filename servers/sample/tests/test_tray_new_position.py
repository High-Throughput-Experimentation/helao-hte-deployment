"""Archive.tray_new_position must block only the vial it returns.

The search set ``blocked`` on every new best-fit candidate inside the loop,
so a superseded larger vial stayed blocked (lost to later calls until a
reset or unload). The method touches only ``self.positions``.
"""

import asyncio
import types

from helao.helpers.sample_positions import VT15, VT54, Positions
from helao.deploy.hte.servers.sample.archive_driver import Archive


def test_only_the_returned_vial_is_blocked():
    # VT15 (10 mL, 15 vials) in tray 1 qualifies first for 1 mL; VT54 (2 mL,
    # 54 vials) in tray 2 is smaller and wins. Only the winner is blocked.
    stub = types.SimpleNamespace(
        positions=Positions(trays_dict={1: {1: VT15()}, 2: {1: VT54()}})
    )
    got = asyncio.run(Archive.tray_new_position(stub, req_vol=1.0))
    assert got == {"tray": 2, "slot": 1, "vial": 1}
    assert stub.positions.trays_dict[1][1].blocked == [False] * 15
    assert stub.positions.trays_dict[2][1].blocked[0] is True
    assert stub.positions.trays_dict[2][1].blocked[1:] == [False] * 53
