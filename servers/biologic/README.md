# biologic

Action server for BioLogic potentiostats (`biologic_server.py`). It serves the same technique endpoints (`run_CA`, `run_CP`, `run_CV`, `run_OCV`, `run_PEIS`, `run_GEIS`, and others) from one of three backends chosen by `pstat_backend`: `eclib` (EClib1 DLL, `biologic/`), `olecom` (EC-Lab application over OLE COM, `biologic_ole/`) or `eclib2` (EC-Lib 2.0 SDK, `biologic_eclib2/`). `bokeh/biologic_vis.py` is its action visualizer (`action_vis: biologic_vis`). Design notes for the OLE backend: `CLAUDE.md` in this folder.

## Vendor software

Install by hand (not pip/conda). What a station needs depends on `pstat_backend`; `simulate: true` needs none of it.

- `eclib` (default): the BioLogic EC-Lab Development Package, which provides `EClib64.dll` and the firmware files. Python must be 64-bit. The driver looks in `sdk_path`, default `C:\EC-Lab Development Package\lib` (`biologic/vendor.py:71`, `:73`).
- `olecom`: the EC-Lab application itself, installed and registered for OLE COM (ProgID `EC-Lab.Application`, key `progid`). The driver also needs `comtypes`, which `helao_dev_win-64.yml` installs. The `.mps` templates in `biologic_ole/templates/` are authored in the EC-Lab GUI; see `biologic_ole/templates/README.md`.
- `eclib2`: the BioLogic EC-Lib 2.0 SDK (`biologic_ec_sdk`), unpacked anywhere and named by `sdk_path`. It ships no installable distribution. It must hold `Python/ECLibAPI.py`, `Python/Constants/`, `lib/eclib64.dll` and the license file `license_biologic_*.lic` at its root (`biologic_eclib2/vendor.py:21-26`). Without the license file every call fails with `EC_SDK_ERROR_LICENSE_NOT_VALID` (-99900). EC-Lib 2.0 supports Ethernet only.

The code does not say where BioLogic distributes these packages; get them from BioLogic.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `biologic_server` (`fast:`)

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `pstat_backend` | no | str | `"eclib"` | Backend driver: `"eclib"`, `"olecom"` or `"eclib2"`. Any other value raises `ValueError` when the app is built. | `helao/deploy/hte/servers/biologic/biologic_server.py:1026` |

All other keys are read by the selected backend's driver, below. A key set for another backend is ignored.

### `pstat_backend: eclib`

Driver `biologic/driver.py`.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `address` | no | str | `"192.168.200.240"` | Instrument IP passed to the DLL connect. | `helao/deploy/hte/servers/biologic/biologic/driver.py:135` |
| `num_channels` | no | int | `12` | Number of channels the server drives; channel indices run `0..num_channels-1`. | `helao/deploy/hte/servers/biologic/biologic/driver.py:136` |
| `sdk_path` | no | str (path) | `C:\EC-Lab Development Package\lib` | Folder holding `EClib64.dll`, the `.ecc` technique files and firmware. | `helao/deploy/hte/servers/biologic/biologic/driver.py:137` |
| `simulate` | no | bool | `False` | Use the in-process simulator instead of the DLL. | `helao/deploy/hte/servers/biologic/biologic/driver.py:138` |
| `force_load_firmware` | no | bool | `False` | Load the kernel and FPGA firmware at connect even when not needed. | `helao/deploy/hte/servers/biologic/biologic/driver.py:139` |
| `timeout` | no | number (s) | `5` | Connect timeout passed to the client. | `helao/deploy/hte/servers/biologic/biologic/driver.py:140` |

Example:
```yaml
params:
  address: 192.168.x.x
  num_channels: 1
```

### `pstat_backend: olecom`

Driver `biologic_ole/driver.py`.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `address` | no | str | `"192.168.200.240"` | Instrument IP passed to EC-Lab's `ConnectDeviceByIP`. | `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:107` |
| `num_channels` | no | int | `12` | Channels this server drives. | `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:108` |
| `simulate` | no | bool | `False` | Use the fake COM server in `sim.py` (no EC-Lab, comtypes or instrument needed). | `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:109` |
| `progid` | no | str | `"EC-Lab.Application"` | EC-Lab OLE ProgID. | `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:110` |
| `com_timeout_s` | no | number (s) | `30.0` | Per-call ceiling on every COM call. | `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:111` |
| `templates_dir` | no | str (path) | `biologic_ole/templates/` in the package | Folder holding the `.mps` templates. | `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:138` |
| `scratch_dir` | no | str (path) | `<cwd>/STATES/olecom` | Where patched settings files and in-progress MPR files are written. | `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:146` |
| `protocol_dir` | no | str (path) | `templates_dir` | Folder `run_protocol` resolves its `mps_path` against; the file must stay inside it. | `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:151` |

Example:
```yaml
params:
  pstat_backend: olecom
  address: 192.168.x.x
  num_channels: 2
  templates_dir: C:\path\to\mps_templates
```

### `pstat_backend: eclib2`

Driver `biologic_eclib2/driver.py`.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `address` | yes on a station | str | `""` | Instrument IP (Ethernet only). Unused while simulating. | `helao/deploy/hte/servers/biologic/biologic_eclib2/driver.py:93` |
| `num_channels` | no | int | `1` | Channels this server drives. | `helao/deploy/hte/servers/biologic/biologic_eclib2/driver.py:94` |
| `sdk_path` | yes unless `simulate` | str (path) | `None` | Unpacked `biologic_ec_sdk` root (see Vendor software). Absent with `simulate: false` raises `ValueError("sdk_path is required when simulate is false")`. | `helao/deploy/hte/servers/biologic/biologic_eclib2/driver.py:95`, `helao/deploy/hte/servers/biologic/biologic_eclib2/sdk_client.py:484` |
| `simulate` | no | bool | `False` | Use `biologic_eclib2/sim.py` in place of the SDK. | `helao/deploy/hte/servers/biologic/biologic_eclib2/driver.py:96` |
| `timeout_s` | no | int (s) | `120` | Connect timeout. | `helao/deploy/hte/servers/biologic/biologic_eclib2/driver.py:97` |

Example (simulated, from `helao/deploy/hte/configs/biologiceclib2.yml`):
```yaml
params:
  pstat_backend: eclib2
  simulate: true
  address: 127.0.0.1
  num_channels: 1
```

### `bokeh/biologic_vis.py` (`action_vis: biologic_vis`)

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `num_channels` | no | int | `1` | Number of channels the visualizer shows. It reads the key from this server's params. | `helao/deploy/hte/servers/biologic/bokeh/biologic_vis.py:99` |

### Unused keys seen in configs

- `allow_no_sample` and `grounded` (set in `hte` configs for this server): no code in this folder reads them.

## Outputs

Every technique action runs `BiologicExec` (`helao/deploy/hte/servers/biologic/biologic_server.py:67`) through the framework default data connection: one JSON object per queued message, file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Each `_poll` queues the backend's `get_data` result as one row, so every value in a row is a list with one entry per sample read in that poll (`biologic_server.py:299`; queued at `helao/hexagon/app/executor_runner.py:129-136`). Columns are the keys of the first message queued (`helao/hexagon/adapters/native/data_stream.py:338-349`). Non-finite floats are written as `null` (`helao/helpers/to_json.py:30`), so a column that can hold NaN is typed `float | null`.

`action_abbr` per endpoint: `run_CA` `CA` (`biologic_server.py:422`), `run_CP` `CP` (`:459`), `run_CV` `CV` (`:510`), `run_OCV` `OCV` (`:542`), `run_PEIS` `PEIS` (`:582`), `run_GEIS` `GEIS` (`:621`), `run_CAOCV` `CAOCV` (`:659`), `run_CALIMIT` `CALIM` (`:709`), `run_CPLIMIT` `CPLIM` (`:767`), `run_SPEIS` `SPEIS` (`:813`), `run_SGEIS` `SGEIS` (`:864`), `run_plan` `PLAN` (`:931`), `run_protocol` `PROT` (`:963`).

Which techniques a backend serves: `eclib` serves all of `OCV`, `CA`, `CP`, `CV`, `PEIS`, `GEIS`, `CAOCV`, `CALIMIT`, `CPLIMIT`, `SPEIS`, `SGEIS` (`helao/deploy/hte/servers/biologic/biologic/data.py:186-198`); `olecom` has the techniques in `OLE_TECHS` (`helao/deploy/hte/servers/biologic/biologic_ole/technique.py:352`; not `CALIMIT`, `CPLIMIT`, `SPEIS`, `SGEIS`); `eclib2` serves `OCV`, `CA`, `CP`, `CV`, `PEIS`, `GEIS`, `CAOCV` (`helao/deploy/hte/servers/biologic/biologic_eclib2/technique.py:60-67`). An endpoint whose technique the active backend lacks fails at technique resolution and writes no data.

### Data columns shared by all technique actions

Added by the executor to every non-empty poll, on all three backends:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `channel` | int | list[int] | none | channel index of the action, repeated once per sample | `helao/deploy/hte/servers/biologic/biologic_server.py:286` |

### `run_OCV` (action)

Data file `OCV-*.jsonl` (+ `.meta.json`). Columns (all backends; `eclib2` `OCV_COLUMNS`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `t_s` | float | list[float] | s | time since technique start (eclib: `StartTime` + decoded timestamp) | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:222`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:127-129`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:119` |
| `Ewe_V` | float | list[float] | V | working-electrode potential | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:225`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:127-129`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:120` |

The action also writes `Ewe_V__mean_final`, `t_s__mean_final`, `has_bubble` and `AcqInterval__V` (below).

### `run_CA`, `run_CP`, `run_CV`, `run_CAOCV`, `run_CALIMIT`, `run_CPLIMIT` (actions)

Data file `<action_abbr>-*.jsonl` (+ `.meta.json`). DC column set (`eclib` `COLUMNS` `_DC`, `helao/deploy/hte/servers/biologic/biologic/data.py:166`; olecom `DC_COLUMNS`, `helao/deploy/hte/servers/biologic/biologic_ole/technique.py:142`; eclib2 `STEP_COLUMNS`, `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:29`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `t_s` | float | list[float] | s | time since technique start | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:210`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:127-129`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:127` |
| `Ewe_V` | float | list[float] | V | working-electrode potential (eclib2: `ewe_average`) | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:215`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:127-129`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:128` |
| `I_A` | float \| null | list[float \| null] | A | current (eclib2: `i_average`); `null` on the OCV leg of `run_CAOCV` on eclib and eclib2 (NaN padding: `helao/deploy/hte/servers/biologic/biologic/driver.py:690-691`, `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:184-195`) | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:216`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:127-129`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:129` |
| `P_W` | float \| null | list[float \| null] | W | power; `null` on the CAOCV OCV leg (eclib, eclib2); eclib and eclib2 `Ewe*I` (signed), olecom `abs(Ewe*I)` | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:217`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:131`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:130` |
| `cycle` | int \| float \| null | list[int \| float \| null] | none | cycle number; `null` on the CAOCV OCV leg (eclib, eclib2) (`int` on eclib and eclib2, `float` on olecom); on olecom the status-register cycle at poll time (`helao/deploy/hte/servers/biologic/biologic_ole/status.py:131`) stamped on every point read in that poll | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:218`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:133`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:131` |

`eclib` also adds the `_`-prefixed live-state columns below to every technique.

Action results (in `-act.json`), set at run time by the endpoint after `ctx.begin()`:

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `AcqInterval__A` | `action_params` | float | scalar | fixed `10.0`; `run_CA` and `run_CALIMIT` | `helao/deploy/hte/servers/biologic/biologic_server.py:423`, `:710` |
| `AcqInterval__V` | `action_params` | float | scalar | fixed `10.0` for `run_CP`, `run_OCV`, `run_CPLIMIT`; for `run_CV` `AcqInterval__s * ScanRate__V_s` | `biologic_server.py:460`, `:543`, `:768`, `:506-509` |
| `CA_AcqInterval__A` | `action_params` | float | scalar | fixed `10.0`; `run_CAOCV` only | `biologic_server.py:660` |
| `OCV_AcqInterval__V` | `action_params` | float | scalar | fixed `10.0`; `run_CAOCV` only | `biologic_server.py:661` |
| `Cycles` | `action_params` | int | scalar | `run_CV` only: the requested value minus 1 ("additional cycles") | `biologic_server.py:505` |
| `t_s__mean_final` | `action_params` | float \| null | scalar | `nanmean` of the last 5 `t_s` samples; present only when the data buffer holds `t_s`; NaN is written as `null` by the orjson record writer (`helao/helpers/meta_io.py:60`) | `biologic_server.py:318` |
| `Ewe_V__mean_final` | `action_params` | float \| null | scalar | same for `Ewe_V` | `biologic_server.py:318` |
| `I_A__mean_final` | `action_params` | float \| null | scalar | same for `I_A`; absent for `run_OCV` (no `I_A` column) | `biologic_server.py:318` |
| `has_bubble` | `action_params` | bool | scalar | `run_OCV` only: result of `bubble_detection` on the buffered data, with the `RSD_threshold`, `simple_threshold`, `signal_change_threshold`, `amplitude_threshold` params (default `1` each) | `biologic_server.py:333` |

(`*__mean_final` is written for every technique action, `run_plan` and `run_protocol` included, for whichever of `t_s`, `Ewe_V`, `I_A` the run produced; the table lists the three keys once.)

### `run_PEIS`, `run_GEIS`, `run_SPEIS`, `run_SGEIS` (actions)

Data file `<action_abbr>-*.jsonl` (+ `.meta.json`). EIS column set (`eclib` `_EIS`, `helao/deploy/hte/servers/biologic/biologic/data.py:167-184`; `SPEIS`/`SGEIS` add `step`; olecom `EIS_COLUMNS`, `helao/deploy/hte/servers/biologic/biologic_ole/technique.py:146`; eclib2 `EIS_COLUMNS`, `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:34`). Columns are `float | null` where a row of another process type carries NaN.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `process` | int \| float | list[int \| float] | none | process index (`int` on eclib and eclib2, `float` on olecom): `0` time-domain leg, `1` frequency-domain leg (olecom: `1.0` when `f_Hz` is non-zero, else `0.0`) | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:230`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:145-146`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:144` |
| `t_s` | float | list[float] | s | time of the sample | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:231`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:142-144`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:145` |
| `Ewe_V` | float | list[float] | V | DC working-electrode potential | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:257`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:149-150`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:146` |
| `I_A` | float | list[float] | A | DC current | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:258`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:149-150`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:147` |
| `AbsEwe_V` | float \| null | list[float \| null] | V | potential amplitude of the perturbation; NaN on eclib process 0 | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:259`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:148` |
| `AbsI_A` | float \| null | list[float \| null] | A | current amplitude; NaN on eclib process 0 | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:260`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:149` |
| `phase` | float \| null | list[float \| null] | rad (as used in `-modulus*sin(phase)`) | working-electrode impedance phase | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:261`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:150` |
| `modulus` | float \| null | list[float \| null] | ohm | `AbsEwe_V / AbsI_A`; NaN when the divisor is 0 or either is NaN | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:262`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:151` |
| `Ece_V` | float \| null | list[float \| null] | V | counter-electrode potential | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:263`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:152` |
| `AbsEce_V` | float \| null | list[float \| null] | V | counter-electrode potential amplitude | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:264`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:153` |
| `AbsIce_A` | float \| null | list[float \| null] | A | counter-electrode current amplitude | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:265`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:154` |
| `phase_ce` | float \| null | list[float \| null] | rad | counter-electrode phase | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:266`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:155` |
| `modulus_ce` | float \| null | list[float \| null] | ohm | `AbsEce_V / AbsIce_A` | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:267`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:156` |
| `f_Hz` | float \| null | list[float \| null] | Hz | frequency; NaN on eclib process 0 | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:268`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:142-144`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:157` |
| `X_ohm` | float \| null | list[float \| null] | ohm | `-modulus * sin(phase)` (olecom: `-Im(Z)` as returned by EC-Lab) | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:269`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:142-144`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:159` |
| `R_ohm` | float \| null | list[float \| null] | ohm | `modulus * cos(phase)` (olecom: `Re(Z)`) | eclib `helao/deploy/hte/servers/biologic/biologic/data.py:270`; olecom `helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:142-144`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:160` |
| `step` | int | list[int] | none | step index; `SPEIS` and `SGEIS` only (eclib only) | `helao/deploy/hte/servers/biologic/biologic/data.py:273` |

On olecom the columns `AbsEwe_V`, `AbsI_A`, `phase`, `modulus`, `Ece_V`, `AbsEce_V`, `AbsIce_A`, `phase_ce`, `modulus_ce` come one value per call from `MeasureValueByCode`, NaN when the technique does not record the variable (`helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:147-156`); the OLE values are floats from the EC-Lab COM server. `eclib2` types follow the simulator dataclasses (`helao/deploy/hte/servers/biologic/biologic_eclib2/sim.py:248-279`) because the vendor SDK is not in the repo. No action results besides the `*__mean_final` keys listed above (`t_s`, `Ewe_V`, `I_A`).

### `run_plan` (action, `eclib` and `eclib2` only)

Data file `PLAN-*.jsonl` (+ `.meta.json`). Columns are the union of the entries' techniques: eclib `PlanTechnique.column_plan` (`helao/deploy/hte/servers/biologic/biologic/technique.py:843-849`), eclib2 `union(*columns)` (`helao/deploy/hte/servers/biologic/biologic_eclib2/technique.py:827`) in `ALL_COLUMNS` order. Column definitions as in the DC and EIS tables above; a column a segment does not report is `NaN` (`null`) for that segment's rows (eclib `helao/deploy/hte/servers/biologic/biologic/driver.py:690-691`; eclib2 `helao/deploy/hte/servers/biologic/biologic_eclib2/data.py:184-195`), except eclib2 `process`, which is `0` for a segment without one. Plus `channel`, and on eclib the `_`-prefixed columns below. Action results: `t_s__mean_final`, `Ewe_V__mean_final`, `I_A__mean_final` as above; no other keys.

### `run_protocol` (action, `olecom` only)

`BiologicProtocolExec` (`biologic_server.py:347`); data file `PROT-*.jsonl` (+ `.meta.json`). The columns are chosen from the loaded technique code (`helao/deploy/hte/servers/biologic/biologic_ole/technique.py:515-540`): the DC set above, the EIS set above, or `t_s`, `Ewe_V`, `I_A` only for an unrecognized code, plus `channel`. Types as for olecom above. Action results: `t_s__mean_final`, `Ewe_V__mean_final`, `I_A__mean_final` as above.

### `eclib`-only live-state columns

`BiologicDriver.get_data` appends one `_<field>` column per `CurrentValues` field to every poll row, the value repeated once per row read (`helao/deploy/hte/servers/biologic/biologic/driver.py:692-696`; fields at `helao/deploy/hte/servers/biologic/biologic/vendor.py:131-152`). Types follow the ctypes fields. The `olecom` and `eclib2` backends emit none of these.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `_State` | int | list[int] | none | channel state code | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_MemFilled` | int | list[int] | none | instrument memory fill | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_TimeBase` | float | list[float] | s | firmware time base | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_Ewe` | float | list[float] | V | instantaneous Ewe | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_EweRangeMin` | float | list[float] | V | Ewe range minimum | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_EweRangeMax` | float | list[float] | V | Ewe range maximum | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_Ece` | float | list[float] | V | instantaneous Ece | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_EceRangeMin` | float | list[float] | V | Ece range minimum | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_EceRangeMax` | float | list[float] | V | Ece range maximum | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_Eoverflow` | int | list[int] | none | Ewe overflow flag | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_I` | float | list[float] | A | instantaneous current | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_IRange` | int | list[int] | none | current range code | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_Ioverflow` | int | list[int] | none | current overflow flag | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_ElapsedTime` | float | list[float] | s | elapsed time | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_Freq` | float | list[float] | Hz | instantaneous frequency | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_Rcomp` | float | list[float] | ohm | compensated resistance | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_Saturation` | int | list[int] | none | saturation flag | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_OptErr` | int | list[int] | none | option error code | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |
| `_OptPos` | int | list[int] | none | option position | `helao/deploy/hte/servers/biologic/biologic/driver.py:694` |

### Files moved into the action directory (`olecom` only)

These files are moved into the action directory but never registered on the action: nothing calls `track_file` for them, so they are not in the record's `files` list and are not uploaded by the syncer (it ships only that list, `helao/hexagon/adapters/native/sync_driver.py:538-562`); `_register_present_files` (`helao/hexagon/app/action_host.py:1522`) runs only when an interrupted action is reconciled. They stay local (see Notes). At `cleanup` the driver moves the run's `.mps`, `.mpr`, `.mpt` files into the action output directory (`helao/deploy/hte/servers/biologic/biologic_ole/driver.py:685-702`, called from `cleanup` at `:718`); `run_protocol` also copies the unpatched protocol file into the run directory first (`helao/deploy/hte/servers/biologic/biologic_ole/driver.py:499`), so it lands there too. The `eclib` and `eclib2` backends ship no such files (their `setup` takes `output_dir` and never uses it: `helao/deploy/hte/servers/biologic/biologic/driver.py:436`, `helao/deploy/hte/servers/biologic/biologic_eclib2/driver.py:295`).

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| patched settings | EC-Lab `.mps` text, CRLF line ends | `<technique_name>.mps` (e.g. `CA.mps`) | the template with the action's parameters patched in | `helao/deploy/hte/servers/biologic/biologic_ole/mps_template.py:302-303`, call `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:402` |
| protocol copy | EC-Lab `.mps` | `<name of the file named by mps_path>` | the station-authored protocol, unpatched (`run_protocol`) | `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:499` |
| raw measurement | EC-Lab `.mpr` binary | EC-Lab-chosen | raw record EC-Lab appends to during the run | EC-Lab itself, moved at `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:702` |
| text export | EC-Lab `.mpt` text | EC-Lab-chosen | shipped if EC-Lab produced one in the run directory | EC-Lab itself, moved at `helao/deploy/hte/servers/biologic/biologic_ole/driver.py:702` |

### `get_meas_status` (action)

Intended to queue one row `{"status": <str>}` from `app.driver.dtaqsink.status` (`helao/deploy/hte/servers/biologic/biologic_server.py:1079`; `enqueue_data_dflt`, `helao/hexagon/adapters/native/data_stream.py:112`), but no backend defines `dtaqsink`, so the call raises `AttributeError` before the row is queued (see Notes). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `status` | unknown (dynamic) | scalar per row | none | dtaq sink status; the attribute does not exist, so the type is unknowable and the row is never written | `helao/deploy/hte/servers/biologic/biologic_server.py:1079` |

### `stop` (action) and `/stop_private`

No data files or action results.

## Notes

- `num_channels` defaults differ: the `eclib` and `olecom` drivers default to 12, the `eclib2` driver to 1, and the visualizer to 1. A station driving more than one channel on `eclib` or `olecom` without setting the key gets 12 driver channels but a one-channel visualizer.
- The `biologic_ole/driver.py` module docstring says "all optional except `address`", but the code gives `address` a default (`192.168.200.240`) on `eclib` and `olecom`.
- `biologic_server.py:382` writes `server_params["allow_concurrent_actions"] = False` at startup; a config value for it is overwritten.
- `get_meas_status` reads `app.driver.dtaqsink.status` (`helao/deploy/hte/servers/biologic/biologic_server.py:1079`), but no backend defines `dtaqsink`, so the action raises `AttributeError` and queues no row.
- `P_W` is signed `Ewe*I` on `eclib` and `eclib2` but `abs(Ewe*I)` on `olecom` (`helao/deploy/hte/servers/biologic/biologic_ole/mpr_cursor.py:131`), and `cycle` and `process` are `int` on the SDK backends but `float` on `olecom`; the column names match across backends, the values do not.
- The olecom artifacts (`.mps`, `.mpr`, `.mpt`) are moved into the action directory with `shutil.move` (`helao/deploy/hte/servers/biologic/biologic_ole/driver.py:702`) and never registered with `track_file`, so the syncer, which uploads only the record's `files` list, does not ship them. The `_ship_artifacts` docstring and `helao/deploy/hte/servers/biologic/CLAUDE.md` still describe the old directory-glob uploader.
