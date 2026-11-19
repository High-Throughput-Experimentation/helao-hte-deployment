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

All three actions open the file with fixed columns (`json_data_keys`), file type `power_supply_helao__file` and a header with `column_headings` set to the same list (`helao/deploy/hte/servers/power_supply/power_supply_server.py:499-506`, `:537-544`, `:583-590`). Rows come from the executors' `_poll` return and are queued by the executor runner (`helao/hexagon/app/executor_runner.py:129-136`) into `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Rows serialize NaN as `null` (`helao/helpers/to_json.py:39`).

### `apply_voltage` (action)

`ApplyVoltageExecutor` (`helao/deploy/hte/servers/power_supply/power_supply_server.py:511`; `action_abbr` `APPLYVOLT`, `:509`) applies the voltage in `_exec` and polls the output current; each cycle normally takes about 10 s (about 5 s when the reply is non-numeric, which returns before the sleep, `helao/deploy/hte/servers/power_supply/power_supply_driver.py:300`, or when the query raises, `helao/deploy/hte/servers/power_supply/power_supply_driver.py:311-317`): the driver sleeps 5 s after the read (`helao/deploy/hte/servers/power_supply/power_supply_driver.py:305`, `sleep_time=self.poll_rate`, `helao/deploy/hte/servers/power_supply/power_supply_server.py:302`) and the runner sleeps `poll_rate` = 5 s (`helao/deploy/hte/servers/power_supply/power_supply_server.py:249`, `helao/hexagon/app/executor_runner.py:138`) until stopped. `get_current_async` always returns a success response, even from its except branch, so the `errored` branch in `helao/deploy/hte/servers/power_supply/power_supply_server.py:305-307` is never taken (see Notes). Data file `APPLYVOLT-*.jsonl` (+ `.meta.json`), one row per successful poll. A poll whose query raised returns success without data (`helao/deploy/hte/servers/power_supply/power_supply_driver.py:311-317`), so it writes no row.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `current_a` | float \| null | scalar per row | A | `IOUT1?` reading; `null` when the reply was not numeric (NaN) | `helao/deploy/hte/servers/power_supply/power_supply_driver.py:303`, `:309` (row returned at `helao/deploy/hte/servers/power_supply/power_supply_server.py:308`) |

No action results (`voltage`, `sleep_time` etc. are inputs; the executor reads them from `action_params` as dispatched).

### `square_wave` (action)

`SquareWaveExecutor` (`helao/deploy/hte/servers/power_supply/power_supply_server.py:549`; `action_abbr` `SQUAREWAVE`, `:547`) runs the whole off-on-off pulse in `_exec` (`:376-429`). Its `_poll` returns no `status`, which the runner reads as finished (`helao/hexagon/app/executor_runner.py:128`), so the loop polls once: at most one row, the output current after the pulse, and none when the read fails (`helao/deploy/hte/servers/power_supply/power_supply_server.py:441-450`). Data file `SQUAREWAVE-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `current_a` | float \| null | scalar per row | A | `IOUT1?` reading; `null` when the reply was not numeric | `helao/deploy/hte/servers/power_supply/power_supply_driver.py:303`, `:309` (row returned at `helao/deploy/hte/servers/power_supply/power_supply_server.py:447`) |

No action results (`voltage`, `sleep_time` etc. are inputs; the executor reads them from `action_params` as dispatched).

### `constant_current_square_wave` (action)

`ConstantCurrentSquareWaveExecutor` (`helao/deploy/hte/servers/power_supply/power_supply_server.py:595`; `action_abbr` `SQUAREWAVE`, `:593`) polls every 0.2 s (`:79`); each poll before `sleep_time2` elapses reads the output voltage and returns one row, and the final poll (after `sleep_time2`) returns only `finished` and no row (`:166-171`). Data file `SQUAREWAVE-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `t_s` | float | scalar per row | s | time since `_exec` started | `helao/deploy/hte/servers/power_supply/power_supply_server.py:211` |
| `voltage_v` | float \| null | scalar per row | V | `VOUT1?` reading; `null` when the query raised (NaN) | `helao/deploy/hte/servers/power_supply/power_supply_driver.py:250`, `:269` |

No action results (`voltage`, `sleep_time` etc. are inputs; the executor reads them from `action_params` as dispatched).

### Private endpoints

`/stop_private` disconnects the driver and returns nothing (`helao/deploy/hte/servers/power_supply/power_supply_server.py:623-626`); no data files or action results.

## Notes

- `ConstantCurrentSquareWaveExecutor._poll` reads `resp.data['voltage_v']` (`helao/deploy/hte/servers/power_supply/power_supply_server.py:210`) without checking `resp.response`. When the driver is not connected, `get_voltage_async` returns a failed response with empty `data` (`helao/deploy/hte/servers/power_supply/power_supply_driver.py:237-242`), so the line raises `KeyError`, the runner catches it and ends the polling loop early with no further rows (`helao/hexagon/app/executor_runner.py:122-126`).
- `SquareWaveExecutor._poll` returns no `status`, so the runner treats the first poll as the last (`helao/hexagon/app/executor_runner.py:128`); `square_wave` therefore writes at most one data row.
- `ApplyVoltageExecutor._poll` has an `errored` branch for a failed read (`helao/deploy/hte/servers/power_supply/power_supply_server.py:305-307`), but `get_current_async` returns `DriverResponseType.success` in every path after the connected check, including its except branch (`helao/deploy/hte/servers/power_supply/power_supply_driver.py:311-317`), so the branch is dead code; a failed query yields a success reply without data and no row.
