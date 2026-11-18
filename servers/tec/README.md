# tec

Meerstetter TEC temperature controller action server (`tec_server`, driver `MeerstetterTEC` in `mecom_driver.py`): reads TEC telemetry, enables or disables the control loop and sets the target temperature. `bokeh/tec_vis.py` plots it.

## Vendor software
- `pyMeCom` (Python module `mecom`): listed in this folder's `requirements.txt` and the root `requirements.txt`, installed from `https://github.com/meerstetter/pyMeCom/archive/master.zip`. It is not on conda; pip/uv installs it.
- No Meerstetter PC software or serial driver is required by the code; the TEC is reached over a serial port.

## Params
Host-level keys every server accepts: see `docs/config-schema.md` ("Group conventions for `params:`").

### `tec_server` (`fast:` value)
| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `port` | yes | string | none | Serial port of the TEC (passed to `MeCom(serialport=...)`). `KeyError` at startup if absent. | `helao/deploy/hte/servers/tec/mecom_driver.py:84`, `:101` |
| `channel` | yes | int | none | TEC channel (parameter instance). `KeyError` at startup if absent. | `helao/deploy/hte/servers/tec/mecom_driver.py:83` |
| `queries` | no | list of string | `DEFAULT_QUERIES` = `enabled_status`, `object_temperature`, `target_object_temperature`, `output_current`, `temperature_is_stable` | Parameters polled into `tec_vals`. Allowed names (`COMMAND_TABLE`): `device_status`, `enabled_status`, `temperature_is_stable`, `object_temperature`, `target_object_temperature`, `output_current`, `output_voltage`, `sink_temperature`, `ramp_temperature`. | `helao/deploy/hte/servers/tec/mecom_driver.py:85`, `:32`, `:42` |
| `retries` | no | int | `15` | Connection attempts when the handshake raises `ResponseTimeout`. Another error ends the attempts at once. | `helao/deploy/hte/servers/tec/mecom_driver.py:112` |
| `start_margin` | no | number | `0` | Stored on the driver but not used (the docstring says "carried for parity"). | `helao/deploy/hte/servers/tec/mecom_driver.py:91` |
| `allow_no_sample` | no | bool | `True` | Stored on the driver but not used. | `helao/deploy/hte/servers/tec/mecom_driver.py:96` |

Notes:
- The poll interval comes from the server-level key `polling_time` (default 0.1 s, read by `ActionHost`), not from `params`.
- No `hte` or `test` config uses this server, so the example is built from the code defaults.

Example:
```yaml
params:
  port: COM5
  channel: 1
  queries: [object_temperature, target_object_temperature, output_current]
  retries: 15
```

### `tec_vis` (`bokeh:` panel)
Reads no params of its own.

## Outputs

`TECMonExec` and `TECWaitExec` are non-one-off executors. Each `_poll` returns one row, which the executor runner queues through the framework default data connection (`helao/hexagon/app/executor_runner.py:129-136`): file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`); columns are the keys of the first row (`helao/hexagon/adapters/native/data_stream.py:338-349`). The row is the live-buffer `tec_vals` dict plus `epoch_s`. If the buffer has never received `tec_vals` (the poller publishes it only when at least one parameter was read), `get_lbuf` raises `KeyError` (`helao/hexagon/app/action_host.py:415`), the runner catches it (`helao/hexagon/app/executor_runner.py:122-126`), treats the poll as finished and writes no row.

### `record_tec` (action)

`TECMonExec` (`helao/deploy/hte/servers/tec/tec_server.py:80-84`; `action_abbr` `TEC`, `:79`). Each poll queues one row (`helao/deploy/hte/servers/tec/mecom_driver.py:328-332`); the poll that reaches `duration` is still written. Data file `TEC-*.jsonl` (+ `.meta.json`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `epoch_s` | float | scalar per row | s | epoch stamp of the live-buffer `tec_vals` value | `helao/deploy/hte/servers/tec/mecom_driver.py:317` |
| `<query>` | unknown (dynamic) | scalar per row | as in `COMMAND_TABLE` (`degC`, `A`, `V`, none) | one column per name in the server's `queries` param whose read succeeded in the latest poll (the row is the whole `tec_vals` dict, replaced on every poll, `helao/hexagon/adapters/native/data_stream.py:359-361`; default `enabled_status`, `object_temperature`, `target_object_temperature`, `output_current`, `temperature_is_stable`; allowed names in `COMMAND_TABLE`, `helao/deploy/hte/servers/tec/mecom_driver.py:42-52`). The Python type is whatever `MeCom.get_parameter` returns for that parameter id (vendor library) | `helao/deploy/hte/servers/tec/mecom_driver.py:319` (values from `:284`) |

### `wait_till_stable` (action)

`TECWaitExec` (`helao/deploy/hte/servers/tec/tec_server.py:182-186`; `action_abbr` `waitTEC`, `:181`). Sleeps 2 s in `_pre_exec` (`helao/deploy/hte/servers/tec/mecom_driver.py:361`), then each poll queues one row with the same layout as `record_tec` (`:386-390`) until `temperature_is_stable` equals `2`; that final poll is written. Data file `waitTEC-*.jsonl` (+ `.meta.json`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `epoch_s` | float | scalar per row | s | epoch stamp of the live-buffer `tec_vals` value | `helao/deploy/hte/servers/tec/mecom_driver.py:372` |
| `<query>` | unknown (dynamic) | scalar per row | as in `COMMAND_TABLE` | one column per name in the `queries` param whose read succeeded in the latest poll, as for `record_tec`; the `queries` list must contain `temperature_is_stable`, see Notes | `helao/deploy/hte/servers/tec/mecom_driver.py:374` |

### `cancel_record_tec`, `cancel_wait_till_stable`, `set_temperature`, `enable_tec`, `disable_tec` (actions)

No data files or action results.

### Live data (status/ws stream)

`MeerstetterTECPoller.get_data` (`helao/deploy/hte/servers/tec/mecom_driver.py:275-291`) publishes one `tec_vals` dict per poll; never written to a file by the poller itself. A parameter whose query fails is left out (a MeCom checksum or response error also drops the session so it is reopened, `:207-209`); if no parameter was read nothing is published. The key is stamped `(value, epoch)` (`helao/hexagon/app/action_host.py:403`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `tec_vals` | dict | dict | none | `{query_name: value}` with the unit dropped (fields below) | `helao/deploy/hte/servers/tec/mecom_driver.py:290` |

| key | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `<query>` | unknown (dynamic) | scalar per poll | as in `COMMAND_TABLE` | value of that parameter; type from `MeCom.get_parameter` (vendor library). `<query>` is a name from the `queries` param | `helao/deploy/hte/servers/tec/mecom_driver.py:284` |

## Notes

- `TECWaitExec._poll` indexes `live_dict["temperature_is_stable"]` (`helao/deploy/hte/servers/tec/mecom_driver.py:375`). If the `queries` param omits `temperature_is_stable`, or that read failed in the latest poll, this raises `KeyError`, the runner catches it and ends the loop at once, so `wait_till_stable` returns without waiting for stability (`helao/hexagon/app/executor_runner.py:122-126`).
