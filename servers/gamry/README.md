# gamry

Action server for Gamry potentiostats (`gamry_server2.py`, over the GamryCOM Windows COM interface). It exposes LSV, CA, CP, CV, OCV, RCA, PEIS and GEIS techniques. `bokeh/gamry_vis.py` and `reflex/gamry_vis.py` are its action visualizers (`action_vis: gamry_vis`).

## Vendor software

Install by hand (not pip/conda):

- Gamry Framework (provides the GamryCOM COM server used through `comtypes`). The driver loads the GamryCOM type library by GUID `{BD962F0D-A990-4823-9CF5-284D1CDD9C6D}`.

`comtypes` itself is installed on Windows by `requirements.txt` in this folder. The driver imports it inside `connect()`, so the module imports on Linux, but the server only works on Windows.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `gamry_server2` (`fast:`)

The `GamryDriver` receives the server's `params` dict as its config (through `GamryComAdapter`, `gamry_com.py:299`). The server module reads none itself. The Bokeh and Reflex visualizer modules read no server params.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `dev_id` | yes | int | `None` | Index into `GamryDeviceList.EnumSections()` selecting the potentiostat. When absent, indexing the list with `None` raises and `connect` fails. | `helao/deploy/hte/servers/gamry/driver.py:87`, `:104` |
| `filterfreq_hz` | no | number (Hz) | `1000.0` | Analog input filter for the I and V channels. | `helao/deploy/hte/servers/gamry/driver.py:88`, `:269`, `:281` |
| `grounded` | no | bool | `True` | Passed to `SetGround`. | `helao/deploy/hte/servers/gamry/driver.py:89`, `:259` |
| `recover_stale_gamrycom` | no | bool | `False` | When `pstat.Open()` fails with "in use by another script", kill every GamryCOM process on the host and retry the open once. Leave it off where another live instance may hold the device. | `helao/deploy/hte/servers/gamry/driver.py:149` |

Example:
```yaml
params:
  dev_id: 0
  filterfreq_hz: 1000.0
  grounded: true
```

### Unused keys seen in configs

- `allow_no_sample` (set to `true` in several `hte` configs): no code in this folder reads it.
- `address`, `num_channels` (commented out in `hte` configs): no code in this folder reads them.

## Outputs

The server is backed by `GamryComAdapter` (`helao/deploy/hte/servers/gamry/gamry_server2.py:1335`); `GamryPoller` is defined (`helao/deploy/hte/servers/gamry/driver.py:824`) but its wiring is commented out (`gamry_server2.py:1336`), so there is no idle live-data stream. Technique and EIS actions write through the framework default data connection: one JSON object per queued message, file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). `Executor` actions queue the `data` dict returned by `_poll` as one row (`helao/hexagon/app/executor_runner.py:129-136`); an empty dict queues nothing. Columns are the keys of the first message queued (`helao/hexagon/adapters/native/data_stream.py:338-349`). Non-finite floats are written as `null` (`helao/helpers/to_json.py:30`).

### `run_LSV`, `run_CA`, `run_CP`, `run_CV`, `run_OCV`, `run_RCA` (actions)

`GamryExec` (`helao/deploy/hte/servers/gamry/gamry_server2.py:115`); `action_abbr` is `LSV` (`:773`), `CA` (`:847`), `CP` (`:913`), `CV` (`:1002`), `OCV` (`:1062`), `RCA` (`:1141`). Each `_poll` queues the dtaq sink's new points as one row (`gamry_server2.py:362`); every value is a list with one entry per point. The columns are the technique's `output_keys` in order (`helao/deploy/hte/servers/gamry/gamry_com.py:345-350`), and all are `list[float]` because the points are stacked with `np.matrix(...).T.tolist()` (`gamry_com.py:349`). The dtaq per technique is set in `helao/deploy/hte/servers/gamry/technique.py` (`LSV` `:82`, `CA` `:94`, `CP` `:103`, `CV` `:112`, `OCV` `:120`, `RCA` `:127`).

Data file `<action_abbr>-*.jsonl` (+ `.meta.json`), one row per poll that returned points. `<n>` below is the column's position in that dtaq's `output_keys`:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `t_s` | float | list[float] | s | time since the start of the technique; all techniques | `helao/deploy/hte/servers/gamry/dtaq.py:54` |
| `Ewe_V` | float | list[float] | V | working-electrode potential; all techniques | `helao/deploy/hte/servers/gamry/dtaq.py:55` |
| `Vu` | float | list[float] | V | uncompensated potential; all except `OCV` | `helao/deploy/hte/servers/gamry/dtaq.py:56` |
| `Vm` | float | list[float] | V | measured potential; `OCV` only | `helao/deploy/hte/servers/gamry/dtaq.py:190` |
| `I_A` | float | list[float] | A | current; all except `OCV` | `helao/deploy/hte/servers/gamry/dtaq.py:57` |
| `Vsig` | float | list[float] | V | signal-generator potential | `helao/deploy/hte/servers/gamry/dtaq.py:58` |
| `Ach_V` | float | list[float] | V | auxiliary analog channel | `helao/deploy/hte/servers/gamry/dtaq.py:59` |
| `IERange` | float | list[float] | none | current-range code at the sample; all except `OCV` | `helao/deploy/hte/servers/gamry/dtaq.py:60` |
| `Overload_HEX` | float | list[float] | none | overload bit field | `helao/deploy/hte/servers/gamry/dtaq.py:61` |
| `StopTest` | float | list[float] | none | stop-test flag; all except `RCA` | `helao/deploy/hte/servers/gamry/dtaq.py:62` |
| `Cycle` | float | list[float] | none | cycle number; `CV` only | `helao/deploy/hte/servers/gamry/dtaq.py:166` |
| `unknown1` | float | list[float] | unknown (dynamic) | unnamed Gamry column; present in every technique | `helao/deploy/hte/servers/gamry/dtaq.py:63` |
| `unknown2`, `unknown3` | float | list[float] | unknown (dynamic) | unnamed Gamry columns; `OCV` only | `helao/deploy/hte/servers/gamry/dtaq.py:196-197` |

Column set per technique (from `dtaq.py`): `LSV` `t_s`, `Ewe_V`, `Vu`, `I_A`, `Vsig`, `Ach_V`, `IERange`, `Overload_HEX`, `StopTest`, `unknown1` (`:53-64`); `CA` and `CP` the same (`:92-103`, `:124-135`); `CV` the same with `Cycle` before `unknown1` (`:156-168`); `OCV` `t_s`, `Ewe_V`, `Vm`, `Vsig`, `Ach_V`, `Overload_HEX`, `StopTest`, `unknown1-3` (`:187-198`); `RCA` `t_s`, `Ewe_V`, `Vu`, `I_A`, `Vsig`, `Ach_V`, `IERange`, `Overload_HEX`, `unknown1` (`:207-217`).

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `t_s__mean_final` | `action_params` | float \| null | scalar | `nanmean` of the last 5 `t_s` samples; present only when the run produced `t_s`; NaN is written as `null` by the orjson record writer (`helao/helpers/meta_io.py:60`) | `helao/deploy/hte/servers/gamry/gamry_server2.py:385` |
| `Ewe_V__mean_final` | `action_params` | float \| null | scalar | same for `Ewe_V` | `helao/deploy/hte/servers/gamry/gamry_server2.py:385` |
| `I_A__mean_final` | `action_params` | float \| null | scalar | same for `I_A`; absent for `run_OCV` (no `I_A` column) | `helao/deploy/hte/servers/gamry/gamry_server2.py:385` |
| `has_bubble` | `action_params` | bool | scalar | `run_OCV` only: `bubble_detection` result using the `RSD_threshold`, `simple_threshold`, `signal_change_threshold`, `amplitude_threshold` params (default `1` each) | `helao/deploy/hte/servers/gamry/gamry_server2.py:400` |
| `AcqPointsPerCycle` | `action_params` | int | scalar | `run_RCA` only: `round((Tinit__s + Tstep__s) / AcqInterval__s)` | `helao/deploy/hte/servers/gamry/gamry_server2.py:1136` |
| `SignalArray__V` | `action_params` | float | list[float] | `run_RCA` only: `Vinit__V` while `i * AcqInterval__s <= Tinit__s`, else `Vstep__V`, one entry per point of a cycle | `helao/deploy/hte/servers/gamry/gamry_server2.py:1137` |

### `init_ocv.jsonl` (written by all technique and EIS actions when `versus_OCV` is set)

Before the cell is energised, `GamryExec._pre_exec` (`gamry_server2.py:235-237`) and `GamryEisExec._pre_exec` (`gamry_server2.py:514-518`) call `measure_init_ocv`, which writes `init_ocv.jsonl` (+ `init_ocv.meta.json`) of file type `pstat_helao__file` as a single JSON line (`helao/deploy/hte/servers/gamry/gamry_server2.py:81-88`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `t_s` | float | list[float] | s | time since the OCV measurement started | `helao/deploy/hte/servers/gamry/readz.py:49` |
| `Ewe_V` | unknown (dynamic) | list[unknown (dynamic)] | V | `pstat.MeasureV()` reading; the COM return type is not defined in the repo. This file is written with stdlib `json.dumps` (`helao/deploy/hte/servers/gamry/gamry_server2.py:82`), so a NaN would appear as a bare `NaN` token, not `null` | `helao/deploy/hte/servers/gamry/readz.py:49` |

`init_ocv.meta.json` header (`gamry_server2.py:86`): `mean_ocv` (float, V), the mean of the last 5 `Ewe_V` samples. The signal potentials of the technique are then shifted by `mean_ocv` (`gamry_server2.py:242`) and the shifted values are what the driver sets up; the `mean_ocv` value is not copied into `action_params`.

`run_CV` also takes `previous_ocv__V` (V, default `None`). When it is set, `GamryExec._pre_exec` adds it to every signal potential with `offset_potentials` before setup and measures nothing (`helao/deploy/hte/servers/gamry/gamry_server2.py:216`); no `init_ocv.jsonl` is written. An orchestrator fills it from a preceding OCV action's `Ewe_V__mean_final` (`from_global_act_params`), which is how a CV references an OCV run in the same experiment. It is refused (`setup`) together with `versus_OCV`, or when it is not a finite number. The recorded `action_params` keep the requested potentials and the `previous_ocv__V` used.

### `run_PEIS`, `run_GEIS` (actions)

`GamryEisExec` (`helao/deploy/hte/servers/gamry/gamry_server2.py:419`); `action_abbr` is `PEIS` (`:1192`) or `GEIS` (`:1237`). Each `_poll` that has an impedance result queues one row (`gamry_server2.py:626`): the final impedance tuple of one frequency, read from the `GamryReadZ` COM object when the sink reports `ReadZStatusOk` (`helao/deploy/hte/servers/gamry/readz.py:402`, `:431`), plus `t_s` added by the executor. Values are scalars. `dtaqsink.reset()` clears the result before the next frequency (`gamry_server2.py:610`; `readz.py:439-441`), so rows are normally one per frequency; a frequency is retried up to `MaxRetries` times and a retried one writes no row until it succeeds.

Data file `<action_abbr>-*.jsonl` (+ `.meta.json`), one row per frequency. The values come from COM getters on `GamryReadZ`, whose return types are fixed by the Gamry type library, not by this repo, so each type is `unknown (dynamic)`:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `Zfreq` | unknown (dynamic) | scalar per row | Hz | measured frequency | `helao/deploy/hte/servers/gamry/readz.py:402` |
| `Zreal`, `Zimag` | unknown (dynamic) | scalar per row | ohm | real and imaginary impedance | `helao/deploy/hte/servers/gamry/readz.py:402` |
| `Zsig`, `Zmod`, `Zphz` | unknown (dynamic) | scalar per row | ohm, ohm, degrees (as Gamry defines them) | signal, modulus and phase of the impedance | `helao/deploy/hte/servers/gamry/readz.py:402` |
| `Ireal`, `Iimag`, `Isig`, `Imod`, `Iphz`, `Idc` | unknown (dynamic) | scalar per row | A (`Iphz` degrees) | current components, modulus, phase, DC | `helao/deploy/hte/servers/gamry/readz.py:402` |
| `Vreal`, `Vimag`, `Vsig`, `Vmod`, `Vphz`, `Vdc` | unknown (dynamic) | scalar per row | V (`Vphz` degrees) | potential components, modulus, phase, DC | `helao/deploy/hte/servers/gamry/readz.py:402` |
| `Gain`, `INoise`, `VNoise`, `IENoise`, `IERange` | unknown (dynamic) | scalar per row | none | gain, noise figures and current-range code reported by `GamryReadZ` | `helao/deploy/hte/servers/gamry/readz.py:402` |
| `t_s` | float | scalar per row | s | wall-clock seconds since the executor's `start_time` | `helao/deploy/hte/servers/gamry/gamry_server2.py:624-625` |

The keys are the fixed list at `readz.py:377-401`. No action results.

### `get_meas_status` (action)

Queues one row from the adapter's sink (`helao/deploy/hte/servers/gamry/gamry_server2.py:1256`; `GamryComAdapter.dtaqsink`, `gamry_com.py:265`); data file `<action_abbr>-*.jsonl` (+ `.meta.json`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `status` | str | scalar per row | none | state of `driver.dtaqsink` (`gamry_com.py:265`): `idle`, `measuring` or `done`. During an EIS run the underlying driver's `dtaqsink` is the dummy sink (`helao/deploy/hte/servers/gamry/driver.py:757-760`, `:811`), so it reports `idle` | `helao/deploy/hte/servers/gamry/gamry_server2.py:1256` |

### `stop` (action) and private endpoints

No data files or action results (`/stop_private`, `/gamry_state`, `/gamry_is_open`, `/measure_v`, `/measure_i`, `/measure_a` return values to the caller only).

## Notes

- `gamry_dyn_endpoints` writes `server_params["allow_concurrent_actions"] = False` at startup (`gamry_server2.py:674`). The server sets this itself; a config value is overwritten.
- `driver.py:89` stores `grounded` as `int(...)`, while `driver.py:259` re-reads the raw value for `SetGround`. Both come from the same key.
