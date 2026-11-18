# galil_io

Action server for the digital and analog IO of a Galil controller: digital in/out, analog in/out, DMC-program digital cycles, and an analog-input monitor.

## Vendor software

Install by hand (not pip/conda), on Windows or Linux:

1. The Galil gclib C library: the vendor installer on Windows, the Galil package
   repository on Linux (https://www.galil.com/sw/pub/all/doc/gclib/html/).
2. One gclib Python wrapper. Both install as `import gclib`, so an env holds one,
   and the server's `gclib_api` param must match it:
   - `gclib_api: "1"` (default): wrapper 1.0.1, the `gclib.py()` API, from the
     gclib installation's Python wrapper (gclib 2.4.1 Python docs). From the
     helao env on Windows:
     `python "C:\Program Files (x86)\Galil\gclib\source\wrappers\python\setup.py" install`.
     On Linux, run the same `setup.py install` from the `wrappers/python` folder
     of the gclib installation. Alternative (`setup.py install` is deprecated
     in current setuptools): `python -m pip install "<gclib install>/source/wrappers/python"`.
   - `gclib_api: "2"`: wrapper 2.x, the `gclib.Controller` API (Python >= 3.12):
     `pip install --upgrade --index-url https://www.galil.com/sw/pub/python gclib`
     (docs: https://www.galil.com/sw/pub/python/doc/index.html).
     Not yet verified at a station (reply trimming, gcaps bypass, unsolicited
     output without `-s ALL`): before using `"2"` in production, run
     `helao/deploy/hte/tests/smoke/golden_capture_galil.py` and
     `golden_capture_galil_io.py` with `"1"` and with `"2"` and diff the captures.

A mismatch fails at connect with a message naming `gclib_api`.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `galil_io` (`fast:`)

All keys are read by the `Galil` driver (`helao/deploy/hte/servers/galil_io/galil_io_driver.py`); `galil_io.py` itself reads none.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `galil_ip_str` | no (the server starts but is not connected without it) | str | `None` | Controller IP. `connect` opens `"<ip> --direct -s ALL"`. When empty or absent, `connect` logs "no Galil IP configured" and returns a failed response. | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:133` |
| `dev_ai` | no | dict[str, int] | `{}` | Analog-input channels, `{name: port}`. Names become the `dev_ai` action enum. Read with `MG @AN[port]`. | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:95` |
| `dev_ao` | no | dict[str, int] | `{}` | Analog-output channels, `{name: port}`. Names become the `dev_ao` enum. | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:104` |
| `dev_di` | no | dict[str, int] | `{}` | Digital-input channels, `{name: port}`. Read with `MG @IN[port]`; also the trigger names for digital cycles. | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:107` |
| `dev_do` | no | dict[str, int] | `{}` | Digital-output channels, `{name: port}`. Read and set with `@OUT[port]`; also the output names for digital cycles. | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:110` |
| `monitor_ai` | no | dict[str, number] | `{}` | `{ai_name: scale}` polled by `GalilPoller`; each raw reading is multiplied by `scale`. Names not present in `dev_ai` are dropped. | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:100` |
| `gclib_api` | no | str `"1"` or `"2"` (YAML int `1`/`2` accepted) | `"1"` | Which gclib Python wrapper API the env holds (see Vendor software). Any other value raises `ValueError` when the driver is constructed. | `helao/deploy/hte/servers/galil_motion/galil_channels.py:25` (called from `galil_io_driver.py:119`) |
| `connect_attempts` | no | int | `5` | How many times the driver's connect (open plus init queries) is tried at startup. `galil_io` and `galil_motion` on one controller open it together at launch, and the second can fail its first try. | `helao/deploy/hte/servers/galil_motion/galil_channels.py:59` |
| `connect_retry_wait_s` | no | float | `2.0` | Base wait between connect attempts; attempt *n* waits *n* x this (2, 4, 6, 8 s by default). | `helao/deploy/hte/servers/galil_motion/galil_channels.py:59` |

Example:
```yaml
params:
  galil_ip_str: 192.168.x.x
  gclib_api: "1"
  dev_ai:
    cell_pressure_psi: 1
  dev_di:
    gamry_ttl0: 1
  dev_do:
    spec_trig: 5
    we_pump: 7
  monitor_ai:
    cell_pressure_psi: 5.0
```

## Outputs

Actions here write through the framework default data connection: one JSON object per queued message, file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Columns are the keys of the first message queued (`helao/hexagon/adapters/native/data_stream.py:338-349`). Endpoints are registered only when the matching `dev_*` group is configured and the controller connected (`galil_enabled`: `helao/deploy/hte/servers/galil_io/galil_io.py:91`; `dev_ai` `:93`, `dev_ao` `:149`, `dev_di` `:174`, `dev_do` `:198`, `:222`; cycles `:301`, `:362`). Every `value` is the controller's raw string reply (`GCommand`), not parsed (`helao/deploy/hte/servers/galil_motion/galil_command_channel_port.py:33` is the channel contract; `command(cmd) -> str`).

### Single-channel IO rows: `get_analog_in`, `get_digital_in`, `get_digital_out`, `set_digital_out`, `set_analog_out` (actions)

Each calls the driver once and queues its returned dict as one row. `action_abbr` per endpoint: `get_ai` (`helao/deploy/hte/servers/galil_io/galil_io.py:102`), `get_di` (`:183`), `get_do` (`:207`), `set_do` (`:232`), `set_ao` (`:159`). Data file `<action_abbr>-*.jsonl` (+ `.meta.json`), one row:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `error_code` | str | scalar per row | none | `ErrorCodes` value: `none`, or `not_available` when `name` is not in the matching `dev_*` group (always `not_available` for `set_analog_out`, which is a placeholder) | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:240`, `:305`, `:336`, `:367`, `:406` |
| `port` | int | scalar per row | none | configured port number; `-1` when `name` is unknown | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:241`, `:306`, `:337`, `:368`, `:407` |
| `name` | str \| null | scalar per row | none | channel name as passed in (`null` if the endpoint item was omitted) | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:242`, `:307`, `:338`, `:369`, `:408` |
| `type` | str | scalar per row | none | `analog_in`, `digital_in`, `digital_out` or `analog_out` | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:243`, `:308`, `:339`, `:370`, `:409` |
| `value` | str \| null | scalar per row | none | `MG @AN[port]`, `MG @IN[port]` or `MG @OUT[port]` reply; for `set_digital_out` the readback after the set; `null` when the name is unknown or (for `set_analog_out`) always | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:244`, `:309`, `:340`, `:371`, `:410` |

Action results (in `-act.json`), set before the driver call from the endpoint's own item param:

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `ai_name` | `action_params` | str \| null | scalar | copy of `ai_item`; `get_analog_in` | `helao/deploy/hte/servers/galil_io/galil_io.py:104-106` |
| `ao_name` | `action_params` | str \| null | scalar | copy of `ao_item`; `set_analog_out` | `helao/deploy/hte/servers/galil_io/galil_io.py:161-163` |
| `di_name` | `action_params` | str \| null | scalar | copy of `di_item`; `get_digital_in` | `helao/deploy/hte/servers/galil_io/galil_io.py:185-187` |
| `do_name` | `action_params` | str \| null | scalar | copy of `do_item`; `get_digital_out` and `set_digital_out` | `helao/deploy/hte/servers/galil_io/galil_io.py:209-211`, `:234-236` |

### `acquire_analog_in` (action)

`AiMonExec` (`helao/deploy/hte/servers/galil_io/galil_io.py:127-133`); `action_abbr` is `galil_ai` (`:128`). Each `_poll` queues one row (`helao/deploy/hte/servers/galil_io/galil_io_driver.py:731-735`) from the live buffer filled by the poller below; data file `galil_ai-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `<ai_name>` | float \| null | scalar per row | as scaled by `monitor_ai` | one column per `monitor_ai` key; latest live-buffer value, `null` before the poller has published one | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:721` |
| `epoch_s` | float \| null | scalar per row | s | newest epoch stamp among the monitored values | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:723` |

No action results.

### `cancel_acquire_analog_in` (action)

No data files or action results.

### `set_digital_cycle` (action)

Uploads a generated DMC program (`helao/deploy/hte/servers/galil_io/galil_io_driver.py:425-627`) and queues one row, `{"error_code": ...}` (`:575`, `:627`; queued at `helao/deploy/hte/servers/galil_io/galil_io.py:358`); data file `<action_abbr>-*.jsonl` (+ `.meta.json`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `error_code` | str | scalar per row | none | `none` on success, `not_available` when a trigger or output name is missing from `dev_di`/`dev_do` (early return at `:575`) | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:627` |

### `stop_digital_cycle` (action)

Stops the cycle program; its row is commented out, so no data file is written (`helao/deploy/hte/servers/galil_io/galil_io.py:374`). The driver's `error_code` only sets the action's error code. No action results.

### `reset` (action)

Queues one row (`helao/deploy/hte/servers/galil_io/galil_io.py:388-393`); data file `reset-*.jsonl` (+ `.meta.json`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `reset` | str | scalar per row | none | `DriverResponseType` value of the driver reset | `helao/deploy/hte/servers/galil_io/galil_io.py:390` |
| `status` | str | scalar per row | none | `DriverStatus` value after the reset | `helao/deploy/hte/servers/galil_io/galil_io.py:391` |

### Live data (status/ws stream)

`GalilPoller.get_data` (`helao/deploy/hte/servers/galil_io/galil_io_driver.py:664-693`) publishes one scaled reading per `monitor_ai` channel at each poll, never written to a file by the poller itself. A channel whose read returns an error is left out; if none succeeds nothing is published. Each key is stamped `(value, epoch)` (`helao/hexagon/app/action_host.py:403`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `<ai_name>` | float | scalar per poll | as scaled by `monitor_ai` | `float(raw MG @AN reply) * scale` for each `monitor_ai` key | `helao/deploy/hte/servers/galil_io/galil_io_driver.py:685` |

### Private endpoints

`/get_digital_outs` and `/set_digital_out` return values to the caller only (`helao/deploy/hte/servers/galil_io/galil_io.py:257-298`); no data files or action results.

## Notes

- `visualizer/pressure_vis.py` also reads the `dev_ai` keys from this server's `params` to build its pressure display.
- The `.dmc` files in this folder are the DMC programs the digital-cycle actions upload.
