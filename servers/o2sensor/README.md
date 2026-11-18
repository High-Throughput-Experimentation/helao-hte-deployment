# o2sensor

Action server for the CM-0134 dissolved-oxygen sensor on Modbus-RTU over a serial port: continuous O2 ppm acquisition.

## Vendor software

No vendor software beyond the env files. `pyserial` and `minimalmodbus` are in `environment.yml`.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `o2sensor_server` (`fast:`)

All keys are optional; the defaults are used when a key is absent.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `device` | no | str | `"COM7"` | Serial port, e.g. `COM7` or `/dev/ttyUSB0`. | `helao/deploy/hte/servers/o2sensor/cm0134_driver.py:75` |
| `address` | no | int | `254` | Modbus device address. | `cm0134_driver.py:76` |
| `baudrate` | no | int | `9600` | Serial baud rate. | `cm0134_driver.py:78` |
| `start_margin` | no | number | `0` | Stored on the driver; nothing else in the module reads it. | `cm0134_driver.py:58` |
| `allow_no_sample` | no | bool | `True` | Stored on the driver; nothing else in the module reads it. | `cm0134_driver.py:63` |

Example (no shipped station config uses this server; values are the defaults):
```yaml
params:
  device: COM7
  address: 254
  baudrate: 9600
```

Notes:
- `start_margin` and `allow_no_sample` are documented in the driver docstring but have no effect on the code paths in this folder.

## Outputs

### `acquire_o2` (action)

`O2MonExec` (`helao/deploy/hte/servers/o2sensor/o2sensor_server.py:77-82`; `action_abbr` is `O2`, `:76`) runs a non-one-off executor. Each `_poll` returns one row, which the executor runner queues through the framework default data connection (`helao/hexagon/app/executor_runner.py:129-136`): file `O2-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Columns are the keys of the first row (`helao/hexagon/adapters/native/data_stream.py:338-349`). Rows come from the live buffer filled by the poller below; the final poll (after `duration` elapses) is still written. If the buffer has never received an `o2_ppm` value, `get_lbuf` raises `KeyError` (`helao/hexagon/app/action_host.py:415`), the runner catches it (`helao/hexagon/app/executor_runner.py:122-126`), treats the poll as finished and writes no row. No action results.

Data file `O2-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `o2_ppm` | int | scalar per row | ppm | latest live-buffer reading | `helao/deploy/hte/servers/o2sensor/cm0134_driver.py:201` |
| `epoch_s` | float | scalar per row | s | epoch stamp of that live-buffer value | `helao/deploy/hte/servers/o2sensor/cm0134_driver.py:202` |

### `cancel_acquire_o2` (action)

No data files or action results.

### Live data (status/ws stream)

`CM0134Poller.get_data` (`helao/deploy/hte/servers/o2sensor/cm0134_driver.py:158-174`) publishes one reading per poll; it is never written to a file by the poller itself. Nothing is published when the read fails (`None`) or returns 0. Each key is stamped `(value, epoch)` (`helao/hexagon/app/action_host.py:403`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `o2_ppm` | int | scalar per poll | ppm | Modbus input register 1 times 10 | `helao/deploy/hte/servers/o2sensor/cm0134_driver.py:173` (register read `:143`) |
