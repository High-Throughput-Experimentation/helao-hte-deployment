# htedata

Action server for plate information lookups (platemap, screening-print elements, info-file and print/anneal-record checks) for a `plate_id`. It wraps the legacy `HTEdata` driver, which calls the plate API (`helao/helpers/plate_api.py`).

## Vendor software

No vendor software beyond the env files. The plate API client needs the `HELAO_CREDENTIALS` environment variable (path to its credentials/environment file; see `helao/helpers/plate_api.py`), which is not a vendor package.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `HTEdata_server` (`fast:`)

No module-specific keys. `HTEdata.__init__` stores the params dict as `config_dict` but never reads a key from it (`helao/deploy/hte/servers/htedata/HTEdata_legacy.py:133`). No shipped station config uses this server.

Example:
```yaml
params: {}
```

## Outputs

Every action here queues one row through the framework default data connection, with a single column: file `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`; columns from the first row, `helao/hexagon/adapters/native/data_stream.py:338-349`). No endpoint passes `action_abbr`, so it defaults to the action name (`helao/hexagon/app/action_context.py:190`) and the file is `<action_name>-*.jsonl`. No action sets any `action_params` or `action_output` key. The value comes from the `HTEdata` driver, which proxies `HTEPlateAPI` (`helao/helpers/plate_api.py`); for plate ids below its `legacy_plateid_threshold` and no live info record, the call falls back to `HTELegacyAPI` (`helao/helpers/legacy_api.py`).

### `get_elements_plateid` (action)

Data file `get_elements_plateid-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `elements` | str \| null | list[str] | none | element symbols of the plate's screening print (gases and noble gases filtered out); `null` when no info/print record is found (a bare `null`, not a list) | `helao/deploy/hte/servers/htedata/HTEdata_server.py:50-52` (driver `helao/deploy/hte/servers/htedata/HTEdata_legacy.py:199`) |

### `get_platemap_plateid` (action)

Data file `get_platemap_plateid-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `platemap` | dict \| null | list[dict] | none | one dict per sample of the plate's screening platemap (`null` when none is found; for legacy plate ids without a live record it can also be `[]`, `helao/helpers/legacy_api.py:350-351`) | `helao/deploy/hte/servers/htedata/HTEdata_server.py:67-69` (driver `helao/deploy/hte/servers/htedata/HTEdata_legacy.py:193`; built at `helao/helpers/plate_api.py:216`) |

For live plates each `platemap` dict is one row of the S3 platemap text file (read by `helao/helpers/plate_api.py:get_platemap`), with column names cleaned of `(...)` suffixes and `%` (`helao/helpers/plate_api.py:187-193`). For legacy plate ids the dicts come from the legacy parser (`helao/helpers/legacy_api.py:350-353`) and their keys are not covered by the table below, which describes the live-plate dicts only. The column set and the types of columns other than those below come from that file and are `unknown (dynamic)`:

| key | type | meaning | set at |
|---|---|---|---|
| `A`-`H` | float | (live plates) composition fractions, converted from text where they are strings | `helao/helpers/plate_api.py:209-214` |
| `sample_no` | unknown (dynamic) | copy of the file's `Sample` column | `helao/helpers/plate_api.py:215` |

### `get_platexycalibration` (action)

Stub: the driver returns `None` (`helao/deploy/hte/servers/htedata/HTEdata_legacy.py:171`). Data file `get_platexycalibration-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `platecal` | null | scalar per row | none | always `null` | `helao/deploy/hte/servers/htedata/HTEdata_server.py:84-86` |

### `save_platexycalibration` (action)

Stub: the driver stores nothing and returns `None` (`helao/deploy/hte/servers/htedata/HTEdata_legacy.py:175`). Data file `save_platexycalibration-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `platecal` | null | scalar per row | none | always `null` | `helao/deploy/hte/servers/htedata/HTEdata_server.py:101-103` |

### `check_plateid` (action)

Data file `check_plateid-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `plateid` | bool | scalar per row | none | whether an info record exists for the plate (live API, then legacy share for old ids); the column holds the boolean, not the id | `helao/deploy/hte/servers/htedata/HTEdata_server.py:118` (driver `helao/deploy/hte/servers/htedata/HTEdata_legacy.py:191`) |

### `check_printrecord_plateid` (action)

Data file `check_printrecord_plateid-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `printrecord` | bool | scalar per row | none | whether the plate's info record has a `screening_print_id` | `helao/deploy/hte/servers/htedata/HTEdata_server.py:133-135` (driver `helao/deploy/hte/servers/htedata/HTEdata_legacy.py:187`) |

### `check_annealrecord_plateid` (action)

Data file `check_annealrecord_plateid-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `annealrecord` | bool | scalar per row | none | whether the plate's info record has an `anneals` block | `helao/deploy/hte/servers/htedata/HTEdata_server.py:150-152` (driver `helao/deploy/hte/servers/htedata/HTEdata_legacy.py:183`) |

### `get_info_plateid` (action)

Data file `get_info_plateid-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `info` | dict \| null | list[dict] | none | despite the name, the platemap of the plate's `screening_map_id` (same per-sample dicts as `platemap` above); `null` when the info record is missing or has no `screening_map_id`; legacy plate ids can return `[]` (`helao/helpers/legacy_api.py:350-351`) | `helao/deploy/hte/servers/htedata/HTEdata_server.py:167` (driver `helao/deploy/hte/servers/htedata/HTEdata_legacy.py:179`; `helao/helpers/plate_api.py:218-232`) |
