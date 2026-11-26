# syringe

KD Scientific Legato 100 syringe pump action server (`syringe_server`, driver `KDS100` in `legato_driver.py`): infuse and withdraw over an RS-232 chain, with a status poller.

## Vendor software
No vendor software beyond the env files (`pyserial` is in `environment.yml` and the root env). The pump takes RS-232 at a fixed 115200 baud; no vendor driver is loaded.

## Params
Host-level keys every server accepts: see `docs/config-schema.md` ("Group conventions for `params:`").

### `syringe_server` (`fast:` value)
| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `port` | yes | string | none | Serial port of the pump chain (for example `COM3`). `KeyError` inside `connect()`, which is caught: the connect then fails and is logged. | `helao/deploy/hte/servers/syringe/legato_driver.py:143` |
| `pumps` | yes | dict | none | `{pump_name: {address: int, diameter: float}}`. `address` is the pump's chain address; `diameter` is the syringe inner diameter in mm, sent to the pump at startup. The poller, safe-state and setup loops use every entry. A pump action uses only the first entry in the dict (one pump per COM port). Missing `pumps`: `KeyError` in the action; the loops treat it as no pumps. | `helao/deploy/hte/servers/syringe/legato_driver.py:205`, `:486`, `:509`, `:544`, `:616` |
| `pump_addrs` | no | dict | `{}` | Only its keys are read, as pump names for the time-query helpers. No existing config sets it, so those helpers do nothing when called without a pump name. | `helao/deploy/hte/servers/syringe/legato_driver.py:389`, `:418`, `:441`, `:458` |

Example:
```yaml
params:
  port: COM3
  pumps:
    zero:
      address: 0
      diameter: 26.7
```
Notes:
- The docstring of `KDS100` lists only `port` and `pumps`; `pump_addrs` is read in code but documented nowhere else.

## Outputs

### `infuse`, `withdraw` (actions)

`PumpExec` (`helao/deploy/hte/servers/syringe/syringe_server.py:73`, `:95`) returns no `data` from `_pre_exec`, `_exec`, `_poll` or `_post_exec` (`helao/deploy/hte/servers/syringe/legato_driver.py:633`, `:654`, `:663-667`, `:687`). The driver's tracked `present_volume_ul` is updated by the pump commands, but nothing is recorded in the action.

No data files or action results.

### `get_present_volume` (action)

Queues one row (`helao/deploy/hte/servers/syringe/syringe_server.py:118`) through the framework default data connection; no `action_abbr` is passed, so it defaults to the action name (`helao/hexagon/app/action_context.py:190`): file `get_present_volume-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Data file `get_present_volume-*.jsonl` (+ `.meta.json`), one row:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `present_volume_ul` | float | scalar per row | uL | volume the driver tracks as in the syringe (starts at 0.0, set by `/set_present_volume`, adjusted when `clear_volume` runs after infuse/withdraw) | `helao/deploy/hte/servers/syringe/syringe_server.py:115` |
| `error_code` | str | scalar per row | none | `ErrorCodes.none` value, always `none` | `helao/deploy/hte/servers/syringe/syringe_server.py:115` |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `_present_volume_ul` | `action_output` | float | scalar | same value as the row's `present_volume_ul`, so later actions inherit it | `helao/deploy/hte/servers/syringe/syringe_server.py:117` |

### Private endpoints

`/set_present_volume` and `/get_present_volume` return `{"present_volume_ul": ...}` to the caller; `/start_polling`, `/stop_polling`, `/set_rate`, `/set_target_volume`, `/start_pump`, `/stop_pump`, `/clear_volume` and `/clear_target_volume` return the driver reply or nothing (`helao/deploy/hte/servers/syringe/syringe_server.py:45-161`). No data files or action results.

### Live data (status/ws stream)

`KDS100Poller.get_data` (`helao/deploy/hte/servers/syringe/legato_driver.py:521-599`) publishes one status dict per configured pump (`<pump_name>` is a key of the server's `pumps` config); never written to a file by the poller itself. A pump that did not answer, answered with a mismatching address, or any poll while polling is paused or the port is not open contributes nothing. A prompt that matches no known state only yields `status: null` (`state` comes from the prompt, `helao/deploy/hte/servers/syringe/legato_driver.py:561-562`) while the pump keeps publishing. A flags string that is not exactly six characters, or a status line that does not split into four fields, makes `get_data` raise (`helao/deploy/hte/servers/syringe/legato_driver.py:551`, `helao/deploy/hte/servers/syringe/legato_driver.py:573-580`), and so does a status-line field whose prefix after the two address characters matches no known state: `state_split` (from `addrstate_rate[2:]`, `helao/deploy/hte/servers/syringe/legato_driver.py:559-560`) stays `None`, `split(None)` returns the whole text and the `int(...)` conversion raises (`helao/deploy/hte/servers/syringe/legato_driver.py:570`). The poll is then dropped for every pump. Each key is stamped `(value, epoch)` (`helao/hexagon/app/action_host.py:403`) with `value` a dict:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `status` | str \| null | scalar per poll | none | `idle`, `infusing`, `withdrawing`, `stalled` or `target reached`; `null` when the prompt matched none of them | `helao/deploy/hte/servers/syringe/legato_driver.py:582` |
| `rate_fL` | int | scalar per poll | as reported by the pump (key name says fL) | current rate | `helao/deploy/hte/servers/syringe/legato_driver.py:583` |
| `pump_time_ms` | int | scalar per poll | ms | pump run time | `helao/deploy/hte/servers/syringe/legato_driver.py:584` |
| `pump_volume_fL` | int | scalar per poll | fL | volume counter | `helao/deploy/hte/servers/syringe/legato_driver.py:585` |
| `motor_direction` | str | scalar per poll | none | single status character from the flag string | `helao/deploy/hte/servers/syringe/legato_driver.py:586` |
| `limit_switch_state` | str | scalar per poll | none | single status character | `helao/deploy/hte/servers/syringe/legato_driver.py:587` |
| `stall_status` | str | scalar per poll | none | single status character | `helao/deploy/hte/servers/syringe/legato_driver.py:588` |
| `trigger_input_state` | str | scalar per poll | none | single status character | `helao/deploy/hte/servers/syringe/legato_driver.py:589` |
| `direction_port` | str | scalar per poll | none | single status character | `helao/deploy/hte/servers/syringe/legato_driver.py:590` |
| `target_reached` | str | scalar per poll | none | single status character | `helao/deploy/hte/servers/syringe/legato_driver.py:591` |

`PumpExec._exec` also publishes a one-key value `{"status": "infusing" | "withdrawing"}` for its pump right after the start command, so the executor's first poll does not read stale state (`helao/deploy/hte/servers/syringe/legato_driver.py:647-653`).
