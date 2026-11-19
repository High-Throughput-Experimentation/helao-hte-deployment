# galil_motion

Action server for Galil-controlled motion stages (`galil_motion.py`, backed by `NativeGalilMotion` in `galil_motion_native.py`): axis moves and queries, plate-alignment and coordinate transforms, and an optional Bokeh plate aligner (`galil_aligner_host.py`).

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

### `galil_motion` (`fast:`)

Read by `galil_motion.py` (the server), `NativeGalilMotion` (the driver, constructed with `config=server_params`), `GalilAlignerHost`, and the Bokeh aligner layout.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `galil_ip_str` | yes in practice | str | `None` | Controller IP. When empty or absent, `connect` leaves the driver `uninitialized` and the motion endpoints are not registered. Opened as `"<ip> --direct -s ALL"`. | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:161` |
| `axis_id` | yes in practice | dict[str, str] | `{}` | Map of HELAO axis name to Galil axis letter, for example `{x: B, y: A}` or `{x: C, y: B, z: A, Rz: D}`. When empty, no motion endpoints are registered. | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:105`, `helao/deploy/hte/servers/galil_motion/galil_motion.py:126` |
| `count_to_mm` | no | dict[str, float] | `{}` | Millimetres per encoder count, keyed by Galil axis letter. A missing letter reads as 0 in `query_axis_position`, as `None` in the counts query, and raises `KeyError` in a move. | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:317`, `:375`, `:605`, `:623` |
| `axis_zero` | no (required by `setmotionref`) | dict[str, float] | none (KeyError) | Zero position in mm, keyed by Galil axis letter. Read only by the `setmotionref` homing sequence. | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:793` |
| `timeout` | no | number (s) | `60` | Motor move timeout. | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:117` |
| `max_speed_count_sec` | no | int | `25000` | Maximum speed in counts per second; move speeds are clamped to it. | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:118` |
| `def_speed_count_sec` | no | int | `10000` | Default speed in counts per second. | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:121` |
| `M_instr` | no | 4x4 list of numbers | identity matrix | Instrument transform used when no instrument calibration file is found. Logs a warning when neither exists. | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:240`, `:243` |
| `z_height_mm` | no | dict[str, float] | `{}` | Named z heights in mm. Each key becomes a `z_position` choice of the `z_move` action; the server adds a `NA` key (no-op). Only read when `axis_id` is non-empty. | `helao/deploy/hte/servers/galil_motion/galil_motion.py:588` |
| `enable_aligner` | no | bool | `False` | Start the Bokeh plate aligner (`/Aligner`) when the controller connected. | `helao/deploy/hte/servers/galil_motion/galil_motion.py:110` |
| `bokeh_port` | no | int or null | `port + 1000` of the server block | Port of the aligner Bokeh server. Null counts as unset. | `helao/hexagon/preflight.py:109` (used by `galil_aligner_host.py:163`) |
| `cutoff` | no | number | `6` | Aligner layout cutoff value, wrapped in `np.array`. | `helao/deploy/hte/layouts/aligner.py:129` |
| `gclib_api` | no | str `"1"` or `"2"` (YAML int `1`/`2` accepted) | `"1"` | Which gclib Python wrapper API the env holds (see Vendor software). Any other value raises `ValueError` at driver construction. | `helao/deploy/hte/servers/galil_motion/galil_channels.py:25` |
| `connect_attempts` | no | int | `5` | How many times the driver's connect (open plus init queries) is tried at startup. `galil_io` and `galil_motion` on one controller open it together at launch, and the second can fail its first try. | `helao/deploy/hte/servers/galil_motion/galil_channels.py:59` |
| `connect_retry_wait_s` | no | float | `2.0` | Base wait between connect attempts; attempt *n* waits *n* x this (2, 4, 6, 8 s by default). | `helao/deploy/hte/servers/galil_motion/galil_channels.py:59` |

Example:
```yaml
params:
  galil_ip_str: 192.168.x.x
  gclib_api: "1"
  enable_aligner: true
  bokeh_port: 5003
  axis_id:
    x: B
    y: A
  count_to_mm:
    A: 0.00015625
    B: 0.00015625
  axis_zero:
    A: 127.8
    B: 76.7
  def_speed_count_sec: 10000
  max_speed_count_sec: 25000
  timeout: 600
  M_instr:
    - [1, 0, 0, 0]
    - [0, 1, 0, 0]
    - [0, 0, 1, 0]
    - [0, 0, 0, 1]
```

## Outputs

Actions here write through the framework default data connection: one JSON object per queued message, file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Columns are the keys of the first message queued (`helao/hexagon/adapters/native/data_stream.py:338-349`). Motion endpoints are registered only when `axis_id` is configured and the controller connected (`helao/deploy/hte/servers/galil_motion/galil_motion.py:126`); an action without an `action_abbr` below uses the framework default.

### Move result row: `move`, `easymove`, `easymove_to_solid`, `z_move` (actions)

Each calls `NativeGalilMotion.motor_move`, which reads `d_mm`, `axis`, `speed`, `mode`, `transformation` from `action_params` (`helao/deploy/hte/servers/galil_motion/galil_motion_native.py:807-839`) and returns the dict below; it is queued as one row. `action_abbr`: `move` (`helao/deploy/hte/servers/galil_motion/galil_motion.py:290`), `move` for `easymove` (`:314`), `z_move` (`:605`); `easymove_to_solid` has none. Data file `<action_abbr>-*.jsonl` (+ `.meta.json`), one row; each field is a list with one entry per moved axis (`galil_motion_native.py:746-752`); a move that times out still writes its row, with `timeout` in `err_code` (see below):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `moved_axis` | str \| null | list[str \| null] | none | Galil axis letter moved; `null` for an axis that was refused | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:746`, `:665` |
| `speed` | int \| null | list[int \| null] | counts/s | speed used, after default and clamp | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:747`, `:666` |
| `accepted_rel_dist` | null | list[null] | none | always `null` | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:748`, `:667` |
| `supplied_rel_dist` | float | list[float] | mm (counts under a counts move) | the requested distance of that axis; an axis not in `axis_id` is dropped together with its distance and logged as a WARNING | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:749`, `:668` |
| `err_dist` | float \| null | list[float \| null] | mm | rounding remainder of the mm to counts conversion (`0.0` for counts moves) | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:750`, `:669` |
| `err_code` | str | list[str] | none | `ErrorCodes` value per axis: `none`, `numerical`, `motor`, `timeout`, or, when every axis reported `stopped`, the final `query_axis_moving` code for an axis whose move code was `none` (`galil_motion_native.py:726-736`; so it is `none` in practice; the one other value is `not_available` for every axis when the controller was disabled mid-move, where the query returns a scalar, `:400`. An axis missing from the `SC` reply reports `invalid` (`:418-419`), never settles, and is marked `timeout` as below); `estop` for every axis if E-stopped (`:740`). A move whose axes are not all `stopped` by `timeout` (config, default 60 s) is halted (`ST`) and logged as an ERROR (`motion timeout: axes ... not stopped after ... s`); every axis not seen `stopped` (including an `invalid` one) gets `timeout`, an axis seen `stopped` keeps its code (`galil_motion_native.py:711-723`). The row is written and the action returns normally, so its `error_code` is `timeout` (non-`none`) and an orchestrator E-STOPs | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:751`, `:670` |
| `counts` | int \| null | list[int \| null] | counts | counts commanded to `PR`/`PA` | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:752`, `:671` |

A move refused before any axis runs (`in_progress` at `:492-499` and `:831-839`, `estop` at `:588-595`; the `not_available` branch at `:560-567` is the counts-mode refusal and cannot be reached through `motor_move`, which always passes `units="mm"`, `:807-830`) returns the same keys with every value `null` except `err_code`, which is then a scalar `str` instead of a list. The per-axis `null` entries come from the `numerical` (`helao/deploy/hte/servers/galil_motion/galil_motion_native.py:633-641`) and `motor` (`:678-684`) failure branches.

Action results (in `-act.json`): `easymove_to_solid` and `z_move` rewrite the inputs before moving:

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `d_mm` | `action_params` | float | list[float] | `easymove_to_solid`: the sample's plate XY; `z_move`: `[z_value]` from the `z_height_mm` config | `helao/deploy/hte/servers/galil_motion/galil_motion.py:343-348`, `:611-617` |
| `axis` | `action_params` | str | list[str] | `["x", "y"]` for `easymove_to_solid`, `["z"]` for `z_move` | `helao/deploy/hte/servers/galil_motion/galil_motion.py:343-348`, `:611-617` |
| `mode` | `action_params` | str | scalar | `absolute` | `helao/deploy/hte/servers/galil_motion/galil_motion.py:343-348`, `:611-617` |
| `transformation` | `action_params` | str | scalar | `platexy` for `easymove_to_solid` only; `z_move` leaves the caller's value | `helao/deploy/hte/servers/galil_motion/galil_motion.py:343-348` |

`easymove_to_solid` queues no row and sets `error_code` `not_available` when the sample has no platemap XY (`:341-343`); `z_move` with `z_position` `NA` writes no row (`:611`, `:626-627`); any other key is looked up in `z_height_mm`, and one that is missing yields `d_mm=["NA"]` and a move attempt (`:610-625`), which the `Zpos` enum validation normally prevents.

### Axis state rows: `query_positions`, `query_position`, `query_moving`, `axis_off`, `axis_on`, `stop`

`action_abbr` is `query_position` for `query_positions` (`helao/deploy/hte/servers/galil_motion/galil_motion.py:372`) and `query_position` (`:390`), `query_moving` (`:407`), `axis_off` (`:428`), `axis_on` (`:445`), `stop` (`:560`). Data file `<action_abbr>-*.jsonl` (+ `.meta.json`), one row. `query_positions`/`query_position` queue the position dict; `query_moving` the moving dict; `axis_off`, `axis_on` and `stop` queue the moving dict merged with the position dict (`galil_motion_native.py:428-470`).

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `ax` | str \| null | list[str \| null] | none | axis name per queried axis; `null` when the axis is not in `axis_id` | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:338` |
| `position` | float \| null | list[float \| null] | mm | position of that axis (`count_to_mm` applied); `null` for an unknown axis; empty lists when the controller is not enabled (`:308`) | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:338` |
| `motor_status` | str | list[str] | none | `moving`, `stopped` or `invalid`; `query_moving`, `axis_off`, `axis_on`, `stop` only | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:423` |
| `err_code` | str | list[str] | none | `none`, `unspecified` or `not_available` per axis (a scalar `not_available` when the controller is disabled, `:400`); same set of rows as `motor_status` | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:423` |

No action results.

### `setmotionref` (action)

Homes the axes and queues one row `{"setref": <final move dict | "error">}` (`helao/deploy/hte/servers/galil_motion/galil_motion.py:139-141`; `galil_motion_native.py:755-804`); `action_abbr` `setmotionref`. `setref` is `str` (`"error"`, `:763`) when the controller is disabled, else the move result dict of the last move; the `else` branch at `:804` also returns `"error"`. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `setref` | dict \| str | dict | none | the final move dict, with the fields `moved_axis`, `speed`, `accepted_rel_dist`, `supplied_rel_dist`, `err_dist`, `err_code`, `counts` described in the move table above, or the string `error` | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:802`, `:763`, `:804` |

### `reset` (action)

Queues `{"reset": <str>}` (`helao/deploy/hte/servers/galil_motion/galil_motion.py:580-582`), `action_abbr` `reset`; `reset` is the controller's reply to `RS`, or `""` when disabled (`galil_motion_native.py:472-476`). No action results.

### `disconnect` (action)

Queues `{"connection": <str>}` (`helao/deploy/hte/servers/galil_motion/galil_motion.py:363`), `action_abbr` `disconnect`; the value is `motor_offline` or `Unexpected GalilChannelError: <message>` (`galil_motion_native.py:841-847`). No action results.

### Plate-alignment and transform actions

| action | abbr | row (data file `<abbr>-*.jsonl`) | row field type | action results | written at |
|---|---|---|---|---|---|
| `load_plate_alignment` | default | `{"matrix": <3x3>}` | `matrix`: `int | float`, `list[list[int | float]]` (the default and identity matrices are integer, `galil_motion_native.py:106`, `galil_motion.py:155`), the matrix now in force (the identity when the supplied shape differs) | none | `helao/deploy/hte/servers/galil_motion/galil_motion.py:163` |
| `reset_plate_alignment` | default | none | none | none | `helao/deploy/hte/servers/galil_motion/galil_motion.py:148-151` |
| `toMotorXY` | `tomotorxy` | `{"motorxy": ...}` | `float`, `list[float]` of length 3 `[x, y, 1.0]` (homogeneous coordinate; `helao/hexagon/domain/motion_transform.py:81-93`); the `platexy` param is one `"x,y"` string | none | `helao/deploy/hte/servers/galil_motion/galil_motion.py:227-233` |
| `toPlateXY` | `toplatexy` | `{"platexy": ...}` | `float`, `list[float]` of length 3 `[x, y, 1.0]` (`motion_transform.py:99-109`); the `motorxy` param is one `"x,y"` string | none | `helao/deploy/hte/servers/galil_motion/galil_motion.py:245-251` |
| `MxytoMPlate` | `mxytomplate` | `{"mplate": ...}` | `mplate`: `float \| null`, `list[list[float]]` (3x3): the plate matrix `Minstr^-1 · Mxy` from the JSON-string `Mxy` (`helao/hexagon/domain/motion_transform.py`, `get_Mplate_Msystem`); `null` when `Minstr` is singular. `Mxy` absent raises `ValueError("Mxy required")` (HTTP 500, no row) | none | `helao/deploy/hte/servers/galil_motion/galil_motion.py:264-266` |

`load_plate_alignment`, `reset_plate_alignment` and the aligner also persist the plate matrix, see Files below.

### Platemap lookup actions: `solid_get_platemap`, `solid_get_samples_xy`, `solid_get_builtin_specref`, `solid_get_nearest_specref`

Each queues one row; data file `<action_abbr>-*.jsonl` (+ `.meta.json`). Values come from the unified sample database or this server's config, so their element types are `unknown (dynamic)`.

| action | row fields | action results (in `-act.json`) | written at |
|---|---|---|---|
| `solid_get_platemap` | `platemap`: unknown (dynamic), `list` of platemap rows for `plate_id` | none | `helao/deploy/hte/servers/galil_motion/galil_motion.py:464`; value `galil_motion_native.py:876-879` |
| `solid_get_samples_xy` | `platexy`: unknown (dynamic), `list` of `[x, y]` pairs | `_platexy` (`list`, first `[x, y]` pair, entries may be `null`) | `helao/deploy/hte/servers/galil_motion/galil_motion.py:488`; `_platexy` `:487`; value `galil_motion_native.py:881-888` |
| `solid_get_builtin_specref` | `_refxy`: unknown (dynamic), the config `world_cfg[ref_position_name]` entry | `_refxy`, same value | `helao/deploy/hte/servers/galil_motion/galil_motion.py:506`; `_refxy` `:505` |
| `solid_get_nearest_specref` | `_refno`: `float`, `_refxy`: `list[float]` | `_refno` (`float`, a numpy float64 element of `refnos`), `_refxy` (`list[float]`), same values | `helao/deploy/hte/servers/galil_motion/galil_motion.py:553`; keys `:552` |

### `run_aligner` (action) and `stop_aligner`

`run_aligner` opens the action with file type `aligner_helao__file` and hands it to the Bokeh aligner (`helao/deploy/hte/servers/galil_motion/galil_motion.py:200-201`; `galil_aligner_host.py:199-206`). The action stays active until the operator submits or stops in the aligner UI; the aligner (`helao/deploy/hte/layouts/aligner.py:1225-1273`) then writes one row and one file and finishes the action. `stop_aligner` writes no data files or action results (`galil_motion.py:208-216`).

Data file `<action_abbr>-*.jsonl` (+ `.meta.json`), one row (`helao/deploy/hte/layouts/aligner.py:1260-1270`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `Transfermatrix` | int \| float | list[list[int \| float]] | none | the new 3x3 plate-to-motor matrix | `helao/deploy/hte/layouts/aligner.py:1264` |
| `oldTransfermatrix` | int \| float | list[list[int \| float]] | none | the matrix in force when the aligner started | `helao/deploy/hte/layouts/aligner.py:1265` |
| `err_code` | str | scalar per row | none | `f"{errorcode}"`: `none` (submit, and "skip step", which writes the initial matrix, `helao/deploy/hte/layouts/aligner.py:1105`) or `stop` (stop). Rows written on Python >= 3.12 before `ErrorCodes.__str__` was fixed (`helao/core/error.py:8`) carry `ErrorCodes.none` / `ErrorCodes.stop`; readers must accept both spellings | `helao/deploy/hte/layouts/aligner.py:1266` |

The row is queued only while the aligner holds an active action (`helao/deploy/hte/layouts/aligner.py:1238`).

### Files

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| plate calibration (action output) | JSON, the 3x3 matrix as nested lists; file type `plate_calib` | `<host>_plate_<plateid_or_pmpath>_calib.json` in the action output directory | matrix applied at the end of `run_aligner` | `helao/deploy/hte/layouts/aligner.py:1252-1257` |
| plate calibration (DB copy) | JSON, nested lists | `<db_root>/plate_calib/<host>_plate_<plateid_or_pmpath>_calib.json` | same matrix, written under the sample-DB root | `helao/deploy/hte/layouts/aligner.py:1242-1247`; writer `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:856-857` |
| last plate calibration | JSON, nested lists | `<states_root>/<host>_last_plate_calib.json` | matrix last installed by `load_plate_alignment`, `reset_plate_alignment` or the aligner; reloaded at startup | `helao/deploy/hte/servers/galil_motion/galil_motion_native.py:208-212`, `:856-857` |

`<host>` is the lower-cased host name. `/move_axis`, `/stop_motion`, `/get_axis_positions` and the other private endpoints return values to the caller only and write nothing (`galil_motion.py:650-792`).

## Notes

- `GalilCommandChannel` tests use `tests/fake_gclib.py`, so no gclib install is needed to run them.
- A move that times out halts the axes (`ST`), marks each axis not seen `stopped` with `err_code` `timeout`, and returns normally (`helao/deploy/hte/servers/galil_motion/galil_motion_native.py:711-723`); the action's `error_code` is `timeout`, so an orchestrator E-STOPs. The driver releases its busy and blocked flags, so the next move is accepted.
