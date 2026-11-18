# nidaqmx

Action server for National Instruments DAQmx hardware: digital outputs (cells, pumps, valves, LEDs, heaters, TTL), foot-switch digital inputs, thermocouple monitoring, a heater loop, and synchronised multi-cell current/voltage measurement.

## Vendor software

Install by hand (not pip/conda):

- NI-DAQmx driver runtime. The `nidaqmx` Python package (in `requirements.txt`) only wraps it and does not work without it. The code does not say where to download it; National Instruments distributes it.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `nidaqmx_server` (`fast:`)

Every key is optional. An endpoint is registered only when its group is non-empty. The `nidaqmx_control` and `nidaqmx_vis` panels (`control_vis:` / `action_vis:`) read no params of their own; the control panels take the digital-output group list from `DO_GROUPS` in `nidaqmx_server.py`.

Port strings are NI-DAQmx physical channel names, e.g. `cDAQ1Mod1/port0/line9` or `PXI-6289/ai16`.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `dev_mastercell` | no | dict `{name: do_port}` | `{}` | Digital outputs for the `mastercell` action. | `helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:247` |
| `dev_activecell` | no | dict `{name: do_port}` | `{}` | Digital outputs for the `activecell` action. | `nidaqmx_server.py:243` |
| `dev_pump` | no | dict `{name: do_port}` | `{}` | Digital outputs for the `pump` action. Also driven low on E-STOP. | `nidaqmx_server.py:216`, `nidaqmx_driver.py:119` |
| `dev_gasvalve` | no | dict `{name: do_port}` | `{}` | Digital outputs for the `gasvalve` action. Also driven low on E-STOP. | `nidaqmx_server.py:219`, `nidaqmx_driver.py:124` |
| `dev_liquidvalve` | no | dict `{name: do_port}` | `{}` | Digital outputs for the `liquidvalve` action. Also driven low on E-STOP. | `nidaqmx_server.py:224`, `nidaqmx_driver.py:129` |
| `dev_multivalve` | no | dict `{name: do_port}` | `{}` | Digital outputs for the `multivalve` action. Not driven low on E-STOP. | `nidaqmx_server.py:229` |
| `dev_led` | no | dict `{name: do_port}` | `{}` | Digital outputs for the `led` action. Also driven low on E-STOP. | `nidaqmx_server.py:234`, `nidaqmx_driver.py:138` |
| `dev_fswbcd` | no | dict `{name: do_port}` | `{}` | Digital outputs for the `fswbcd` action. Not driven low on E-STOP. | `nidaqmx_server.py:237` |
| `dev_heat` | no | dict `{name: do_port}` | `{}` | Digital outputs for the `heater` action and the heater loop. The loop acts only on the names `cellheater` and `res_heater`. Also driven low on E-STOP. | `nidaqmx_server.py:213`, `nidaqmx_driver.py:133`, `nidaqmx_driver.py:658` |
| `dev_ttl` | no | dict `{name: do_port}` | `{}` | TTL lines held high for a duration by the `toggle_ttl` action. Also driven low on E-STOP. | `nidaqmx_server.py:251`, `nidaqmx_driver.py:141` |
| `dev_fsw` | no | dict `{name: di_port}` | `{}` | Digital inputs read by the `fsw` (foot switch) action. | `nidaqmx_server.py:253`, `nidaqmx_server.py:445` |
| `dev_monitor` | no | dict `{name: ai_port}` | `{}` | Thermocouple analog inputs polled continuously. K-type, or T-type when the name contains `Ttc_`; range 0 to 150 degC. The heater loop indexes this dict without a default and reads the names `Ttemp_Ktc_in_cell_C` and `Ttemp_Ttc_in_reservoir_C` (`KeyError` if absent). | `nidaqmx_server.py:210`, `nidaqmx_driver.py:420`, `nidaqmx_driver.py:653` |
| `dev_cellcurrent` | no | dict `{cell: ai_port}` | `{}` | Current analog inputs (master task) for `cellIV`. `cellIV` is registered only when both `dev_cellcurrent` and `dev_cellvoltage` are non-empty; the driver indexes it without a default when a cell IV starts. | `nidaqmx_server.py:239`, `nidaqmx_server.py:457`, `nidaqmx_driver.py:332` |
| `dev_cellvoltage` | no | dict `{cell: ai_port}` | `{}` | Voltage analog inputs (slave task) for `cellIV`. Same registration rule as `dev_cellcurrent`. | `nidaqmx_server.py:241`, `nidaqmx_driver.py:361` |
| `dev_cellcurrent_trigger` | no | str | `""` | Digital-edge start-trigger terminal (e.g. `PFI1`) for the current task. Used only when `TTLwait` is not `-1` and both trigger keys are non-empty; otherwise a warning is logged and the measurement starts without a trigger wait. | `nidaqmx_driver.py:384`, `nidaqmx_driver.py:408` |
| `dev_cellvoltage_trigger` | no | str | `""` | Same, for the voltage task. | `nidaqmx_driver.py:383`, `nidaqmx_driver.py:400` |
| `allow_no_sample` | no | bool | `False` | `True` permits a `cellIV` run with no validated samples. | `nidaqmx_driver.py:143`, `nidaqmx_server.py:504` |
| `do_active_low` | no | list of DO names | `[]` | Names from any DO group (`dev_mastercell`, `dev_activecell`, `dev_pump`, `dev_gasvalve`, `dev_liquidvalve`, `dev_multivalve`, `dev_led`, `dev_fswbcd`, `dev_heat`, `dev_ttl`) wired active-low: logical ON writes LOW, OFF writes HIGH, and readback and `/get_digital_outs` report the logical state. E-STOP still writes OFF, so these lines go HIGH. An unknown name or a non-list raises `ValueError` at start. | `nidaqmx_driver.py:set_digital_out` |
| `do_open_collector` | no | list of DO names, or `true` | `[]` | Lines whose output drive type is set to open collector each time a write or readback task opens them. `true` means every configured DO line. Same validation as `do_active_low`. Some DO modules reject `do_output_drive_type`, so writes to listed lines would then raise; bench-check set OC, write and read on the target module before enabling it on a station. | `nidaqmx_driver.py:set_digital_out` |
| `shutdown_to_off` | no | bool | `False` | `True` writes logical OFF (per-line polarity) to every configured DO line on server shutdown, best effort, before disconnecting. | `nidaqmx_driver.py:async_shutdown` |

Example (digital I/O only, trimmed from a station config):
```yaml
params:
  dev_pump:
    peripump: PXI-6284/port0/line4
    direction: PXI-6284/port0/line0
  dev_gasvalve:
    inlet: PXI-6284/port1/line2
  dev_liquidvalve:
    work_refill: PXI-6284/port1/line4
  dev_fsw:
    done: PXI-6284/port2/line4
  dev_led:
    led: PXI-6289/port0/line0
```

Cell IV and monitor keys, from a station config that uses them:
```yaml
params:
  allow_no_sample: true
  dev_cellcurrent_trigger: PFI1
  dev_cellvoltage_trigger: PFI1
  dev_cellcurrent:
    '1': PXI-6289/ai16
  dev_cellvoltage:
    '1': PXI-6284/ai16
  dev_monitor:
    Ttemp_Ktc_in_cell_C: PXI-6289/ai6
    Ttemp_Ttc_in_reservoir_C: PXI-6289/ai7
```

Notes:
- A name used in more than one digital-output group is logged as an error and refused by the private `set_digital_out` endpoint (`nidaqmx_server.py:121`).
- `dev_pump`, `dev_gasvalve`, `dev_liquidvalve`, `dev_led`, `dev_heat` and `dev_ttl` are read in two places (server and driver) with the same default `{}`.

## Outputs

Actions here write through the framework default data connection: one JSON object per queued message, file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Without declared `json_data_keys` the columns are the keys of the first message queued (`helao/hexagon/adapters/native/data_stream.py:338-349`). Which actions exist depends on the `dev_*` groups present in the server params; each group below says which one gates it.

### Digital-output actions: `mastercell`, `activecell`, `pump`, `gasvalve`, `liquidvalve`, `multivalve`, `led`, `fswbcd`, `heater` (actions)

Each drives one named line through `_set_do` (`helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:138-151`) and queues one row, `action_abbr` `mcell` (`:259`), `acell` (`:280`), `pump` (`:301`), `gfv` (`:322`), `lfv` for `liquidvalve` (`:343`) and for `multivalve` (`:364`), `led` (`:385`), `fswbcd` (`:406`), `heat` (`:614`). Each exists only when its `dev_*` group is configured. The data file is `<action_abbr>-*.jsonl` (+ `.meta.json`), one row:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `error_code` | str | scalar per row | none | `ErrorCodes` value: `none`, or `not_available` when the port is `None` | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:801` |
| `port` | str | scalar per row | none | NI-DAQ channel string written (looked up from the `dev_*` group by `_set_do`, which raises `KeyError` for an unknown name, `nidaqmx_server.py:146`) | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:802` |
| `name` | str | scalar per row | none | friendly line name | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:803` |
| `type` | str | scalar per row | none | always `digital_out` | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:804` |
| `value` | bool | scalar per row | none | requested logical state (`on`); on `do_active_low` lines the wire level is the inverse | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:805` |

Action results (in `-act.json`), set before the write:

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `do_port` | `action_params` | str | scalar | channel string looked up from the `dev_*` group by the selected name | `helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:146` |
| `do_name` | `action_params` | str | scalar | the selected line name, copied from the endpoint's own param (`cell`, `pump`, `gasvalve`, `liquidvalve`, `multivalve`, `led`, `fswbcd`, `heater`) | `helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:147` |

### `fsw` (action, needs `dev_fsw`)

Reads one foot-switch digital input and queues one row, `action_abbr` `fsw` (`helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:425`, `:432-436`); data file `fsw-*.jsonl` (+ `.meta.json`).

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `error_code` | str | scalar per row | none | `none`, or `not_available` when the port is `None` | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:900` |
| `port` | str | scalar per row | none | NI-DAQ channel string read | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:901` |
| `name` | str | scalar per row | none | foot-switch name | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:902` |
| `type` | str | scalar per row | none | always `digital_in` | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:903` |
| `value` | unknown (dynamic) | scalar per row | none | `Task.read` result of the one-sample read; `null` when the port is `None` | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:904` |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `di_port` | `action_params` | str | scalar | channel string of the selected foot switch | `helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:428` |
| `di_name` | `action_params` | str | scalar | the selected foot-switch name | `helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:431` |

### `toggle_ttl` (action, needs `dev_ttl`)

`TTLExec` (`helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:660-661`); `action_abbr` is `ttl`. Two rows are queued: the line going high from `_exec` (`helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:1194`) and going low from `_post_exec` (`:1210`). Data file `ttl-*.jsonl` (+ `.meta.json`). Each row has the same fields as a digital-output row above (`error_code`, `port`, `name`, `type`, `value`), with `name` the TTL name and `value` `true` on the first row and `false` on the second. An exception setting the line high ends the action with no row. No action results.

### `cancel_toggle_ttl` (action)

No data files or action results.

### `cellIV` (action, needs `dev_cellcurrent` and `dev_cellvoltage`)

`CellIVExec` (`helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:479`, `:514-527`; `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:1000`); `action_abbr` is `multiCV`. The NI-DAQ buffer callback pushes one message per callback straight to the data queue (`nidaqmx_driver.py:569-582`), holding one entry per cell in `FIFO_cell_keys` (`cell1`..`cell9`, `:245-255`), each routed to that cell's own file: `_pre_exec` splits the action into nine file connections (`nidaqmx_driver.py:1049-1062`), so one action writes nine data files, each with a `.meta.json` header carrying `optional.cell` set to `cell<k>` (`nidaqmx_server.py:518`, `nidaqmx_driver.py:1061`) and its own sample labels. File type is `ni_helao__file`. `CellIVExec._poll` returns no data (`nidaqmx_driver.py:1091`, `:1099`).

Data file `multiCV-*.jsonl` (+ `.meta.json`), one row per NI buffer callback, per cell:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `t_s` | float | list[float] | s | `IVtimeoffset + i / samplingrate` for each sample of the callback | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:562-565`, `:572` |
| `Icell_A` | float | list[float] | A | current of that cell, from the `dev_cellcurrent` task (scaled by the `NEGATE3` custom scale) | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:573` |
| `Ecell_V` | float | list[float] | V | potential of that cell, from the `dev_cellvoltage` task | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:574` |
| `<monitor>` | float | scalar per row | degC | one column per `dev_monitor` name (for example `Ktc_in_cell`); the monitor's latest live-buffer value at the callback. A name the poller has not yet published raises `KeyError` in `ActionHost.get_lbuf` (`helao/hexagon/app/action_host.py:415`, buffer starts `{}` at `:190`); the callback catches it (`helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:584-586`) and drops that callback's batch for all nine cells | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:577` |

`<monitor>` columns come from the config key `dev_monitor` (`nidaqmx_driver.py:490`); a server with no `dev_monitor` has none. The `Ttemp_*` strings in `FIFO_column_headings` (`:260-265`) are not used as columns. Rows are not written when the action is E-stopped or after the measurement has been turned off (`:588-612`). No action results.

### `acquire_monitors` (action, needs `dev_monitor`)

`DevMonExec` (`helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:555-561`); `action_abbr` is `ni_monitor`. Each `_poll` queues one row (`helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:1147-1151`); data file `ni_monitor-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `<monitor>` | float | scalar per row | degC | one column per `dev_monitor` name; the latest live-buffer value. A name the poller has not yet published raises `KeyError` (`helao/hexagon/app/action_host.py:415`) out of `_poll`, the runner receives `{}` and the action finishes with no row | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:1137` |
| `epoch_s` | float | scalar per row | s | the newest epoch stamp among the monitor values (`max(times)`) | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:1139` |

No action results.

### `cancel_acquire_monitors`, `heatloop` (actions)

No data files or action results (`heatloop` drives the heaters through the driver directly and never calls `ctx.begin()`, `nidaqmx_server.py:697-760`).

### `stop` (action)

Queues one row `{"stop": <DriverResponse>}` (`helao/deploy/hte/servers/nidaqmx/nidaqmx_server.py:865`); data file `stop-*.jsonl` (+ `.meta.json`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `stop` | dict | dict | none | the driver's `DriverResponse` dataclass, serialised by field | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:319-331` |

Nested `stop` fields (`helao/core/drivers/helao_driver.py:73-77`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `response` | str | scalar | none | `DriverResponseType`; always `success` here | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:330` |
| `message` | str | scalar | none | always empty here | `helao/core/drivers/helao_driver.py:74` |
| `data` | dict | dict | none | always `{}` here | `helao/core/drivers/helao_driver.py:75` |
| `status` | str | scalar | none | `DriverStatus`; always `ok` here | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:330` |
| `timestamp` | str | scalar | none | ISO 8601 time the response was built | `helao/core/drivers/helao_driver.py:80` |

### Live data (status/ws stream)

`cNIMAXPoller.get_data` (`helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:970-995`), wired as the server's `poller_class` (`nidaqmx_server.py:190`), publishes one value per thermocouple channel at each poll, never written to a file by the poller itself; it is empty when no `dev_monitor` is configured. Each key is stamped `(value, epoch)` (`helao/hexagon/app/action_host.py:403`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `<monitor>` | float | scalar per poll | degC | latest reading of the `dev_monitor` channel of that name (K-type, or T-type when the name contains `Ttc_`) | `helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:989-992` |

### Private endpoints

`/readtemp`, `/monloop`, `/stopmonloop`, `/stopheatloop`, `/get_digital_outs`, `/set_digital_out`: return values to the caller only (`nidaqmx_server.py:583-594`, `:685-694`, `:769-780`, `:796-851`); no data files or action results.

## Notes

- `acquire_monitors` and `cellIV` read monitor values with `ActionHost.get_lbuf`, which raises `KeyError` for a name never published (`helao/hexagon/app/action_host.py:415`); a monitor whose first poller read has not happened yet makes `acquire_monitors` finish with no row and drops cellIV batches silently (`helao/deploy/hte/servers/nidaqmx/nidaqmx_driver.py:584-586`).
