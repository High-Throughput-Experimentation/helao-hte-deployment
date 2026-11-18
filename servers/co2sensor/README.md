# co2sensor

Action server for a SprintIR-6S NDIR CO2 sensor on a serial port. It polls CO2 ppm and records it on request (`acquire_co2`, `cancel_acquire_co2`). `bokeh/co2_vis.py` and `reflex/co2_vis.py` are its live visualizers (`live_vis: co2_vis`).

## Vendor software

No vendor software beyond the env files (`pyserial`, from `environment.yml`).

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `co2sensor_server` (`fast:`)

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `port` | yes | str | none (KeyError in `connect` if absent) | Serial port or device path of the sensor (for example `COM12` or `/dev/ttyUSB0`). Opened at 9600 baud. | `helao/deploy/hte/servers/co2sensor/sprintir_driver.py:82` |
| `start_margin` | no | number | `0` | Stored by the driver; nothing in this folder reads it (unused). | `helao/deploy/hte/servers/co2sensor/sprintir_driver.py:68` |

The Bokeh and Reflex visualizer modules read no server params.

Example:
```yaml
params:
  port: COM12
  start_margin: 0
```

## Outputs

### `acquire_co2` (action)

`CO2MonExec` (`helao/deploy/hte/servers/co2sensor/co2sensor_server.py:68-73`; `action_abbr` is `CO2`, `:67`) runs a non-one-off executor. Each `_poll` returns one row, which the executor runner queues through the framework default data connection (`helao/hexagon/app/executor_runner.py:129-136`): file `CO2-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Columns are the keys of the first row (`helao/hexagon/adapters/native/data_stream.py:338-349`). Rows come from the live buffer filled by the poller below; the final poll (after `duration` elapses) is still written. If the buffer has never received a `co2_ppm` value, `get_lbuf` raises `KeyError` (`helao/hexagon/app/action_host.py:415`), the runner catches it (`helao/hexagon/app/executor_runner.py:122-126`), treats the poll as finished and writes no row.

Data file `CO2-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `co2_ppm` | int | scalar per row | ppm | latest live-buffer reading | `helao/deploy/hte/servers/co2sensor/sprintir_driver.py:285` |
| `epoch_s` | float | scalar per row | s | epoch stamp of that live-buffer value | `helao/deploy/hte/servers/co2sensor/sprintir_driver.py:286` |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `mean_co2_ppm` | `action_params` | float | scalar | mean of the `co2_ppm` values of all polls; set at the end of the run and only when at least one poll succeeded | `helao/deploy/hte/servers/co2sensor/sprintir_driver.py:305` |

### `cancel_acquire_co2` (action)

No data files or action results.

### Live data (status/ws stream)

`SprintIRPoller.get_data` (`helao/deploy/hte/servers/co2sensor/sprintir_driver.py:213-253`) publishes one reading per poll; it is never written to a file by the poller itself. Nothing is published for a blank read, a parse error or a value outside `0 <= ppm < 1e6`. Each key is stamped `(value, epoch)` (`helao/hexagon/app/action_host.py:403`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `co2_ppm` | int | scalar per poll | ppm | `int(Z reading) * scaling_factor`, where `scaling_factor` is the int read from the sensor at connect | `helao/deploy/hte/servers/co2sensor/sprintir_driver.py:250` |
