# calc

Action server for in-sequence calculations (UV-Vis absorbance, CO2 purge check, syringe fill check, OCV and CP bounds) that do not produce `Analysis` models.

## Vendor software

No vendor software beyond the env files.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `calc_server` (`fast:`)

No server-level keys. `Calc.__init__` stores the params dict as `config_dict` (`helao/deploy/hte/servers/calc/calc_driver.py:112`) but nothing reads a key from it. Calculation inputs arrive as per-action parameters instead.

Example:
```yaml
params: {}
```

## Outputs

Actions here queue one dict through the framework default data connection (`active.enqueue_data_dflt`): one JSON line per action in `<action_abbr>-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` plus `.meta.json` header (`helao/hexagon/adapters/native/data_file.py:172`, `:288`). Columns are the keys of that dict (`helao/hexagon/adapters/native/data_stream.py:338-349`); NaN and infinity serialize as `null` (`helao/helpers/to_json.py:39`).

### `calc_uvis_abs` (action)

`action_abbr` is `calcAbs` (`helao/deploy/hte/servers/calc/calc_server.py:73`). Reads the sequence's `acquire_spec` files from disk, queues one row of per-sample figures of merit (`helao/deploy/hte/servers/calc/calc_server.py:80`) and writes one extra data file per entry of `arraydict` (`:104`). When references or data are missing the driver returns `{}, {}` (`helao/deploy/hte/servers/calc/calc_driver.py:375`): the queued row is then an empty dict and no array files are written. No action results.

Data file `calcAbs-*.jsonl` (+ `.meta.json`), one row. Every field is a list with one entry per sample, in `sample_label` order, except where noted. Multi-spectrum fields are reduced to one number per sample by the row-mean of `squeeze_foms` (`helao/deploy/hte/servers/calc/calc_driver.py:741`, defined at `:82-99`); boolean arrays therefore become the fraction of spectra for which the test held.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `1-T-R_av_<lo>_<hi>` | float | list[float] | none | mean of 1-T-R over the photon-energy window `lo`-`hi` eV; present only for T plus R (TR) data. `<lo>`,`<hi>` are consecutive `ev_parts` values formatted with `f"{lo}_{hi}"`, plus one window for the full `ev_parts[0]`-`ev_parts[-1]` range | `helao/deploy/hte/servers/calc/calc_driver.py:588`, `:597` |
| `1-T_av_<lo>_<hi>` | float | list[float] | none | mean of 1-T over the same windows; present for TR and T-only data | `helao/deploy/hte/servers/calc/calc_driver.py:591`, `:600`, `:620`, `:626` |
| `TplusR_0to1` | float | list[float] | none | fraction of spectra whose smoothed 1-T-R stays strictly between 0 and 1 over all bins; TR data only | `helao/deploy/hte/servers/calc/calc_driver.py:603` |
| `T_0to1` | float | list[float] | none | fraction of spectra whose smoothed T signal stays strictly between 0 and 1; TR and T-only data | `helao/deploy/hte/servers/calc/calc_driver.py:607`, `:629` |
| `R_0to1` | float | list[float] | none | same test on the R signal; TR data only | `helao/deploy/hte/servers/calc/calc_driver.py:610` |
| `DR_0to1` | float | list[float] | none | same test on the R signal; R-only (DR) data only | `helao/deploy/hte/servers/calc/calc_driver.py:635` |
| `max_abs` | float | list[float] | absorbance | row-mean of the per-spectrum maximum of the smoothed, reference-adjusted absorbance (`nanmax`) | `helao/deploy/hte/servers/calc/calc_driver.py:639` |
| `abs_hasnan` | float | list[float] | none | fraction of spectra with a NaN in the 410-850 nm bins | `helao/deploy/hte/servers/calc/calc_driver.py:643` |
| `abs_<lo>_<hi>` | float | list[float] | absorbance x eV | minus the trapezoid integral of absorbance over each `ev_parts` window, plus the full range | `helao/deploy/hte/servers/calc/calc_driver.py:651`, `:657` |
| `max_abs2ndderiv` | float | list[float] | none | max of the max-normalized second derivative of absorbance | `helao/deploy/hte/servers/calc/calc_driver.py:661` |
| `min_abs1stderiv` | float | list[float] | none | min of the max-normalized first derivative of absorbance | `helao/deploy/hte/servers/calc/calc_driver.py:664` |
| `<z>_minslope` | float | list[float] | none | minimum smoothed slope of the reference-adjusted quantity `z`; `<z>` is one of `DA`, `IA`, `DF`, `IF` | `helao/deploy/hte/servers/calc/calc_driver.py:684` |
| `sample_label` | str | list[str] | none | solid sample global labels, one per spectrum action | `helao/deploy/hte/servers/calc/calc_driver.py:686` |
| `min_rescaled` | float | list[float] | none | fraction of spectra shifted up by `refadjust` | `helao/deploy/hte/servers/calc/calc_driver.py:687` |
| `max_rescaled` | float | list[float] | none | fraction of spectra scaled down by `refadjust` | `helao/deploy/hte/servers/calc/calc_driver.py:688` |
| `T__action_uuid` | str | list[str] | none | action UUIDs of the T spectra; present when T data exist | `helao/deploy/hte/servers/calc/calc_driver.py:692` |
| `R__action_uuid` | str | list[str] | none | action UUIDs of the R spectra; present when R data exist | `helao/deploy/hte/servers/calc/calc_driver.py:692` |

Array data files, one per `arraydict` key (`helao/deploy/hte/servers/calc/calc_server.py:104-114`; `file_type` `helao_calc__file`, group `helao_files`, tracked on the action so they sync). File `<action_abbr>.<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<key>.jsonl` (+ `.meta.json`, whose `optional.wl` holds the wavelength vector in nm), one JSON line written with stdlib `json.dumps` (`helao/deploy/hte/servers/calc/calc_server.py:91`), so a NaN in an array would be a bare `NaN` token, not `null`. `<key>` is `rawlen_<ref_dark|ref_light>__<T|R>` (`helao/deploy/hte/servers/calc/calc_driver.py:705`) or, per smoothing stage and quantity, one of `<trunclen_bkgsub|interlen_binned|interlen_smooth|interlen_smoothrefadj|interlen_smoothrefadjscl>__<T|R|TR|one_minus_T_minus_R|one_minus_T|abs>` (`:739`; stage name from `lenmap` `:707-713`, quantity from the quantity key, `sig` giving the spectrum name `T`/`R`/`TR`). Columns:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `sample_label` | str | list[str] | none | sample labels, one per spectrum action | `helao/deploy/hte/servers/calc/calc_server.py:84`, `:87-90` |
| `action_uuid` | str | list[str] | none | action UUIDs, same order | `helao/deploy/hte/servers/calc/calc_server.py:85`, `:87-90` |
| `idx_<i>` (zero-padded 4 digits) | float | array[float, (n_samples)] for `rawlen_*` keys; array[float, (n_samples, n_wavelengths)] for the other keys | reflectance/transmission/absorbance as named by the key | column `i` of `zip(*data)`: wavelength index `i` for `rawlen_*` (mean raw spectrum), spectrum index `i` (each element a wavelength vector) for the other keys | `helao/deploy/hte/servers/calc/calc_server.py:86-90` |

### `check_co2_purge` (action)

`action_abbr` is `checkCO2` (`helao/deploy/hte/servers/calc/calc_server.py:133`). Reads the latest `acquire_co2` file of the sequence, queues one row (`helao/deploy/hte/servers/calc/calc_server.py:160`), and, when a repeat purge is needed, POSTs `insert_experiment` to the orchestrator (`:150-157`; the `__insert_experiment__` payload is popped out of the row first, `:147`). Data file `checkCO2-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `epoch` | float | scalar per row | s | wall-clock `time.time()` of the check | `helao/deploy/hte/servers/calc/calc_driver.py:861` |
| `mean_co2_ppm` | float | scalar per row | ppm | mean `co2_ppm` of the latest `acquire_co2` file | `helao/deploy/hte/servers/calc/calc_driver.py:862` |
| `redo_purge` | bool | scalar per row | none | whether the threshold condition requested another purge (still `true` when `max_repeats` stops the repeat, which then inserts no experiment) | `helao/deploy/hte/servers/calc/calc_driver.py:863` |

### `fill_syringe_volume_check` (action)

`action_abbr` is `syringefillvolume` (`helao/deploy/hte/servers/calc/calc_server.py:179`). Queues one row (`helao/deploy/hte/servers/calc/calc_server.py:202`) and, when a refill is needed, POSTs `insert_experiment` to the orchestrator (`:192-199`, payload popped at `:189`). Data file `syringefillvolume-*.jsonl` (+ `.meta.json`), one row. No action results.

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `epoch` | float | scalar per row | s | wall-clock `time.time()` of the check | `helao/deploy/hte/servers/calc/calc_driver.py:925` |
| `syringe_present_volume_ul` | float | scalar per row | uL | copy of the `present_volume_ul` param | `helao/deploy/hte/servers/calc/calc_driver.py:926` |

### `keep_min_ocv` (action)

`action_abbr` is `keepMinOCV` (`helao/deploy/hte/servers/calc/calc_server.py:226`). Data file `keepMinOCV-*.jsonl` (+ `.meta.json`), one row:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `result` | float | scalar per row | V | smaller of the inherited `min_offset_ocv` and `new_ocv + offset_value` (3 substituted for a missing value), clamped to `[lower_limit, upper_limit]` | `helao/deploy/hte/servers/calc/calc_server.py:260` |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `min_offset_ocv` | `action_params` | float | scalar | the clamped `result`, overwriting the inherited value so later actions inherit it | `helao/deploy/hte/servers/calc/calc_server.py:261` |

### `check_CP_Ewe_bounds` (action)

`action_abbr` is `CheckCPEweBounds` (`helao/deploy/hte/servers/calc/calc_server.py:280`). Data file `CheckCPEweBounds-*.jsonl` (+ `.meta.json`), one row:

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `CP_Ewe_V__mean_final` | float \| bool | scalar per row | V | inherited trailing-mean CP Ewe clamped to `[lower_limit, upper_limit]`. A `bool` `False` (the param default, when nothing was inherited) is not replaced by the 0.4 fallback, see Notes | `helao/deploy/hte/servers/calc/calc_server.py:309-311` |

Action results (in `-act.json`):

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `CP_Ewe_V__mean_final` | `action_params` | float \| bool | scalar | the clamped value, overwriting the inherited one | `helao/deploy/hte/servers/calc/calc_server.py:312` |

## Notes

- `check_CP_Ewe_bounds` tests `isinstance(Ewe_V__mean_final, (int, float, np.floating))` (`helao/deploy/hte/servers/calc/calc_server.py:284`), and `bool` is an `int`, so the default `False` passes the test: the 0.4 fallback never applies, and `False` is compared with the limits and written back as `False`. If the `action_params` key were absent, `Ewe_V__mean_final` would be unbound at `:297`.
