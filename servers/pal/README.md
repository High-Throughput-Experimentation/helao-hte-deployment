# pal

Action server for a PAL autosampler (liquid and gas transfers, GC/HPLC injections, archive, deep clean). It builds `.cam` method jobs and runs the PAL program locally or over SSH, optionally synchronised by NI-DAQmx digital-input triggers. See `CLAUDE.md` in this folder for how the SSH identity is configured.

## Vendor software

Install by hand (not pip/conda):

- PAL autosampler control software, providing the `PAL` command-line program and the `.cam` methods. The driver runs `PAL <jobfile> /start /quit` (`pal_transport.py:136`), either on this machine (`host: localhost`) or, over SSH, on the PAL PC. The `.cam` method files named under `cams` must exist in `cam_file_path` on the machine where PAL runs. The code does not say where to get the software or which version.
- Remote PAL PC (SSH mode only): an SSH server on a Cygwin install (the driver writes paths as `/cygdrive/c/...`, `pal_transport.py:106`) that accepts the RSA key named by `key`.
- NI-DAQmx driver runtime on the HELAO machine, only when `dev_trigger: NImax` (the `nidaqmx` package, in `requirements.txt`, is imported lazily at `pal_trigger.py:88`). See `../nidaqmx/README.md`.

`paramiko` is in `environment.yml`.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `pal_server` (`fast:`)

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `host` | yes, unless `host_env` is set | str | `None` | SSH hostname of the PAL PC, or `localhost` to run PAL on this machine. A literal value wins over `host_env`. If neither gives a value, `connect()` fails and every PAL action returns `not_available`. | `helao/deploy/hte/servers/pal/pal_driver.py:227`, `pal_driver.py:92` |
| `host_env` | no | str | none | Name of an environment variable holding the host. Unset or empty logs an error. | `pal_driver.py:97` |
| `user` | no | str | `""` | SSH user. Literal value wins over `user_env`. | `pal_driver.py:225` |
| `user_env` | no | str | none | Environment variable holding the SSH user. | `pal_driver.py:97` |
| `key` | no | str | `""` | Path to the RSA private key file used for SSH (`paramiko.RSAKey.from_private_key_file`). Literal value wins over `key_env`. | `pal_driver.py:226`, `pal_transport.py:61` |
| `key_env` | no | str | none | Environment variable holding the key path. | `pal_driver.py:97` |
| `timeout` | no | float (s) | `1800` (`30 * 60`) | Passed to the NI-DAQmx trigger poller as its wait timeout. Not read when `dev_trigger` is not `NImax`. | `pal_driver.py:229`, `pal_driver.py:255` |
| `dev_trigger` | no | str | `None` | `NImax` selects the NI-DAQmx digital-input trigger handshake; any other value (or absent) uses a no-op trigger. | `pal_driver.py:242` |
| `trigger` | yes if `dev_trigger: NImax` | dict | none | Indexed without a default (`KeyError` if absent). Keys `start`, `continue`, `done`: NI-DAQmx digital-input lines (e.g. `PXI-6284/port2/line5`); each defaults to `None` when omitted. | `pal_driver.py:245` |
| `cam_file_path` | no | str | `""`, then `None` | Directory holding the `.cam` files on the PAL machine. Re-read at `pal_driver.py:298` with default `None`, which is the value in effect. | `pal_driver.py:228`, `pal_driver.py:298` |
| `cams` | no | dict `{cam_name: file_name}` | `None` | Maps a method name from the `CAMS` enum (`enum.py:38`: `transfer_tray_tray`, `transfer_custom_tray`, `transfer_tray_custom`, `transfer_custom_custom`, `injection_custom_GC_gas_wait`, `injection_custom_GC_gas_start`, `injection_custom_GC_liquid_wait`, `injection_custom_GC_liquid_start`, `injection_tray_GC_liquid_wait`, `injection_tray_GC_liquid_start`, `injection_tray_GC_gas_wait`, `injection_tray_GC_gas_start`, `injection_custom_HPLC`, `injection_tray_HPLC`, `deepclean`, `none`, `archive`) to its `.cam` file name. A name left out gets file name `None` and its actions return `not_available`. With no `cams` key at all, every method is unavailable. | `pal_driver.py:297`, `pal_server.py:111` |
| `positions` | no | dict | none | Only `positions.custom` is read here: its keys become the `dev_custom` enum of the custom-position endpoints. Sample-archive positions normally live on the SAMPLE server (see docs/config-schema.md). | `pal_server.py:115` |
| `world_config` | no | dict | `config_loader.CONFIG`, else `{}` | Overrides the world config handed to the sample-archive shim, which resolves the SAMPLE server's host and port from it. Station configs do not set it. | `pal_driver.py:215` |

Example (adapted from a station config; SSH identity by environment variable):
```yaml
params:
  user_env: HELAO_PAL_SSH_USER
  key_env: HELAO_PAL_SSH_KEY
  host_env: HELAO_PAL_SSH_HOST
  timeout: 1800
  dev_trigger: NImax
  trigger:
    start: PXI-6284/port2/line5
    continue: PXI-6284/port2/line7
    done: PXI-6284/port2/line3
  cam_file_path: C:\Users\<user>\Desktop\psc_methods\HELAO
  cams:
    transfer_tray_tray: tray_to_tray_220214.cam
    transfer_custom_tray: custom_to_tray_220214.cam
    archive: custom_to_tray_220214.cam
    deepclean: deep_clean_220214.cam
```

Local mode (PAL on the HELAO machine) uses `host: localhost` and needs no `user`/`key`.

Notes:
- The PAL server needs a `SAMPLE` server in the same config: the sample-archive shim looks up `world_cfg["servers"]["SAMPLE"]` for host and port (`sample_shim.py:190`).
- `cam_file_path` is read twice with defaults `""` and `None` (`pal_driver.py:228`, `pal_driver.py:298`); only the second value reaches the `cams` table.

## Outputs

### PAL job actions (`PAL_run_method`, `PAL_ANEC_aliquot`, `PAL_ANEC_GC`, `PAL_injection_tray_GC`, `PAL_injection_custom_GC`, `PAL_injection_custom_HPLC`, `PAL_injection_tray_HPLC`, `PAL_transfer_tray_tray`, `PAL_transfer_tray_custom`, `PAL_transfer_custom_tray`, `PAL_transfer_custom_custom`, `PAL_archive`, `PAL_deepclean`) (actions)

Each endpoint builds a `PalCam` from its params (`app.driver.build_palcam_*`, no `action_params` key is rewritten) and starts `PALJobExec` (`helao/deploy/hte/servers/pal/pal_server.py:144-157`); the endpoint exists only when the needed `cams` entries are configured (`:196`, `:292-337`, `:562-859`). A call made while E-STOP is latched, without a PAL host, or while a job runs returns an error code and writes no artifact (`:123-142`). `PALJobExec._poll` returns no data (`:70-72`); everything below is produced by the driver's job worker, `PAL._sendcommand_main` (`helao/deploy/hte/servers/pal/pal_driver.py:471-642`). `action_abbr` per endpoint: `GC_injection` (`PAL_ANEC_aliquot` `:330`, `PAL_ANEC_GC` `:364`, `PAL_injection_tray_GC` `:416`, `PAL_injection_custom_GC` `:466`), `HPLC_injection` (`:507`, `:552`), `transfer` (`:610`, `:664`, `:718`, `:767`), `archive` (`:814`), `deepclean` (`:890`); `PAL_run_method` sets none, so it defaults to the action name (`helao/hexagon/app/action_context.py:190`). `PAL_dilute` and `PAL_autodilute` are registered only when `cams` names `dilute`/`autodilute`, and then only set `not_available` and write nothing (`helao/deploy/hte/servers/pal/pal_server.py:897-989`). No action results.

**Data file** `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`), file type `pal_helao__file` (`helao/deploy/hte/servers/pal/pal_server.py:154`). One row per PAL run (each repeat of each micro-method) after its three triggers have fired and the sample state is reconciled, only when `save_data` is on (`helao/deploy/hte/servers/pal/pal_driver.py:580`, queued at `:618-623`). From the second micro-method on the action is split first (`job.active.split()`, `helao/deploy/hte/servers/pal/pal_driver.py:535-536`), so each micro-method after the first lands in its own split action and file. Every value is stored as a one-element list: the row is `{column: [value]}` (`helao/deploy/hte/servers/pal/pal_driver.py:608-610`), columns from `FIFO_column_headings` (`:267-286`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `samples_in` | str \| null | array[str \| null, (1, n_samples)] | none | global labels of the samples at the SOURCE position before the run (the column name is historical; it is the source, not the action's `samples_in`) | `helao/deploy/hte/servers/pal/pal_driver.py:582-585` |
| `samples_out` | str \| null | array[str \| null, (1, n_samples)] | none | global labels of the samples at the DESTINATION position before the run | `helao/deploy/hte/servers/pal/pal_driver.py:586-589` |
| `epoch_PAL` | str | list[str] | none | `str()` of the joblist submission time in epoch ns, or `"None"` if unset | `helao/deploy/hte/servers/pal/pal_driver.py:590` |
| `epoch_start` | str | list[str] | none | `str()` of the PAL `start` trigger time (epoch ns) | `helao/deploy/hte/servers/pal/pal_driver.py:591` |
| `epoch_continue` | str | list[str] | none | `str()` of the `continue` trigger time; used as the sampling timestamp | `helao/deploy/hte/servers/pal/pal_driver.py:592` |
| `epoch_done` | str | list[str] | none | `str()` of the `done` trigger time | `helao/deploy/hte/servers/pal/pal_driver.py:593` |
| `tool` | str | list[str] | none | PAL tool string, for example `LS 3`; a tool that does not resolve rejects the job before any row (`helao/deploy/hte/servers/pal/pal_driver.py:411-414`) | `helao/deploy/hte/servers/pal/pal_driver.py:594` |
| `source` | str \| null | list[str \| null] | none | source position: `tray` or a custom position name | `helao/deploy/hte/servers/pal/pal_driver.py:595` |
| `volume_ul` | str | list[str] | uL | `str()` of the transfer volume | `helao/deploy/hte/servers/pal/pal_driver.py:596` |
| `source_tray` | str | list[str] | none | `str()` of the source tray (`"None"` for custom positions) | `helao/deploy/hte/servers/pal/pal_driver.py:597` |
| `source_slot` | str | list[str] | none | `str()` of the source slot | `helao/deploy/hte/servers/pal/pal_driver.py:598` |
| `source_vial` | str | list[str] | none | `str()` of the source vial | `helao/deploy/hte/servers/pal/pal_driver.py:599` |
| `dest` | str \| null | list[str \| null] | none | destination position: `tray` or a custom position name | `helao/deploy/hte/servers/pal/pal_driver.py:600` |
| `dest_tray` | str | list[str] | none | `str()` of the destination tray | `helao/deploy/hte/servers/pal/pal_driver.py:601` |
| `dest_slot` | str | list[str] | none | `str()` of the destination slot | `helao/deploy/hte/servers/pal/pal_driver.py:602` |
| `dest_vial` | str | list[str] | none | `str()` of the destination vial | `helao/deploy/hte/servers/pal/pal_driver.py:603` |
| `logfile` | str | list[str] | none | path of the PAL auxiliary log file | `helao/deploy/hte/servers/pal/pal_driver.py:604` |
| `method` | str | list[str] | none | path of the `.cam` method file | `helao/deploy/hte/servers/pal/pal_driver.py:605` |

Other files and records:

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| PAL auxiliary log | tab-separated text, header line then `%%` then rows | `AUX__PAL__log.txt` in the action directory, file type `pal_auxlog_file`, tracked on the action | created with the header `Date`, `Method`, `Tool`, `Source`, `DestinationTray`, `DestinationSlot`, `DestinationVial`, `Volume` (`helao/deploy/hte/servers/pal/pal_driver.py:671-677`, header list `palauxheader` at `:312`); the external PAL program then appends one line per run to the path passed to it (`:708`, `:726`). Row contents and types come from the PAL software and are `unknown (dynamic)`. With a remote PAL PC the header is also written there and the PAL program appends on that machine (`helao/deploy/hte/servers/pal/pal_transport.py:94-97`, `:119-120`; the HELAO-side file then stays header-only) | `helao/deploy/hte/servers/pal/pal_driver.py:671` |

Sample records (in `-act.json`; fields of the action, not `action_params`): after each run the driver appends the reconciled samples (`helao/deploy/hte/servers/pal/pal_driver.py:629-631`). Each run starts by clearing the action's `samples_in`/`samples_out` (`:538-542`), so after a split action each file's record holds only that run's samples.

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `samples_in` | action | dict | list[dict] | snapshot (before the volume update) of the input samples of the run: source samples and any dest samples, refreshed from the SAMPLE server | `helao/deploy/hte/servers/pal/pal_driver.py:629` (snapshot at `helao/deploy/hte/servers/pal/pal_reconciliation.py:1308`) |
| `samples_out` | action | dict | list[dict] | the new samples the run created (reference samples turned into real samples by the SAMPLE server) | `helao/deploy/hte/servers/pal/pal_driver.py:631` (snapshot at `helao/deploy/hte/servers/pal/pal_reconciliation.py:1309`) |

Each sample dict is a `SampleUnion` model dump (`helao/core/models/sample.py`).

Sample-state writes to the SAMPLE server (private endpoints, called through `helao/deploy/hte/servers/pal/sample_shim.py` with `timeout=5, retries=1`; each raises on a non-`none` error code):

| endpoint | payload field | type | structure | meaning | sent at |
|---|---|---|---|---|---|
| `new_samples` | `samples` | dict | list[dict] | the run's `samples_out` (and unassigned assembly parts) persisted as new samples | `helao/deploy/hte/servers/pal/pal_reconciliation.py:1286`, `:1300` (dispatch `helao/deploy/hte/servers/pal/sample_shim.py:151`) |
| `update_samples` | `samples` | dict | list[dict] | the run's `samples_in` after the dilution/volume update, then each `samples_out` item (action UUID stamped) | `helao/deploy/hte/servers/pal/pal_reconciliation.py:1320`, `:1331` (dispatch `helao/deploy/hte/servers/pal/sample_shim.py:164`) |
| `tray_new_position` | `req_vol` | float | scalar | required volume in mL; the SAMPLE server marks the chosen empty vial as blocked (archive destinations only) | `helao/deploy/hte/servers/pal/pal_reconciliation.py:767` (dispatch `helao/deploy/hte/servers/pal/sample_shim.py:265`) |
| `tray_update_position` | `tray`, `slot`, `vial` | int \| null | scalar | vial whose stored sample is overwritten (source and dest of tray positions) | `helao/deploy/hte/servers/pal/pal_reconciliation.py:1108`, `:1125` (dispatch `helao/deploy/hte/servers/pal/sample_shim.py:282`) |
| `tray_update_position` | `sample` | dict | dict | the final sample to store at that vial | `helao/deploy/hte/servers/pal/pal_reconciliation.py:1108`, `:1125` |
| `custom_update_position` | `custom` | str | scalar | custom position name whose stored sample is replaced | `helao/deploy/hte/servers/pal/pal_reconciliation.py:1115`, `:1132` (dispatch `helao/deploy/hte/servers/pal/sample_shim.py:319`) |
| `custom_update_position` | `sample` | dict | dict | the final sample to store at that position | `helao/deploy/hte/servers/pal/pal_reconciliation.py:1115`, `:1132` |

The other SAMPLE calls the job makes (`get_samples`, `tray_query_sample`, `tray_get_next_full`, `custom_query_sample`, `custom_dest_allowed`, `custom_assembly_allowed`, `custom_is_destroyed`, `new_ref_samples`) only read or build in-memory reference samples. `tray_update_position` and `custom_update_position` receive `dilute=false` (the shim default; the PAL code never passes it).

### `stop` (action)

`action_abbr` `stop` (`helao/deploy/hte/servers/pal/pal_server.py:170`). Data file `stop-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `stop` | bool | scalar per row | none | whether the driver's stop request succeeded | `helao/deploy/hte/servers/pal/pal_server.py:172-174` |

### `kill_PAL` (action)

No `action_abbr` is passed, so the file is `kill_PAL-*.jsonl` (+ `.meta.json`), one row. No action results; the same code is also set as the action's `error_code` (`helao/deploy/hte/servers/pal/pal_server.py:191`).

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `error_code` | str | scalar per row | none | `ErrorCodes` value returned by killing the PAL process (`none` on success) | `helao/deploy/hte/servers/pal/pal_server.py:192` |
