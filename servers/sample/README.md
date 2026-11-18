# sample

Sample archive action server (`sample_server`): tracks samples in trays and named custom positions, persists them to `<host>_archive.json` under `STATES/`, and syncs sample records with the sample database. `bokeh/sample_vis.py` and `reflex/sample_vis.py` show the newest samples.

## Vendor software
No vendor software beyond the env files.

## Params
Host-level keys every server accepts: see `docs/config-schema.md` ("Group conventions for `params:`").

### `sample_server` (`fast:` value)
| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `positions` | no | dict | none (no trays, no custom positions) | Sample-archive layout. Keys: `tray<n>` (integer `n`) and `custom`. Any other key is ignored. At most one server per config may declare it. | `helao/deploy/hte/servers/sample/archive_driver.py:123`, `helao/deploy/hte/servers/sample/sample_server.py:76` |
| `positions.tray<n>` | no | dict or null | n/a | Slots of tray `n`. Keys `slot1`, `slot2`, `slot3`; any other slot key is logged and skipped. A null tray is skipped. | `helao/deploy/hte/servers/sample/archive_driver.py:285` |
| `positions.tray<n>.slot<m>` | no | string or null | n/a | Vial rack type in the slot: `VT54`, `VT15` or `VT70`. Null leaves the slot empty. Any other string is logged as unsupported and the slot is stored as empty. | `helao/deploy/hte/servers/sample/archive_driver.py:296` |
| `positions.custom` | no | dict | `{}` | `{custom_name: custom_type}`. `custom_type` must be one of `cell`, `reservoir`, `injector`, `waste` (`CustomTypes`); another value fails pydantic validation. The names also become the `dev_custom` enum of the endpoints that take a `custom` argument. | `helao/deploy/hte/servers/sample/archive_driver.py:260`, `helao/deploy/hte/servers/sample/sample_server.py:77`, `helao/helpers/sample_positions.py:39` |

The persisted `<host>_archive.json` is compared with `positions` at startup. If tray or custom layouts differ, the archive's positions are replaced by the config's.

Example:
```yaml
params:
  positions:
    tray1:
      slot1: null
      slot2: null
      slot3: null
    tray2:
      slot1: VT54
      slot2: VT54
      slot3: VT54
    custom:
      elec_res1: reservoir
      cell1_we: cell
```

### `sample_vis` (`bokeh:` / `reflex:` panel)
Reads no params of its own. The Reflex panel looks up the server's `host` and `port` in the config (`helao/deploy/hte/servers/sample/reflex/sample_vis.py:109`).

## Outputs

`SS` below is `helao/deploy/hte/servers/sample/sample_server.py`, `AD` is `helao/deploy/hte/servers/sample/archive_driver.py`. Unless a section says otherwise, an action queues one row through the framework default data connection: file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`), columns from the first row (`helao/hexagon/adapters/native/data_stream.py:338-349`), serialized with `hlo_json_dumps` (NaN becomes `null`, `helao/helpers/to_json.py:39`). Where the abbreviation is not set, it defaults to the action name (`helao/hexagon/app/action_context.py:190`). A **sample dict** in a row is `Sample.as_dict()` of the sample models in `helao/core/models/sample.py`: the fields of the sample DB table below plus the per-type fields (`volume_ml`, `ph`, `dilution_factor`, `electrolyte` for liquids; `volume_ml`, `dilution_factor` for gases; `parts` for assemblies; `plate_id` for solids).

Three stores are written besides the action record:

**Archive state file** `<states_root>/<hostname lowercase>_archive.json` (`AD:131-134`), local only (not tracked on any action), rewritten whole by `write_config` (`AD:336-340`, stdlib `json.dump`) after every operation that changes the position table: startup (`AD:174`, `:239`), `update_samples_from_db` (`:386`), `tray_unload` (`:505`), `tray_unloadall` (`:544`), the tray exports (`:553`, `:570`, `:628`), `tray_update_position` (`:863`), `custom_replace_sample` (`:945`), `custom_update_position` (`:981`), `custom_unloadall` (`:1045`), `custom_unload` (`:1082`), `custom_load` (`:1226`). `tray_load` and `tray_new_position` change the in-memory table (`tray_new_position` marks the vial `blocked`) without calling it. Fields (from `Positions.as_dict()`, `helao/helpers/sample_positions.py:292-302`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `trays_dict` | dict | dict | none | `{tray_number: {slot_number: vial tray dict or null}}`; keys are JSON strings | `AD:340` |
| `customs_dict` | dict | dict | none | `{custom_name: custom position dict}` | `AD:340` |

Vial tray dict (`VT15`/`VT54`/`VT70`, `helao/helpers/sample_positions.py:151-289`):

| key | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `VTtype` | str | scalar | none | `VT15`, `VT54` or `VT70` | `helao/helpers/sample_positions.py:271`, `:279`, `:287` |
| `max_vol_ml` | float | scalar | mL | per-vial capacity (10, 2 or 1) | `helao/helpers/sample_positions.py:273`, `:281`, `:289` |
| `positions` | int | scalar | none | number of vials (15, 54 or 70) | `helao/helpers/sample_positions.py:272`, `:280`, `:288` |
| `vials` | bool | list[bool] | none | occupancy flag per vial | `helao/helpers/sample_positions.py:166` |
| `blocked` | bool | list[bool] | none | reserved-vial flag per vial | `helao/helpers/sample_positions.py:167` |
| `samples` | dict | list[dict] | none | sample dict per vial (empty vials hold the `NoneSample` dict) | `helao/helpers/sample_positions.py:168` |

Custom position dict (`helao/helpers/sample_positions.py:48-65`):

| key | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `sample` | dict | dict | none | currently loaded sample dict | `helao/helpers/sample_positions.py:59` |
| `custom_name` | str | scalar | none | position name | `helao/helpers/sample_positions.py:62` |
| `custom_type` | str | scalar | none | `cell`, `reservoir`, `injector` or `waste` | `helao/helpers/sample_positions.py:63` |
| `blocked` | bool | scalar | none | administratively blocked | `helao/helpers/sample_positions.py:64` |
| `max_vol_ml` | float \| null | scalar | mL | optional maximum holdup volume | `helao/helpers/sample_positions.py:65` |

**Sample database** (shared writer `helao/helpers/sample_api.py`; this unit's call sites are `AD:120` (opens it), `:1253-1254`, `:1658-1910`, `:1927`, `:1978`, `:2015`, `:2023` and the private `/new_samples`, `/update_samples` endpoints `SS:981-999`). One SQLite file per sample type in `<db_root>`, `<hostname lowercase>__<type>_sample.db` with `<type>` one of `liquid`, `gas`, `assembly`, `solid` (`helao/helpers/sample_api.py:130`), table `<type>_sample` with an autoincrement `idx` primary key. `new_samples` inserts a row (`helao/helpers/sample_api.py:262-325`; `sample_no` is the row count plus one, missing machine/server names, creation time and last-update are filled in); `update_samples` updates the row `idx = sample_no` only when `global_label` and `sample_type` match the stored row, and stamps `last_update` (`helao/helpers/sample_api.py:553-642`, UPDATE at `:523-551`). Columns (`helao/helpers/sample_api.py:87-108`, per-type extras `:672`, `:691`, `:710`, `:726`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `hlo_version` | str \| null | scalar per row | none | model version | `helao/helpers/sample_api.py:87` |
| `global_label` | str | scalar per row | none | unique label, `<machine>__<type>__<no>` style | `helao/helpers/sample_api.py:88` |
| `sample_type` | str | scalar per row | none | `liquid`, `gas`, `assembly` or `solid` | `helao/helpers/sample_api.py:89` |
| `sample_no` | int | scalar per row | none | row number within the table | `helao/helpers/sample_api.py:90` |
| `sample_creation_timecode` | int | scalar per row | ns | creation time (epoch) | `helao/helpers/sample_api.py:91` |
| `sample_position` | str \| null | scalar per row | none | position the sample was created at | `helao/helpers/sample_api.py:92` |
| `machine_name` | str | scalar per row | none | host that created the sample | `helao/helpers/sample_api.py:93` |
| `sample_hash` | str \| null | scalar per row | none | sample hash | `helao/helpers/sample_api.py:94` |
| `last_update` | int | scalar per row | ns | time of last write | `helao/helpers/sample_api.py:95` |
| `inheritance` | str \| null | scalar per row | none | inheritance mode | `helao/helpers/sample_api.py:96` |
| `status` | str \| null | scalar per row | none | JSON text of the status list | `helao/helpers/sample_api.py:97` |
| `action_uuid` | str \| null | scalar per row | none | JSON text of the list of action UUIDs | `helao/helpers/sample_api.py:98` |
| `sample_creation_experiment_uuid` | str \| null | scalar per row | none | experiment that created it | `helao/helpers/sample_api.py:99` |
| `sample_creation_action_uuid` | str \| null | scalar per row | none | action that created it | `helao/helpers/sample_api.py:100` |
| `server_name` | str \| null | scalar per row | none | server that created it | `helao/helpers/sample_api.py:101` |
| `chemical`, `partial_molarity`, `supplier`, `lot_number`, `source` | str \| null | scalar per row | none | each JSON text of a list | `helao/helpers/sample_api.py:102-106` |
| `prep_date`, `comment` | str \| null | scalar per row | none | free text | `helao/helpers/sample_api.py:107-108` |
| `volume_ml` | float | scalar per row | mL | liquid and gas tables; missing value stored as 0.0 | `helao/helpers/sample_api.py:672`, `:692` |
| `ph` | float \| null | scalar per row | pH | liquid table | `helao/helpers/sample_api.py:672` |
| `dilution_factor` | float | scalar per row | none | liquid and gas tables; missing value stored as 1.0 | `helao/helpers/sample_api.py:672`, `:692` |
| `electrolyte` | str \| null | scalar per row | none | liquid table | `helao/helpers/sample_api.py:672` |
| `parts` | str \| null | scalar per row | none | assembly table; JSON-encoded parts | `helao/helpers/sample_api.py:710` |
| `plate_id` | int | scalar per row | none | solid table | `helao/helpers/sample_api.py:726` |

### Tray actions

**`archive_tray_query_sample`** (`query_sample`, `SS:111`). Row (`SS:119-122`); samples-in record (`SS:118`). Data file `query_sample-*.jsonl` (+ `.meta.json`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `sample` | dict | scalar per row | none | sample dict at the vial (the `NoneSample` dict when the vial is empty or undefined) | `SS:119` |
| `error_code` | str | scalar per row | none | `none`, or `not_available` when the tray/slot is undefined | `SS:119` |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `_fast_samples_in` | `action_params` | dict | list[dict] | one-element list with the same sample dict | `SS:121` |

**`archive_tray_load`** (`load_sample`, `SS:188`). Row (`SS:196-198`); data file `load_sample-*.jsonl` (+ `.meta.json`). The loaded sample is verified in the sample DB first; the in-memory table is updated without a state-file write (see above). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `error_code` | str | scalar per row | none | `none` on success, else `not_available` | `SS:196` |
| `sample` | dict | scalar per row | none | loaded sample dict, DB-refreshed; the `NoneSample` dict on failure | `SS:196` |

**`archive_tray_unload`, `archive_tray_unloadall`** (`unload_sample`, `SS:219`, `:140`). Empty the slot (or every slot), write the state file (`AD:505`, `:544`), mark the unloaded samples `unloaded` and update their DB rows (`AD:1253-1254`). Row (`SS:228-230`, `:149-151`); data file `unload_sample-*.jsonl` (+ `.meta.json`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `unloaded` | bool | scalar per row | none | whether a slot was found (always `true` for unload-all) | `SS:228`, `:149` |
| `tray_dict` | dict | dict | none | `{tray: {slot: vial tray dict}}` as it was before unloading (vial tray dict as above) | `SS:228`, `:149` |

**`archive_tray_new_position`** (action name as abbreviation). Reserves the smallest empty vial that fits `req_vol` (marks it `blocked`, `AD:764-772`). Row (`SS:260-262`); data file `<action name>-*.jsonl`. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `tray` | int \| null | scalar per row | none | tray number; `null` when no vial fits | `AD:781` |
| `slot` | int \| null | scalar per row | none | slot number | `AD:781` |
| `vial` | int \| null | scalar per row | none | 1-based vial number | `AD:781` |

**`archive_tray_update_position`** (action name as abbreviation). Row (`SS:299-305`); writes the state file (`AD:863`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `update` | bool | scalar per row | none | whether the vial was overwritten (`false` for no sample or an undefined position) | `SS:300` |

**`archive_tray_export_json`** (`traytojson`, file type `palvialtable_helao__file`, `SS:327-328`). Row (`SS:330-332`); data file `traytojson-*.jsonl` (+ `.meta.json`). The row is the vial tray dict of the slot (fields in the vial tray table above); when the slot is undefined the driver returns `None` and the queued value is `None`, not a dict; what the data writer does with it was not traced. No action results.

**`archive_tray_export_csv`** (`traytocsv`, `SS:394`). When the slot exists, writes `VialTable__tray<tray>__slot<slot>__<%y%m%d.%H%M%S%f>.csv`, file type `pal_vialtable_file`, tracked on the action (`AD:602-608`). No data row, no action results.

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| vial table | CSV; header line `vial_no,global_sample_label,vol_ml`, then `%%`, then one line per vial: 1-based number, label or the text `None`, volume or `None` | `VialTable__tray<tray>__slot<slot>__<timestamp>.csv` | every vial of the slot, empty ones included | `AD:602-608` |

**`archive_tray_export_icpms`** (`traytoicpms`, `SS:362`). When the slot exists, writes `VialTable__tray<tray>__slot<slot>__<%y%m%d-%H%M%S%f>_ICPMS.csv`, file type `pal_icpms_file`, tracked on the action with the vials' labels as the file's sample labels (`AD:683-690`). No data row, no action results.

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| ICP-MS list | semicolon-separated; header `liquid_sample_no;Survey Runs;Main Runs;Rack;Vial;Dilution Factor`, then `%%`, then one line per loaded non-empty vial (label, the `survey_runs`, `main_runs`, `rack` params as text or `None`, 1-based vial, dilution factor from the param or the sample) | `VialTable__tray<tray>__slot<slot>__<timestamp>_ICPMS.csv` | ICP-MS sample list | `AD:643-690` |

### Custom-position actions

**`archive_custom_load`, `archive_custom_load_solid`** (`load_sample`, `SS:467`, `:425`). Load a sample at a custom position; the state file is rewritten (`AD:1226`). Row (`SS:474-476`, `:435-437`); data file `load_sample-*.jsonl` (+ `.meta.json`).

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `loaded` | bool | scalar per row | none | whether the sample was loaded | `SS:474`, `:435` |
| `customs_dict` | dict | dict | none | the custom position dict after loading (`{}` when nothing was loaded) | `SS:474`, `:435` |

Action results (in `-act.json`), `archive_custom_load_solid` only:

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `load_sample_in` | `action_params` | dict | dict | the `SolidSample` built from the `sample_no` and `plate_id` params | `SS:427` |

**`archive_custom_unload`, `archive_custom_unloadall`** (`unload_sample`, `SS:508`, `:556`). Unload one or every custom position, optionally destroying phases; state file rewritten (`AD:1082`, `:1045`); unloaded samples marked `unloaded` and their DB rows updated (`AD:1253-1254`). Row (`SS:520-522`, `:568-570`); data file `unload_sample-*.jsonl` (+ `.meta.json`).

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `unloaded` | bool | scalar per row | none | whether anything was unloaded | `SS:520`, `:569` |
| `customs_dict` | dict | dict | none | `{name: custom position dict}` as it was before unloading | `SS:520`, `:569` |

Action results (in `-act.json`), `archive_custom_unloadall` only:

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `_unloaded_solid` | `action_params` | dict \| null | dict | sample dict of the first unloaded solid, `null` if none | `SS:583` |
| `_unloaded_liquid` | `action_params` | dict \| null | dict | sample dict of the first unloaded liquid, `null` if none | `SS:584` |
| `_unloaded_liquid_vol` | `action_params` | float \| int | scalar | `volume_ml` of that liquid, or the integer `0` when there is none | `SS:585` |

**`archive_custom_query_sample`** (`query_sample`, `SS:606`). Row (`SS:613-616`); data file `query_sample-*.jsonl`. Same fields as `archive_tray_query_sample` (`sample`, `error_code`, `SS:613`), and the same result:

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `_fast_samples_in` | `action_params` | dict | list[dict] | one-element list with the sample dict | `SS:614` |

**`archive_custom_add_liquid`, `archive_custom_add_gas`** (`add_liquid`, `add_gas`, `SS:655`, `:712`). Add volume to a custom position; created and updated samples go to the sample DB (`AD:1658-1910`) and the state file is rewritten through `custom_replace_sample` (`AD:945`). Row (`SS:673-675`, `:729-731`); data file `add_liquid-*.jsonl` or `add_gas-*.jsonl` (+ `.meta.json`). No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `error_code` | str | scalar per row | none | `ErrorCodes` value (`none` on success) | `SS:673`, `:729` |

### Sample database actions

**`db_get_samples`** (action name as abbreviation). Row (`SS:770-772`); replaces the action's samples-in with the resolved samples. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `samples` | dict | list[dict] | none | resolved sample dicts | `SS:770` |

**`db_new_samples`** (action name as abbreviation). Persists the reference samples as new DB rows (`AD:2023`). Row (`SS:825-828`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `samples` | dict | list[dict] | none | the persisted sample dicts | `SS:826` |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `_fast_sample_out` | `action_params` | dict | dict | first created sample dict; present only when at least one sample was created | `SS:830` |

**`generate_plate_sample_no_list`** (action name as abbreviation). When `plate_id`, `sample_code` and `skip_n_samples` are given and the plate's platemap loads, writes the sample numbers as a text file (`AD:2080-2086`); otherwise nothing. No data row, no action results.

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| sample-number list | text; `%%` line, then one sample number per line | `<plate_id>.txt`, file type `plate_sample_no_list_file`, tracked on the action | every `skip_n_samples`+1-th platemap row whose `code` equals `sample_code` | `AD:2080-2086` |

**`get_loaded_positions`** (route of `get_positions`, action name as abbreviation). No row; writes three results into the action record (`SS:919-925`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `_positions` | `action_params` | dict | dict | whole archive (`trays_dict`, `customs_dict`; same layout as the state file) | `SS:921` |
| `_tray_pos` | `action_params` | str \| null | dict | `{(tray, slot, vial): global label}` for every loaded vial; keys are tuples, see Notes | `SS:922` |
| `_custom_pos` | `action_params` | str \| null | dict | `{custom_name: global label of the loaded sample}`; `null` for an empty position's label | `SS:923` |

### Private endpoints

`/list_new_samples`, `/get_samples`, `/tray_query_sample`, `/tray_get_next_full`, `/custom_query_sample`, `/new_ref_samples`, `/custom_dest_allowed`, `/custom_assembly_allowed` and `/custom_is_destroyed` return values to the caller only. `/new_samples` and `/update_samples` write the sample database; `/tray_new_position` marks a vial `blocked`; `/tray_update_position` and `/custom_update_position` overwrite a position and rewrite the state file (`SS:929-1112`). Used by the PAL server (see `../pal/README.md`). No data files or action results.

## Notes

- `get_loaded_positions` builds `_tray_pos` with `(tray, slot, vial)` tuple keys (`helao/deploy/hte/servers/sample/sample_server.py:906-914`). The metadata writer serializes with `orjson` and `OPT_NON_STR_KEYS` (`helao/helpers/meta_io.py:24`), and `orjson.dumps({(1, 2, 3): "a"}, option=orjson.OPT_NON_STR_KEYS)` raises `TypeError` (checked). Whether the action record reaches that call with these keys, and what happens when it does, was not traced.
- `tray_load` changes the in-memory position table but never calls `write_config` (`helao/deploy/hte/servers/sample/archive_driver.py:409-475`), so a loaded vial is absent from `<host>_archive.json` until a later operation rewrites it; the same holds for the vial `tray_new_position` blocks (`:764-772`).
