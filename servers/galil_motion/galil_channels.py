"""``gclib_api`` server param -> Galil command channel (wrapper 1.0 or 2.x).

Both wrappers install as ``import gclib``, so one env holds one of them; the
configured value must match the installed wrapper (the channel's ``open``
says so if it does not). Absent -> "1", today's behaviour.

``connect_with_retry`` retries a driver's connect sequence: on stations where
``galil_io`` and ``galil_motion`` share one controller, both open it within a
second of each other at launch, and the second one's first query can come
back empty (hte-uvis-04, 2026-11-12: MOTOR's ``MG _MOA`` returned ``''``
while IO's open was still in progress; a restart of MOTOR alone connected).
"""

import time
from typing import Callable, TypeVar

from helao.helpers import helao_logging as logging

from helao.deploy.hte.servers.galil_motion.galil_command_channel import (
    GclibCommandChannel,
)
from helao.deploy.hte.servers.galil_motion.galil_command_channel2 import (
    Gclib2CommandChannel,
)
from helao.deploy.hte.servers.galil_motion.galil_command_channel_port import (
    GalilCommandChannel,
)

__all__ = [
    "CHANNELS",
    "DEFAULT_CONNECT_ATTEMPTS",
    "DEFAULT_CONNECT_RETRY_WAIT_S",
    "DEFAULT_GCLIB_API",
    "connect_with_retry",
    "make_channel",
]

LOGGER = logging.make_logger(__file__) if logging.LOGGER is None else logging.LOGGER
T = TypeVar("T")

CHANNELS = {"1": GclibCommandChannel, "2": Gclib2CommandChannel}
DEFAULT_GCLIB_API = "1"
#: Server params ``connect_attempts`` / ``connect_retry_wait_s`` override these.
DEFAULT_CONNECT_ATTEMPTS = 5
DEFAULT_CONNECT_RETRY_WAIT_S = 2.0


def make_channel(config: dict) -> GalilCommandChannel:
    raw = config.get("gclib_api", DEFAULT_GCLIB_API)
    name = str(raw) if type(raw) is int else raw
    if not isinstance(name, str) or name not in CHANNELS:
        raise ValueError(
            f"unknown gclib_api {raw!r}; expected one of "
            + ", ".join(repr(k) for k in CHANNELS)
        )
    return CHANNELS[name]()


def connect_with_retry(
    attempt: Callable[[], T],
    channel: GalilCommandChannel,
    config: dict,
    label: str,
) -> T:
    """Run *attempt* (open + init queries) up to ``connect_attempts`` times.

    Between attempts the half-open channel is closed and the wait grows
    linearly (``connect_retry_wait_s`` x attempt number: 2, 4, 6, 8 s by
    default), so two servers opening one controller at once fall out of step.
    The last attempt's exception propagates to the driver's own handler.
    """
    attempts = max(1, int(config.get("connect_attempts", DEFAULT_CONNECT_ATTEMPTS)))
    wait_s = float(config.get("connect_retry_wait_s", DEFAULT_CONNECT_RETRY_WAIT_S))
    for n in range(1, attempts + 1):
        try:
            result = attempt()
            if n > 1:
                LOGGER.info(f"{label} connected on attempt {n}/{attempts}")
            return result
        except Exception:
            if n == attempts:
                raise
            LOGGER.warning(
                f"{label} connect attempt {n}/{attempts} failed; "
                f"retrying in {wait_s * n:g} s",
                exc_info=True,
            )
            try:
                channel.close()
            except Exception:
                LOGGER.debug("closing the half-open channel failed", exc_info=True)
            time.sleep(wait_s * n)
    raise AssertionError("unreachable")
