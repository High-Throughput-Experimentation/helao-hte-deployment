# diapump

Action server for a KNF SIMDOS RC-P diaphragm dosing pump on RS-485 (continuous-rate runs, polling, direct start/stop).

## Vendor software

No vendor software beyond the env files (`pyserial`, from `environment.yml`).

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `diapump_server` (`fast:`)

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `port` | yes | str | none (KeyError in `connect` if absent) | Serial port of the RS-485 adapter (for example `COM7`). Opened at 9600 baud. | `helao/deploy/hte/servers/diapump/simdos_driver.py:171` |
| `address` | yes | int | none (KeyError on first command) | Pump RS-485 device address. Formatted with `:02`, so it must be an int, not a string. | `helao/deploy/hte/servers/diapump/simdos_driver.py:216` |

Example:
```yaml
params:
  port: COM7
  address: 0
```

## Outputs

### `run_continuous` (action)

`RunExec` (`helao/deploy/hte/servers/diapump/diapump_server.py:74`) returns no `data` from `_pre_exec`, `_exec` or `_poll` (`helao/deploy/hte/servers/diapump/simdos_driver.py:455`, `:466`, `:476`) and defines no `_post_exec`, so no data file is written and no action result is set.

No data files or action results.

### `cancel_run_continuous` (action)

No data files or action results.

### Private endpoints

`/start_polling`, `/stop_polling`, `/start_pump` and `/stop_pump` (`helao/deploy/hte/servers/diapump/diapump_server.py:43-61`) return nothing and write nothing; no data files or action results.

### Live data (status/ws stream)

`SIMDOSPoller.get_data` (`helao/deploy/hte/servers/diapump/simdos_driver.py:361-419`) publishes the decoded status registers of the pump each poll while `driver.polling` is true; it is never written to a file. Nothing is published while polling is paused or when no register answered. Each key is stamped `(value, epoch)` (`helao/hexagon/app/action_host.py:403`), so the stream value is `([label, bit], epoch)`:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `<group>_<i>` | str, int | list[str \| int] | none | `[label, bit]` of status bit `i`. `<group>` is `operation`, `system`, `run` or `dispense` (label picked from the `OPSTAT`/`SYSTAT`/`RUSTAT`/`DISTAT` table pair by the bit; empty string for unused bits) or `fault` (label is the `FADIAG` fault name when the bit is set, else `OK`). `<i>` is the bit index from the LSB (`0`-`7`; `0` only for `run`). A group whose register read fails (`None`) contributes no keys | `helao/deploy/hte/servers/diapump/simdos_driver.py:398`; tuples built at `:239` and `:265` |

A set fault bit also stops every executor on the server (`helao/deploy/hte/servers/diapump/simdos_driver.py:407-411`).
