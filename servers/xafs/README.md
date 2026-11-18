# xafs

easyXAFS spectrometer action server (`xafs_server`): runs wafer-grid XAFS scans by driving a separate sidecar process over loopback HTTP. The sidecar (`sidecar/xafs_sidecar.py`, Python 3.9) owns the hardware and the vendor `easyxafs` package. `driver.py` is the HTTP client (`XafsSidecarDriver`). `naming.py` builds savenames and applies the plate-to-stage affine.

## Vendor software
The sidecar needs packages that no env file installs. It runs in its own Python 3.9 environment, not the `helao` env.

- `easyxafs`: the instrument's vendor package (modules `ketek`, `monochromator`, `scan`, `wafer_stage_motor_control`, `xchanger_control`). Take it from the instrument computer's easyxafs checkout. The code and docs do not say where else it is distributed.
- `pyprotohv`: imported by `sidecar/runner.py` (and named in `sidecar/hardware.py`). Source not documented; take it from the instrument computer's easyxafs environment.
- `easyxafs_xray_utils` 1.1.0 (wheel) and the `hklhop` package: per `sidecar/environment-sim.yml`, both come from the instrument's easyxafs environment; `hklhop` is not on PyPI (copy its directory into the env's `site-packages`).
- For the simulator (`simulate: true`): `sidecar/environment-sim.yml` creates the Python 3.9 conda env `easyxafs-sim`. After `conda env create`, install the `easyxafs_xray_utils` wheel, copy `hklhop`, and make the `easyxafs` checkout importable with a `.pth` file in the env's `site-packages` (steps are in the comments of that file). The simulator stubs the vendor hardware modules, so no device drivers are needed.
- Hardware SDKs behind `easyxafs` (monochromator, KETEK detector, wafer stage, X-changer) are not referenced by this repo's code. If they need separate vendor installers, that is not documented here.

## Params
Host-level keys every server accepts: see `docs/config-schema.md` ("Group conventions for `params:`").

### `xafs_server` (`fast:` value)
| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `sidecar_port` | yes | int | none | TCP port of the sidecar HTTP API. `connect()` fails with "missing sidecar_port in config" if absent. | `helao/deploy/hte/servers/xafs/driver.py:54`, `:139` |
| `sidecar_host` | no | string | `"127.0.0.1"` | Host the driver calls. The sidecar itself always binds `127.0.0.1`. | `helao/deploy/hte/servers/xafs/driver.py:58` |
| `spawn_sidecar` | no | bool | `False` | `True`: if `/health` does not answer, start the sidecar subprocess and wait for it; the driver shuts down a sidecar it spawned on disconnect. `False`: connect fails if the sidecar is not already running. | `helao/deploy/hte/servers/xafs/driver.py:55`, `:145` |
| `sidecar_python` | when spawning | string | none | Python executable of the sidecar's 3.9 env. Missing: the spawn fails ("could not spawn sidecar"). | `helao/deploy/hte/servers/xafs/driver.py:155` |
| `sidecar_script` | when spawning | string | none | Path of `xafs_sidecar.py`. Missing: the spawn fails. | `helao/deploy/hte/servers/xafs/driver.py:156` |
| `sidecar_args` | no | list of string | `[]` | Extra command-line arguments for the sidecar (it accepts `--simulate`, `--lock-file`, `--state-dir`). | `helao/deploy/hte/servers/xafs/driver.py:149` |
| `simulate` | no | bool | `False` | Adds `--simulate` to a spawned sidecar. On connect, the driver compares it with the running sidecar's `simulate` flag and fails on a mismatch, also for a sidecar that was already running. | `helao/deploy/hte/servers/xafs/driver.py:105`, `:151` |
| `request_timeout` | no | number (s) | `10.0` | Timeout of each HTTP call to the sidecar. | `helao/deploy/hte/servers/xafs/driver.py:56` |
| `spawn_wait_s` | no | number (s) | `30.0` | How long to poll `/health` after spawning before giving up. | `helao/deploy/hte/servers/xafs/driver.py:57` |
| `references` | for `run_use` `izero` / `energy_calib` | dict | `{}` | `{reference_name: {x_mm: float, y_mm: float}}`: stage position of each reference pellet. A `reference_name` not in this dict raises a scan-setup error. | `helao/deploy/hte/servers/xafs/xafs_server.py:153`, `:159` |
| `platexy_to_stage` | for `run_use` `data` | 2x3 list of float | none | Affine matrix `[[a, b, tx], [c, d, ty]]` mapping plate XY (mm) to stage XY (mm). `KeyError` on the first `data` scan if absent. | `helao/deploy/hte/servers/xafs/xafs_server.py:185`, `helao/deploy/hte/servers/xafs/naming.py:27` |

Notes:
- The server sets `allow_concurrent_actions` to `False` in code (`helao/deploy/hte/servers/xafs/xafs_server.py:399`); the config value is overridden.
- `platexy_to_stage` is read for every sample scan but the one existing station config sets none. A `run_use: data` scan with that config fails with `KeyError`. Reported, not changed.

Example:
```yaml
params:
  sidecar_port: 18765
  spawn_sidecar: true
  simulate: false
  sidecar_python: 'C:/Users/<user>/anaconda3/envs/easyxafs_env/python.exe'
  sidecar_script: helao/deploy/hte/servers/xafs/sidecar/xafs_sidecar.py
  references:
    Fe2O3_pellet: {x_mm: 55.4, y_mm: -32.0}
    ZnO_film: {x_mm: 53.9, y_mm: 31.4}
  platexy_to_stage:
    - [1.0, 0.0, 0.0]
    - [0.0, 1.0, 0.0]
```

Unused keys seen in configs: `save_root` (no code in this folder reads it; the sequence library takes `save_root` as a sequence param).

## Outputs

Rows and action results are produced by the Python 3.9 sidecar and the vendor `easyxafs` package, which are not importable from the `helao` env and whose scan columns and metadata are defined by the vendor; those fields are typed `unknown (dynamic)` with the reason given. Data files go through the framework default data connection: one JSON object per queued message, file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`).

### `normal_scan` (action)

`XafsScanExec` (`helao/deploy/hte/servers/xafs/xafs_server.py:73`, started at `:489-497`); `action_abbr` is `xafs_normal` and file type `xafsscan__helao_file` (`:466-467`). During the run `_poll` and `_post_exec` call `_drain`, which queues every new sidecar row as one data row, one per scan point (`xafs_server.py:211-217`). The `.meta.json` header carries `optional.scan_def` (dict, the caller's `scan_def` param; `:468`). A scan stopped by the operator before the first point queues no rows and no `exd_path`.

Data file `xafs_normal-*.jsonl` (+ `.meta.json`), one row per scan point:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `<column>` | unknown (dynamic) | scalar per row | unknown (dynamic) | one key per name in the vendor scan's `data_headers[:-1]` followed by its `encoder_header`; the names are fixed by the installed `easyxafs` version, so neither names nor types are knowable from this repo | `helao/deploy/hte/servers/xafs/xafs_server.py:213`; names set at `helao/deploy/hte/servers/xafs/sidecar/runner.py:246`, `:273` |

The row dict is `dict(zip(columns, row))` over the sidecar's `/scans/<id>/rows` response (`helao/deploy/hte/servers/xafs/sidecar/runner.py:325-331`).

Files:

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| exd archive | vendor zip of csv files, plus `metadata.json` | `<savename>_<counter:03d>_exd.csv.zip` in the `save_dir` param | the vendor's own scan record; saved by `easyxafs` after the scan completes (the path is returned as `exd_path`) | `helao/deploy/hte/servers/xafs/sidecar/runner.py:227` (the `savename` it is built from) |
| recorded marker | empty file | `.helao_recorded` in `save_dir` | created before the scan starts | `helao/deploy/hte/servers/xafs/xafs_server.py:228` |
| MCA arrays | numpy `.npz` bytes, copied from the `*_mcas.npz` member of the exd archive, tracked as `xafsmca__npz_file`; array names and shapes are set by the vendor | `xafs_mca-<savename>.npz` in the action output directory | per-point MCA spectra | `helao/deploy/hte/servers/xafs/xafs_server.py:378-382` |
| track json | JSON, written as `xafstrack__json_file` from `scan_def["advanced_calibration"]`; skipped with a warning when that key is absent | `xafs_track-<savename>.json` in the action output directory | the scan's advanced calibration record | `helao/deploy/hte/servers/xafs/xafs_server.py:384-392` |

`<savename>` is `<element>_Scan<scan_index:04d>_Sample<sample_no>_X<x:.3f>_Y<y:.3f>` for `run_use: data` (`helao/deploy/hte/servers/xafs/naming.py:13-16`) and `<element>_EnergyCalib_<reference_name>` or `<element>_IzeroRef_<reference_name>` for the reference runs (`naming.py:19-24`).

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `scan_state` | `action_params` | str | scalar | final sidecar state (`done`, `stopped`, `error`, ...); present once the sidecar reports a terminal state | `helao/deploy/hte/servers/xafs/xafs_server.py:347` |
| `n_points` | `action_params` | int | scalar | points the sidecar recorded | `helao/deploy/hte/servers/xafs/xafs_server.py:347` |
| `n_expected` | `action_params` | int | scalar | points the scan was expected to record | `helao/deploy/hte/servers/xafs/xafs_server.py:347` |
| `exd_path` | `action_params` | str \| null | scalar | path of the exd archive; `null` when the operator stopped before the first point; absent when the scan did not end cleanly | `helao/deploy/hte/servers/xafs/xafs_server.py:357` |
| `sidecar_error` | `action_params` | str | scalar | error text; present only when setup, start, polling or finishing failed | `helao/deploy/hte/servers/xafs/xafs_server.py:106`, `:231`, `:235`, `:240`, `:335`, `:350` |
| `<metadata key>` | `action_params` | unknown (dynamic) | scalar | every key of the exd archive's `metadata.json`, merged in after a successful scan; the vendor writes that file, so the keys and types are not in this repo | `helao/deploy/hte/servers/xafs/xafs_server.py:393` |

### `initialize`, `calibrate`, `status`, `set_xray`, `shutter` (actions)

Each queues one row `{<key>: <sidecar response data>, "message": <str>}` through `finish_with` (`helao/deploy/hte/servers/xafs/xafs_server.py:408-416`) and finishes; `<key>` is the action name. Data file `<action_abbr>-*.jsonl` (+ `.meta.json`), one row. A `shutter` call with `state` other than `open`/`close` writes no row (`:572-577`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `initialize` | dict | dict | none | device name -> `"ok"` or `"<ExceptionType>: <message>"` for `mono`, `ketek`, `wafer_stage`, `xchanger`, `proto` (only the devices requested) | `helao/deploy/hte/servers/xafs/xafs_server.py:414`; values `helao/deploy/hte/servers/xafs/sidecar/hardware.py:77-91` |
| `calibrate` | dict | dict | none | the calibration job record, `{"state": "running" \| "done" \| "error", "error": str \| null}` | `helao/deploy/hte/servers/xafs/xafs_server.py:414`; job at `helao/deploy/hte/servers/xafs/sidecar/xafs_sidecar.py:171-174` |
| `status` | dict | dict | none | `{"health": {easyxafs_version, python, pid, hw_initialized, simulate}, "hw": {mono_calibrated, mono_positions, mono_bragg, wafer_xy, xchanger_station, proto, scan_id}}`; field types are those in `sidecar/xafs_sidecar.py:136-142` and `sidecar/hardware.py:109-127` | `helao/deploy/hte/servers/xafs/xafs_server.py:553`, `:414` |
| `set_xray` | dict | dict | none | `{"kv", "ma", "shutter"}` read back from the X-ray controller; types come from the vendor `pyprotohv` | `helao/deploy/hte/servers/xafs/xafs_server.py:414`; `helao/deploy/hte/servers/xafs/sidecar/hardware.py:153` |
| `shutter` | dict | dict | none | same `{"kv", "ma", "shutter"}` dict as `set_xray` | `helao/deploy/hte/servers/xafs/xafs_server.py:414`; `helao/deploy/hte/servers/xafs/sidecar/hardware.py:153` |
| `message` | str | scalar | none | the driver's response message (empty on success) | `helao/deploy/hte/servers/xafs/xafs_server.py:414` |
