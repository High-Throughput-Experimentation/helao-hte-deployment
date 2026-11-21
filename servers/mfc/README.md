# mfc

Action server for Alicat mass flow controllers on serial ports (flow, pressure, gas, valve hold, tare, and CO2 concentration holding).

## Vendor software

No vendor software beyond the env files. The Alicat serial protocol is implemented in-tree (`alicat_driver.py`, `FlowController`) on top of `pyserial`, which is in `environment.yml`.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `mfc_server` (`fast:`)

The bokeh/reflex `mfc_vis` panels (`live_vis:`) read only `devices`.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `devices` | yes | dict | none | `{device_name: {port, unit_id}}`. Indexed without a default in the server, so a missing key raises `KeyError`. Device names become the `device_name` enum of the endpoints. An empty dict registers no endpoints. | `helao/deploy/hte/servers/mfc/mfc_server.py:74`, `alicat_driver.py:78`, `bokeh/mfc_vis.py:86` |
| `devices.<name>.port` | yes | str | none | Serial port of the controller (e.g. `COM6`, `/dev/ttyUSB0`). | `alicat_driver.py:159` |
| `devices.<name>.unit_id` | yes | str | none | Alicat unit address letter, also the response prefix stripped from gas and manufacturer queries. | `alicat_driver.py:159`, `alicat_driver.py:192` |
| `co2_server_name` | no | str | `None` | Server key of the CO2 sensor server in the same config. `maintain_concentration` and `cancel_maintain_concentration` are registered only when this key names a server present in the config (and `devices` is non-empty). The executor reads that server's `host` and `port` and subscribes to its `ws_live`. | `mfc_server.py:73`, `mfc_server.py:77`, `alicat_driver.py:784` |

Example:
```yaml
params:
  devices:
    CO2:
      port: COM6
      unit_id: A
  co2_server_name: CO2SENSOR
```

Notes:
- If `co2_server_name` is unset or not in the config, the executor does not open a CO2 websocket (`alicat_driver.py:789`).

## Outputs

Endpoints are registered once the driver is online: everything when at least one device is configured under `devices`; `maintain_concentration` and its cancel only when `co2_server_name` names a server of the group (`helao/deploy/hte/servers/mfc/mfc_server.py:76`, `:148`).

Executor-based actions run non-one-off executors. A row returned by `_poll` is queued through the framework default data connection (`helao/hexagon/app/executor_runner.py:129-136`): file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`), columns from the first row (`helao/hexagon/adapters/native/data_stream.py:338-349`). A `_poll` that raises (for example `KeyError` from `get_lbuf` when the device never published, `helao/hexagon/app/action_host.py:415`) is caught, the runner treats the poll as finished and writes no row (`helao/hexagon/app/executor_runner.py:122-126`).

### `acquire_flowrate`, `acquire_pressure` (actions)

`MfcExec` (`helao/deploy/hte/servers/mfc/mfc_server.py:186-190`, `action_abbr` `acq_flow`, `:185`) and its subclass `PfcExec` (`:252-256`, `acq_pres`, `:251`) share `MfcExec._poll` (`helao/deploy/hte/servers/mfc/alicat_driver.py:561-586`). Each poll queues the latest live-buffer record of `device_name` plus `epoch_s`; the poll that reaches `duration` is still written. Data file `acq_flow-*.jsonl` or `acq_pres-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `pressure` | float | scalar per row | psia | pressure reading | `helao/deploy/hte/servers/mfc/alicat_driver.py:1190` |
| `temperature` | float | scalar per row | C | temperature reading | `helao/deploy/hte/servers/mfc/alicat_driver.py:1190` |
| `volumetric_flow` | float | scalar per row | device flow units | volumetric flow | `helao/deploy/hte/servers/mfc/alicat_driver.py:1190` |
| `mass_flow` | float | scalar per row | device flow units (sccm) | mass flow | `helao/deploy/hte/servers/mfc/alicat_driver.py:1190` |
| `setpoint` | float \| null | scalar per row | device units | control setpoint; `null` for a flow meter (MFM) and for any single 5-field reply, which carries no setpoint (each reply is keyed on its own). A status missing `mass_flow`, `pressure` or `control_point` is dropped | `helao/deploy/hte/servers/mfc/alicat_driver.py:1190`, `helao/deploy/hte/servers/mfc/alicat_driver.py:245` |
| `total flow` | float | scalar per row | device units | totalizer; only when the device reports 7 fields | `helao/deploy/hte/servers/mfc/alicat_driver.py:1190` |
| `gas` | str | scalar per row | none | selected gas | `helao/deploy/hte/servers/mfc/alicat_driver.py:1190` |
| `hold_valve` | bool | scalar per row | none | `HLD` flag present | `helao/deploy/hte/servers/mfc/alicat_driver.py:1193` |
| `lock_display` | bool | scalar per row | none | `LCK` flag present | `helao/deploy/hte/servers/mfc/alicat_driver.py:1193` |
| `acquire_time` | float | scalar per row | s | `time.time()` when the status was read | `helao/deploy/hte/servers/mfc/alicat_driver.py:1194` |
| `control_point` | str \| null | scalar per row | none | `mass flow`, `vol flow` or a pressure mode; `null` when the cached control point could not be read | `helao/deploy/hte/servers/mfc/alicat_driver.py:1466` |
| `epoch_s` | float | scalar per row | s | epoch stamp of the live-buffer value | `helao/deploy/hte/servers/mfc/alicat_driver.py:568` |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `total_scc` | `action_params` | float \| int | scalar | integrated gas dispensed (scc), integer `0` if no poll succeeded (`helao/deploy/hte/servers/mfc/alicat_driver.py:553`), trapezoid of `mass_flow` over the polls, floored at 0 flow; set after the run, not set when `_pre_exec` aborts because the device is not connected | `helao/deploy/hte/servers/mfc/alicat_driver.py:591` |

### `maintain_pressure`, `maintain_concentration` (actions)

`MfcConstPresExec` (`helao/deploy/hte/servers/mfc/mfc_server.py:455-459`, `action_abbr` `hold_pres`) and `MfcConstConcExec` (`:114-118`, `hold_conc`) return no `data` from `_poll` (`helao/deploy/hte/servers/mfc/alicat_driver.py:742-745`, `:906-909`), so no data file is written.

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `total_scc` | `action_params` | float \| int | scalar | integrated gas dispensed (scc) over the run, integer `0` if no poll succeeded (`helao/deploy/hte/servers/mfc/alicat_driver.py:698`, `helao/deploy/hte/servers/mfc/alicat_driver.py:862`); set after the run, not set when `_pre_exec` aborts (concentration variant: device not connected or setup failure, `:847`) | `helao/deploy/hte/servers/mfc/alicat_driver.py:750` (pressure), `:914` (concentration) |

### `set_flowrate`, `set_gas`, `set_pressure`, `hold_valve_action`, `cancel_hold_valve_action`, `hold_valve_closed_action`, `cancel_maintain_concentration`, `cancel_maintain_pressure`, `cancel_acquire_flowrate`, `cancel_acquire_pressure` (actions)

`set_gas` (`action_abbr` `set_gas`, `helao/deploy/hte/servers/mfc/mfc_server.py:307`) and the private `/set_gas` (`set_gas_private`) both call `AliCatMFC.set_gas` (`helao/deploy/hte/servers/mfc/alicat_driver.py:305`), which pauses polling, selects the gas and checks register 46; an unknown gas name raises `ValueError` and a failed readback `IOError`, so the action fails with an HTTP error.

No data files or action results.

### Private endpoints

`/start_polling`, `/stop_polling`, `/list_devices`, `/list_gases`, `/set_gas`, `/set_gas_mixture`, `/lock_display`, `/unlock_display`, `/hold_valve`, `/hold_valve_closed`, `/hold_cancel`, `/tare_volume`, `/tare_pressure`, `/manual_query_state`, `/read_valve_register`, `/write_valve_register` and `/send_command` (`helao/deploy/hte/servers/mfc/mfc_server.py:485-616`) return values to the caller only; no data files or action results.

### Live data (status/ws stream)

`AliCatMFCPoller.get_data` (`helao/deploy/hte/servers/mfc/alicat_driver.py:458-487`) publishes one status dict per configured device (`<device_name>` is a key of the server's `devices` config); never written to a file by the poller itself. A device whose read fails is left out; while polling is paused or no device answers nothing is published. Each key is stamped `(value, epoch)` (`helao/hexagon/app/action_host.py:403`). The value has the fields of the data-file table above except `epoch_s`: `MfcExec._poll` adds it by mutating the stored live-buffer dict in place (`helao/deploy/hte/servers/mfc/alicat_driver.py:567-568`), so the stored value, and the `/manual_query_state` reply (`helao/deploy/hte/servers/mfc/mfc_server.py:570`), carry `epoch_s` until the next publish replaces the dict; all have `structure` `scalar per poll`. The dict is the device's `get_status()` (`helao/deploy/hte/servers/mfc/alicat_driver.py:1147-1196`, `control_point` added at `:1466`); a status lacking `mass_flow`, `pressure` or `control_point` is dropped (`helao/deploy/hte/servers/mfc/alicat_driver.py:242-249`). A reply with 5 fields (a flow meter) has no `setpoint` key from `get_status` (`helao/deploy/hte/servers/mfc/alicat_driver.py:1184-1185`); it is published with `setpoint` set to `null` (`helao/deploy/hte/servers/mfc/alicat_driver.py:245`).
