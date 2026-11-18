# power_supply

Action server for a VISA serial bench power supply (Korad/RND-style `VSET1:`/`ISET1:`/`OUT1` command set): constant voltage, square wave, and constant-current square wave.

## Vendor software

No vendor software beyond the env files. `pyvisa` and `pyvisa-py` are in `environment.yml`. The driver calls `pyvisa.ResourceManager()` with no backend argument, so an installed VISA runtime is used if pyvisa finds one; otherwise pyvisa-py is used.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `power_supply_server` (`fast:`)

The `power_supply_vis` panels (`action_vis:`) read no params.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `resource_name` | yes | str | `None` | VISA resource string, e.g. `ASRL/dev/ttyUSB0::INSTR` or `ASRL3::INSTR`. Not checked at start; `connect()` fails if it is missing or wrong. | `helao/deploy/hte/servers/power_supply/power_supply_driver.py:48` |
| `timeout_ms` | no | int | `10000` | VISA I/O timeout in milliseconds. | `power_supply_driver.py:49` |

Example:
```yaml
params:
  resource_name: 'ASRL/dev/ttyUSB0::INSTR'
  timeout_ms: 10000
```

Notes:
- The server sets `app.server_params["allow_concurrent_actions"] = False` in code, overriding any config value (`power_supply_server.py:476`).

## Outputs

All three actions open the file with fixed columns (`json_data_keys`), file type `power_supply_helao__file` and a header with `column_headings` set to the same list (`helao/deploy/hte/servers/power_supply/power_supply_server.py:499-506`, `:541-548`, `:591-598`). Rows come from the executors' `_poll` return and are queued by the executor runner (`helao/hexagon/app/executor_runner.py:129-136`) into `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Rows serialize NaN as `null` (`helao/helpers/to_json.py:39`). Every `-act.json` also records the parameters the endpoint re-writes into `action_params`: the caller's value, or the endpoint default when the caller omitted it.

### `apply_voltage` (action)

`ApplyVoltageExecutor` (`helao/deploy/hte/servers/power_supply/power_supply_server.py:515`; `action_abbr` `APPLYVOLT`, `:509`) applies the voltage in `_exec` and polls the output current; each cycle takes about 10 s: the driver sleeps 5 s after the read (`helao/deploy/hte/servers/power_supply/power_supply_driver.py:305`, `sleep_time=self.poll_rate`, `helao/deploy/hte/servers/power_supply/power_supply_server.py:302`) and the runner sleeps `poll_rate` = 5 s (`helao/deploy/hte/servers/power_supply/power_supply_server.py:249`, `helao/hexagon/app/executor_runner.py:138`) until stopped or a read fails (a failed read ends the loop with status `errored`, `:305-307`). Data file `APPLYVOLT-*.jsonl` (+ `.meta.json`), one row per successful poll. A poll whose query raised returns success without data (`helao/deploy/hte/servers/power_supply/power_supply_driver.py:311-317`), so it writes no row.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `current_a` | float \| null | scalar per row | A | `IOUT1?` reading; `null` when the reply was not numeric (NaN) | `helao/deploy/hte/servers/power_supply/power_supply_driver.py:303`, `:309` (row returned at `helao/deploy/hte/servers/power_supply/power_supply_server.py:308`) |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `voltage` | `action_params` | float | scalar | applied voltage (V) | `helao/deploy/hte/servers/power_supply/power_supply_server.py:511` |
| `sleep_time` | `action_params` | float | scalar | delay (s) passed to `apply_voltage_async` | `helao/deploy/hte/servers/power_supply/power_supply_server.py:512` |

### `square_wave` (action)

`SquareWaveExecutor` (`helao/deploy/hte/servers/power_supply/power_supply_server.py:557`; `action_abbr` `SQUAREWAVE`, `:551`) runs the whole off-on-off pulse in `_exec` (`:376-429`). Its `_poll` returns no `status`, which the runner reads as finished (`helao/hexagon/app/executor_runner.py:128`), so the loop polls once: at most one row, the output current after the pulse, and none when the read fails (`helao/deploy/hte/servers/power_supply/power_supply_server.py:441-450`). Data file `SQUAREWAVE-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `current_a` | float \| null | scalar per row | A | `IOUT1?` reading; `null` when the reply was not numeric | `helao/deploy/hte/servers/power_supply/power_supply_driver.py:303`, `:309` (row returned at `helao/deploy/hte/servers/power_supply/power_supply_server.py:447`) |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `voltage` | `action_params` | float | scalar | pulse amplitude (V) | `helao/deploy/hte/servers/power_supply/power_supply_server.py:553` |
| `sleep_time` | `action_params` | float | scalar | phase duration (s) | `helao/deploy/hte/servers/power_supply/power_supply_server.py:554` |

### `constant_current_square_wave` (action)

`ConstantCurrentSquareWaveExecutor` (`helao/deploy/hte/servers/power_supply/power_supply_server.py:609`; `action_abbr` `SQUAREWAVE`, `:601`) polls every 0.2 s (`:79`); each poll before `sleep_time2` elapses reads the output voltage and returns one row, and the final poll (after `sleep_time2`) returns only `finished` and no row (`:166-171`). Data file `SQUAREWAVE-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `t_s` | float | scalar per row | s | time since `_exec` started | `helao/deploy/hte/servers/power_supply/power_supply_server.py:211` |
| `voltage_v` | float \| null | scalar per row | V | `VOUT1?` reading; `null` when the query raised (NaN) | `helao/deploy/hte/servers/power_supply/power_supply_driver.py:250`, `:269` |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `current` | `action_params` | float | scalar | ON-phase current setpoint (A) | `helao/deploy/hte/servers/power_supply/power_supply_server.py:603` |
| `sleep_time` | `action_params` | float | scalar | elapsed time (s) at which OFF to ON | `helao/deploy/hte/servers/power_supply/power_supply_server.py:604` |
| `sleep_time1` | `action_params` | float | scalar | elapsed time (s) at which ON to OFF | `helao/deploy/hte/servers/power_supply/power_supply_server.py:605` |
| `sleep_time2` | `action_params` | float | scalar | elapsed time (s) at which polling ends | `helao/deploy/hte/servers/power_supply/power_supply_server.py:606` |

### Private endpoints

`/stop_private` disconnects the driver and returns nothing (`helao/deploy/hte/servers/power_supply/power_supply_server.py:637-640`); no data files or action results.

## Notes

- `ConstantCurrentSquareWaveExecutor._poll` reads `resp.data['voltage_v']` (`helao/deploy/hte/servers/power_supply/power_supply_server.py:210`) without checking `resp.response`. When the driver is not connected, `get_voltage_async` returns a failed response with empty `data` (`helao/deploy/hte/servers/power_supply/power_supply_driver.py:237-242`), so the line raises `KeyError`, the runner catches it and ends the polling loop early with no further rows (`helao/hexagon/app/executor_runner.py:122-126`).
- `SquareWaveExecutor._poll` returns no `status`, so the runner treats the first poll as the last (`helao/hexagon/app/executor_runner.py:128`); `square_wave` therefore writes at most one data row.
