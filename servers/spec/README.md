# spec

Spectral Products SM303 USB spectrometer action server (`spec_server`, driver `SM303` in `spectral_products_driver.py`): externally triggered or timed spectrum acquisition, with panels `bokeh/spec_vis.py` and `reflex/spec_vis.py`.

## Vendor software
Install by hand (not pip/conda):

- Spectral Products SM32 USB software and SDK (Windows). The driver loads the SDK DLL with `ctypes.CDLL` from the `lib_path` param. Existing configs point at `C:\Spectral Products\SM32ProForUSB\SDK Examples\DLL\x64\stdcall\SPdbUSBm.dll`; the driver's own messages call the file `SMdbUSBm.dll`. Use the 64-bit `stdcall` DLL that matches the Python build.
- The driver fails to connect (status uninitialized, `spec` is `None`) if the file at `lib_path` does not exist.
- The code and docs do not say where Spectral Products distributes the installer.

## Params
Host-level keys every server accepts: see `docs/config-schema.md` ("Group conventions for `params:`").

### `spec_server` (`fast:` value)
| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `lib_path` | yes | string | none | Path of the SDK DLL. `KeyError` at startup if absent. | `helao/deploy/hte/servers/spec/spectral_products_driver.py:100`, `:142` |
| `dev_num` | yes | int | none | SDK device channel number (passed to every `sp*GivenChannel` call as `c_short`). `KeyError` at startup if absent. | `helao/deploy/hte/servers/spec/spectral_products_driver.py:103` |
| `n_pixels` | yes | int | none | Detector pixel count (1024 for the SM303). `KeyError` at startup if absent. After construction it is used only in log messages. | `helao/deploy/hte/servers/spec/spectral_products_driver.py:101`, `:263` |
| `start_margin` | yes | number (s) | none | Seconds added to the trigger duration when waiting for the trigger and when deciding the polling loop is complete. `KeyError` at startup if absent. | `helao/deploy/hte/servers/spec/spectral_products_driver.py:102`, `helao/deploy/hte/servers/spec/spec_server.py:94`, `:111` |
| `allow_no_sample` | no | bool | `False` | `True`: acquisition endpoints run without `samples_in`. `False`: a request with no sample in is rejected. | `helao/deploy/hte/servers/spec/spectral_products_driver.py:128`, `helao/deploy/hte/servers/spec/spec_server.py:459` |

Notes:
- The server sets `allow_concurrent_actions` to `False` in code (`helao/deploy/hte/servers/spec/spec_server.py:180`); the config value is overridden.
- The driver has commented-out reads of `wl_cal` and `px_cal`; they are not read.

Example:
```yaml
params:
  dev_num: 0
  lib_path: 'C:\Spectral Products\SM32ProForUSB\SDK Examples\DLL\x64\stdcall\SPdbUSBm.dll'
  n_pixels: 1024
  start_margin: 5
  allow_no_sample: true
```

### `spec_vis` (`action_vis:` / `live_vis:` panel, Bokeh and Reflex)
Reads no params of its own. The Reflex panel looks up the server's `host` and `port` in the config (`helao/deploy/hte/servers/spec/reflex/spec_vis.py:73`).

## Outputs

Actions here write through the framework default data connection: one JSON object per line, file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Columns are the keys of the first message queued (`helao/hexagon/adapters/native/data_stream.py:338-349`): a file whose first message is an error row (below) gets only `error_code` in its header `column_headings`, but later rows are dumped whole (`helao/hexagon/adapters/native/data_stream.py:361`), so its data lines still carry `ch_<n>` and `peak_intensity`. `action_abbr` is `OPT` for every acquisition endpoint (`helao/deploy/hte/servers/spec/spec_server.py:226`, `:282`, `:340`, `:428`). The `.meta.json` header carries `optional.wl`, the detector wavelength axis in nm (`list[float]`, read from the SM303 wavelength table: `helao/deploy/hte/servers/spec/spectral_products_driver.py:259-261`; attached at `spec_server.py:224-227`, `:281-283`, `:339-341`, `:466-473`). The spectrum has 1024 channels (`ch_0000`..`ch_1023`), the fixed slice `list(buf)[10:1034]` (`spectral_products_driver.py:411`) whatever `n_pixels` is.

### Spectrum row from `acquire_spec_adv` (software trigger)

Used by `acquire_spec`, `acquire_spec_adv` and `calibrate_intensity`. One row per spectrum, built by `SM303.acquire_spec_adv` (`helao/deploy/hte/servers/spec/spectral_products_driver.py:328`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `epoch_s` | float | scalar per row | s | Unix time the row was built | `helao/deploy/hte/servers/spec/spectral_products_driver.py:357` |
| `ch_<n>` (`ch_0000`..`ch_1023`) | int | scalar per row | detector counts | intensity of detector pixel `<n>`, 4-digit zero-padded index into the 1024-point read | `helao/deploy/hte/servers/spec/spectral_products_driver.py:358` |
| `error_code` | str | scalar per row | none | `ErrorCodes` value; `none` on a successful read | `helao/deploy/hte/servers/spec/spectral_products_driver.py:359` |
| `peak_intensity` | int | scalar per row | detector counts | maximum count among pixels whose wavelength lies in `[peak_lower_wl, peak_upper_wl]` (whole detector when a bound is absent) | `helao/deploy/hte/servers/spec/spectral_products_driver.py:375` |

A failed acquisition (trigger or integration time not set, no data, or an empty peak window) returns the one-field row `{"error_code": "not_available"}` instead (`spectral_products_driver.py:374`, `:379`, `:381`).

### `acquire_spec` (action)

Queues one spectrum row, then one more per loop pass until `duration_sec` elapses (`helao/deploy/hte/servers/spec/spec_server.py:230-237`); data file `OPT-*.jsonl` (+ `.meta.json`). Rows are the spectrum row above. The endpoint passes only `int_time_ms` and `duration_sec`, so `peak_intensity` covers the whole detector. No action results.

### `acquire_spec_adv` (action)

Same loop and rows as `acquire_spec` (`helao/deploy/hte/servers/spec/spec_server.py:285-292`), with `n_avg`, `fft`, `peak_lower_wl`, `peak_upper_wl` forwarded to the driver.

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `peak_intensity` | `action_params` | int \| null | scalar | `peak_intensity` of the last row; `null` when the last row was an error row | `helao/deploy/hte/servers/spec/spec_server.py:294` |

### `calibrate_intensity` (action)

Queues one spectrum row for the initial acquisition (`helao/deploy/hte/servers/spec/spec_server.py:344`) and one per integration-time adjustment (`:373`); data file `OPT-*.jsonl` (+ `.meta.json`). It reads `specdict["peak_intensity"]` unguarded (`:345`, `:374`), so an error row raises `KeyError` out of the endpoint.

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `int_time_ms` | `action_params` | int | scalar | the caller's input is overwritten with each adjusted integration time (`spec_params` is `action_params` itself, not a copy), so the recorded value is the last one tried | `helao/deploy/hte/servers/spec/spec_server.py:371` |
| `peak_intensity` | `action_params` | int | scalar | peak intensity of the last spectrum | `helao/deploy/hte/servers/spec/spec_server.py:379` |
| `calibrated_int_time_ms` | `action_params` | int | scalar | final integration time, capped at `max_integration_time` | `helao/deploy/hte/servers/spec/spec_server.py:380` |

### `acquire_spec_extrig` (action)

Externally triggered acquisition under `SM303Exec` (`helao/deploy/hte/servers/spec/spec_server.py:489-490`); file type `spec_helao__file` (`:472`). Each `_poll` that reads a spectrum queues one row (`helao/deploy/hte/servers/spec/spec_server.py:118-124`); a poll with no data queues nothing. Data file `OPT-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `epoch_s` | float | scalar per row | s | Unix time stamped before the read (`driver.spec_time`) | `helao/deploy/hte/servers/spec/spec_server.py:118` |
| `ch_<n>` (`ch_0000`..`ch_1023`) | int | scalar per row | detector counts | intensity of detector pixel `<n>` | `helao/deploy/hte/servers/spec/spec_server.py:119` |

No `error_code` or `peak_intensity` here. No action results.

### `stop_extrig_after` (action)

Queues one row `{"stop": <DriverResponse>}` after waiting `delay` seconds (`helao/deploy/hte/servers/spec/spec_server.py:516-522`); data file `<action_abbr>-*.jsonl` (+ `.meta.json`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `stop` | dict | dict | none | the driver's `DriverResponse` dataclass, serialised by field | `helao/deploy/hte/servers/spec/spectral_products_driver.py:442-444` |

Nested `stop` fields (`helao/core/drivers/helao_driver.py:73-80`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `response` | str | scalar | none | `DriverResponseType`; `success` | `helao/deploy/hte/servers/spec/spectral_products_driver.py:443` |
| `message` | str | scalar | none | empty | `helao/core/drivers/helao_driver.py:74` |
| `data` | dict | dict | none | `{}` | `helao/core/drivers/helao_driver.py:75` |
| `status` | str | scalar | none | `DriverStatus`; `ok` | `helao/deploy/hte/servers/spec/spectral_products_driver.py:443` |
| `timestamp` | str | scalar | none | ISO 8601 time the response was built | `helao/core/drivers/helao_driver.py:80` |

### `/get_wl` (private endpoint)

Returns `app.driver.pxwl` to the caller (`helao/deploy/hte/servers/spec/spec_server.py:189-192`); no data files or action results.

## Notes

- `calibrate_intensity` reads `specdict["peak_intensity"]` unguarded (`helao/deploy/hte/servers/spec/spec_server.py:345`, `:374`), but `acquire_spec_adv` returns `{"error_code": "not_available"}` without that key on a failed read (`helao/deploy/hte/servers/spec/spectral_products_driver.py:374`, `:379`, `:381`), so a failed read raises `KeyError`.
