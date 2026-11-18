# kinesis

Action server for Thorlabs Kinesis motors (one `KinesisMotor` per configured axis, via pylablib).

## Vendor software

Install by hand (not pip/conda):

- Thorlabs Kinesis software: installs the FTDI D2XX driver that `pyft232` (see requirements.txt) talks through. pylablib does not load Kinesis DLLs. The code does not say where to download it; Thorlabs distributes it.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `kinesis_server` (`fast:`)

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `axes` | yes | dict | none | `{axis_name: {...}}`; indexed without a default, so a missing key raises `KeyError` at startup. Axis names become the `axis` enum of `kmove`. An empty dict registers no motion endpoints. | `helao/deploy/hte/servers/kinesis/kinesis_server.py:175`, `kinesis_driver.py:77` |
| `axes.<axis>.serial_no` | yes | str | none | Device serial number, passed as `conn` to `Thorlabs.KinesisMotor`. | `kinesis_driver.py:90` |
| `axes.<axis>.pos_scale` | yes | float | none | Counts per mm. Also used by the UI and by `query_axis_positions` (missing or 0 gives mm `None`). | `kinesis_driver.py:85`, `kinesis_driver.py:163` |
| `axes.<axis>.vel_scale` | yes | float | none | Device units to mm/s, passed to pylablib `scale`. | `kinesis_driver.py:86` |
| `axes.<axis>.acc_scale` | yes | float | none | Device units to mm/s^2, passed to pylablib `scale`. | `kinesis_driver.py:87` |
| `axes.<axis>.move_limit_mm` | no | float | `3.0` | A move runs only when its target position is below this value; a target >= `move_limit_mm` is refused (logged, not moved). | `kinesis_server.py:119` |
| `warn_above_mm` | no | dict | `{}` | `{axis: mm}`. Read only by the `motion_control_inverse_scale` panel (`control_vis`): displacement above which a move asks for a second click. Falls back to `axes.<axis>.move_limit_mm`, then 10.0 mm. | `helao/ui/shared/motion_control.py:356` (fallback 10.0 at `:98`) |

Example:
```yaml
params:
  axes:
    z:
      serial_no: "49535954"
      pos_scale: 1228800.0  # device to mm
      vel_scale: 65970697.6  # device to mm/s
      acc_scale: 13518.2  # device to mm/s2
      move_limit_mm: 3.0
```

Notes:
- A failed `connect()` for one axis aborts the loop, so later axes are not opened (`kinesis_driver.py:83`).
- The limit check compares only against the upper bound; negative targets are not checked (`kinesis_server.py:119`).

## Outputs

The `kmove`, `cancel_kmove`, `set_velocity` and the private endpoints below exist only when the server has at least one Kinesis axis configured (`helao/deploy/hte/servers/kinesis/kinesis_server.py:177`; the private endpoints are registered inside the same block, `helao/deploy/hte/servers/kinesis/kinesis_server.py:291-453`).

### `kmove` (action)

`KinesisMotorExec` (`helao/deploy/hte/servers/kinesis/kinesis_server.py:215-220`; `action_abbr` is set to `kmove` at `:214`) is a non-one-off executor. Each `_poll` returns one row, which the executor runner queues through the framework default data connection (`helao/hexagon/app/executor_runner.py:129-136`): file `kmove-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). The row is read from the poller's live buffer; the poll that sees the axis no longer moving is still written. If the buffer has no entry for the axis, `get_lbuf` raises `KeyError` (`helao/hexagon/app/action_host.py:415`), the runner catches it (`helao/hexagon/app/executor_runner.py:122-126`), treats the poll as finished and writes no row. A call made while E-STOP is latched returns before a session exists and writes no artifact (`helao/deploy/hte/servers/kinesis/kinesis_server.py:209-212`). No action results (`_pre_exec`, `_exec` and `_manual_stop` return no `data`, and the executor has no `_post_exec`).

Data file `kmove-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `position_mm` | float | scalar per row | mm | axis position from the live buffer, rounded to 3 decimals | `helao/deploy/hte/servers/kinesis/kinesis_server.py:151` (value from `helao/deploy/hte/servers/kinesis/kinesis_driver.py:117`) |

### `cancel_kmove` (action)

No data files or action results.

### `set_velocity` (action)

Applies the velocity and acceleration to the axis. No data files or action results.

### Private endpoints

`/start_polling` and `/stop_polling` return a status string; `/move_axis`, `/stop_motion` and `/get_axis_positions` return `(error_code, payload)` to the caller (`helao/deploy/hte/servers/kinesis/kinesis_server.py:291-453`). No data files or action results.

### Live data (status/ws stream)

`KinesisPoller.get_data` (`helao/deploy/hte/servers/kinesis/kinesis_driver.py:325-328`) publishes `KinesisMotor.get_status()` each poll, never written to a file by the poller itself. One key per configured axis, `<axis>` being a key of the server's `axes` config; an axis for which the device returned nothing is left out, and if the whole status call raises nothing is published. Each key is stamped `(value, epoch)` (`helao/hexagon/app/action_host.py:403`) with `value` a dict. `KinesisMotorExec._poll` adds `epoch_s` to that stored dict in place (`helao/deploy/hte/servers/kinesis/kinesis_server.py:141-142`), so the live-buffer value carries `epoch_s` after the first `kmove` poll until the next publish replaces it:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `<axis>` | dict | dict | none | status dict of that axis (fields below) | `helao/deploy/hte/servers/kinesis/kinesis_driver.py:116` |

| key | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `position_mm` | float | scalar per poll | mm | position, rounded to 3 decimals | `helao/deploy/hte/servers/kinesis/kinesis_driver.py:117` |
| `velocity_mmpersec` | float | scalar per poll | mm/s | max velocity, rounded to 3 decimals | `helao/deploy/hte/servers/kinesis/kinesis_driver.py:118` |
| `acceleration_mmpersec2` | float | scalar per poll | mm/s^2 | acceleration, rounded to 3 decimals | `helao/deploy/hte/servers/kinesis/kinesis_driver.py:119` |
| `status` | str | list[str] | none | status flags reported by the device; any of `moving_fw`, `moving_bk`, `jogging_fw`, `jogging_bk`, `homing`, `active` marks motion (`MOTION_STATES`, `:45-52`) | `helao/deploy/hte/servers/kinesis/kinesis_driver.py:120` |
