# andor

Action server for an Andor Zyla camera with an optional spectrograph (`andor_server.py`): acquisition, sensor cooling, ND-filter adjustment and lamp wavelength calibration. `wl_source` selects one of two driver variants (`spectrograph.py`, `calibrated.py`) on a shared base (`driver.py`). `reflex/andor_vis.py` is its Reflex panel. Design notes: `CLAUDE.md` in this folder.

## Vendor software

Install by hand (not pip/conda):

- Andor SDK3, with the `pyAndorSDK3` wheel from the SDK. Both variants need it; the driver imports it lazily in `connect()` (`driver.py:41`).
- The `pyAndorSpectrograph` wheel from the SDK. Only `wl_source: spectrograph` (the default) needs it; `spectrograph.py` is the only module that imports it (`spectrograph.py:31`). A station with `wl_source: calibration` does not need it.

The code does not say where the SDK is downloaded from. Take both wheels from the Andor SDK installation.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `andor_server` (`fast:`)

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `wl_source` | no | str | `"spectrograph"` | Driver variant. `"spectrograph"`: wavelength axis from the ATSpectrograph `GetCalibration`. `"calibration"`: axis from a lamp-calibration fit persisted under `<STATES>`; no spectrograph needed. Any other value raises `ValueError` when the app is built. | `helao/deploy/hte/servers/andor/andor_server.py:548` |
| `dev_id` | no | int | `0` | Index of the camera to open through the SDK. | `helao/deploy/hte/servers/andor/driver.py:130` |
| `states_root` | no | str (path) | `"STATES"` (cwd-relative, logs a WARNING) | Directory holding the persisted wavelength calibration file. Used only when the host provides no `states_root` of its own; the host value wins. | `helao/deploy/hte/servers/andor/driver.py:166` |
| `host` | no | str | `socket.gethostname()` | Host name used in the calibration file name `<host>_<server_key>_andor_wl_calib.json`. | `helao/deploy/hte/servers/andor/driver.py:174` |

The Reflex module `reflex/andor_vis.py` reads no server params.

Example:
```yaml
params:
  dev_id: 0
  wl_source: spectrograph
```

## Outputs

Every action here writes through the framework default data connection: one JSON object per queued message, file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). `Executor` actions queue the `data` dict returned by `_exec`, each `_poll` and `_post_exec` as one row (`helao/hexagon/app/executor_runner.py:110-117`, `:129-136`, `:157-164`); an empty dict queues nothing. Without declared `json_data_keys` the columns are the keys of the first message queued (`helao/hexagon/adapters/native/data_stream.py:338-349`). The wavelength axis depends on `wl_source`, but every row table below is identical for `spectrograph` and `calibration`, except where stated.

### `acquire` (action)

Runs `AndorAcquire` (`helao/deploy/hte/servers/andor/andor_server.py:404`); `action_abbr` is `ANDORSPEC` (`andor_server.py:403`). Each `_poll` that receives frames queues one row holding that poll's batch, so each value is a list with one entry per frame (up to `frames_per_poll`) (`andor_server.py:295`). Refused with no file when the driver has no wavelength axis (`andor_server.py:362-374`).

Data file `ANDORSPEC-*.jsonl` (+ `.meta.json`), one row per poll:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `tick_time` | float | list[float] | s | camera hardware timestamp of each frame (`timestamp / clock_hz`) | `helao/deploy/hte/servers/andor/driver.py:1000-1001` |
| `ch_<n>` (`ch_0000`..) | int | list[int] | detector counts | intensity of detector column `<n>` per frame; `<n>` runs over `range(wl_arr.size)`, zero-padded to 4 digits, `wl_arr` being the driver's live wavelength axis (width of the sensor) | `helao/deploy/hte/servers/andor/driver.py:1003-1004` |

`.meta.json` header, set at `andor_server.py:379-387`: `column_headings` is `["elapsed_time_s", "ch_0000", ...]` and `optional.wl` is `list[float]`, the wavelength axis in nm (the channel index `0..n-1` when `calibrated` is `False`). `elapsed_time_s` is declared in the header but no row carries it: rows carry `tick_time` (see Notes).

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `action_path` | `action_output` | str | scalar | `action_output_dir` of the action | `helao/deploy/hte/servers/andor/andor_server.py:224` |
| `calibrated` | `action_output` | bool | scalar | `False` when the wavelength axis is the channel index, `True` for a real calibration; written on both paths | `helao/deploy/hte/servers/andor/andor_server.py:390` |

### `cancel_acquire` (action)

No data files or action results.

### `reset_camera_state_for_triggered_aq` (action)

No data files or action results.

### `cooling` (action)

Runs `AndorCooling` (`helao/deploy/hte/servers/andor/andor_server.py:449`). Each `_poll` queues one row (`andor_server.py:104-108`); the data file is `<action_abbr>-*.jsonl` (+ `.meta.json`). A poll with no temperature reading or a `Fault` status returns `errored` and ends the action with `critical_error` (`andor_server.py:87-96`), queueing no row.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `sensor_temp__C` | float | scalar per row | degC | sensor temperature at the poll | `helao/deploy/hte/servers/andor/andor_server.py:107` |

No action results.

### `adjust_nd` (action)

Refused with no data when the driver is not the spectrograph variant (`wl_source: calibration`; `andor_server.py:458-466`). Otherwise `AndorAdjustND._exec` queues one row (`andor_server.py:143`) from `AndorSpectrographDriver.adjust_ND`; the data file is `<action_abbr>-*.jsonl` (+ `.meta.json`). The row is `{}` (so nothing is queued) when the spectrograph does not initialise, and `max_array` and `optimality_array` stay zero when no filter wheel is present.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `max_array` | float | array[float, 6] | detector counts | maximum pixel value measured with ND filter 1..6 | `helao/deploy/hte/servers/andor/spectrograph.py:287` |
| `optimality_array` | float | array[float, 6] | none | `1 + abs(63000 - max) / 63000` per filter; the chosen filter is the argmin, with over-range (max above 54000) entries replaced by `999` | `helao/deploy/hte/servers/andor/spectrograph.py:288` |
| `ND_filter_num` | int \| null | scalar | none | 0-based index of the chosen filter (the wheel is set to this + 1); `null` when no filter wheel is present | `helao/deploy/hte/servers/andor/spectrograph.py:289` |

No action results.

### `calibrate_wl` (action)

Runs `AndorCalibrateWavelength` (`helao/deploy/hte/servers/andor/andor_server.py:517`, `:176-196`); queues one row from `AndorDriver.run_wl_calibration` (`andor_server.py:196`), data file `<action_abbr>-*.jsonl` (+ `.meta.json`). The row is `{"applied": false}` plus the keys listed under "refused" when the fit is rejected, and `{}` (nothing queued) after an unexpected exception (`driver.py:433-436`).

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `coeffs` | float | list[float] | nm (Chebyshev coefficients) | fitted calibration coefficients; success only | `helao/deploy/hte/servers/andor/driver.py:423` |
| `fit_rms_nm` | float | scalar | nm | fit residual RMS; success, and the two quality-gate refusals (`:379`, `:392`) | `helao/deploy/hte/servers/andor/driver.py:424` |
| `n_lines` | int | scalar | none | lines used in the fit; success and the same refusals | `helao/deploy/hte/servers/andor/driver.py:425` |
| `lamp` | str | scalar | none | calibration lamp name; success only | `helao/deploy/hte/servers/andor/driver.py:426` |
| `path` | str | scalar | none | calibration file written; success only | `helao/deploy/hte/servers/andor/driver.py:427` |
| `applied` | bool | scalar | none | `self.uses_lamp_calibration`: `True` on the `calibration` variant, `False` on the spectrograph variant and on every refusal. It is `True` even if the live axis was not refreshed because `_wavelengths()` returned `None` (`helao/deploy/hte/servers/andor/driver.py:410-416`) | `helao/deploy/hte/servers/andor/driver.py:428`, `:292` |
| `max_fit_rms_nm` | float | scalar | nm | the gate that was exceeded; "residual too large" refusal only | `helao/deploy/hte/servers/andor/driver.py:380` |
| `degree` | int | scalar | none | fit degree; "axis not monotonic" refusal only | `helao/deploy/hte/servers/andor/driver.py:394` |

Calibration file `<states_root>/<host>_<server_key>_andor_wl_calib.json` (the previous one is first copied to `<same name>.prev`), written when the fit clears both gates (`helao/deploy/hte/servers/andor/wl_calibration.py:120-126`, call site `driver.py:398`):

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| calibration | indented JSON, one object with the `WavelengthCalibration` fields `model` (str), `coeffs` (list[float]), `n_pixels` (int), `fit_rms_nm` (float), `n_lines` (int), `lamp` (str), `created` (str), `source_action_uuid` (str or null), `domain` (list[float] or null), `medium` (str), `n_rejected` (int), `n_saturated` (int), `max_residual_nm` (float), `wl_source` (str) | `<host>_<server_key>_andor_wl_calib.json` | the persisted pixel-to-nm mapping read at `connect()` on the `calibration` variant | `helao/deploy/hte/servers/andor/wl_calibration.py:125` |

No action results.

### `/set_wl_from_pairs` (private endpoint, not an action)

Writes no action record and no data file; it writes the same calibration file (`helao/deploy/hte/servers/andor/driver.py:246`, `wl_calibration.py:125`) and returns the driver's response dict (`andor_server.py:652-656`). Its `data` carries `coeffs`, `domain`, `degree`, `n_pairs`, `fit_rms_nm`, `max_residual_nm`, `wl_min_nm`, `wl_max_nm`, `path`, `applied` (`driver.py:260-273`).

`/get_wl`, `/stop_private`: no data files or action results.

## Notes

- `andor_dyn_endpoints` writes `server_params["allow_concurrent_actions"] = False` at startup (`andor_server.py:323`); a config value for it is overwritten.
- `driver.py:158-165` says a driver built as `driver_class(config=self.server_params)` has no `_base_hook`, so `states_root` may fall through to the cwd-relative default. Whether that happens in a launched server was not checked here; set `states_root` explicitly if the WARNING appears.
- `acquire` declares `elapsed_time_s` as the first column in the header (`helao/deploy/hte/servers/andor/andor_server.py:376`, `:384`), but `AndorDriver.get_data` queues `tick_time` (`helao/deploy/hte/servers/andor/driver.py:1001`); the rows never contain `elapsed_time_s`.
- `CLAUDE.md` in this folder still says `/ANDOR/adjust_nd` has never worked because `AndorAdjustND` binds no driver; the class now binds it in its `__init__` (`helao/deploy/hte/servers/andor/andor_server.py:132`).
