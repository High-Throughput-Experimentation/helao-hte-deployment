# analysis

Action server that exposes one `analyze_<module>` endpoint per configured analysis class and runs queued analyses on a worker pool (`AnalysisSyncer`), optionally uploading results to S3.

## Vendor software

No vendor software beyond the env files.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `analysis_server` (`fast:`)

`makeApp` delegates to `make_analysis_app` in `helao/core/drivers/data/analysis_driver.py`, which reads the keys below. `docs/config-schema.md` also lists them.

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `analyses` | no | list[str] | `[]` | Entries of the form `module` or `module:ClassName`. Each is imported from the deployment's analyses package (`servers.analysis.analyses`, falling back to `drivers.data.analyses`) and exposed as endpoint `analyze_<module>`. Without `:ClassName` the module must hold exactly one `BaseAnalysis` subclass. Any entry that fails to load aborts the server. | `helao/core/drivers/data/analysis_driver.py:1388`, `:282` |
| `env_file` | no | str (path) | `world_cfg.helao_credentials_path`, else env `HELAO_CREDENTIALS`, else `thisfiledoesntexist.env` | Credentials `.env` file passed to `HelaoLoader` for the S3 connection. | `helao/core/drivers/data/analysis_driver.py:516` |
| `max_tasks` | no | int | `1` | Number of concurrent worker coroutines. | `helao/core/drivers/data/analysis_driver.py:523` |
| `local_only` | no | bool | `False` | When true, outputs are written locally and nothing is uploaded to S3. | `helao/core/drivers/data/analysis_driver.py:1237` |
| `analysis_recovery_on_startup` | no | bool | `True` | Sweep the pending-request journal (`<STATES>/ana_pending`) at startup. | `helao/core/drivers/data/analysis_driver.py:1507` |
| `analysis_recovery_max_per_startup` | no | int | `250` | Entries re-enqueued per sweep batch; non-integer values fall back to 250. A value `<= 0` becomes 0, which removes the cap (`:793`, `:812`). | `helao/core/drivers/data/analysis_driver.py:787` |
| `analysis_recovery_drain_when_idle` | no | bool | `True` | Keep draining the journal in slices while the server is idle. | `helao/core/drivers/data/analysis_driver.py:1519` |
| `analysis_recovery_idle_poll_seconds` | no | float | `30` | Idle-check interval for that drain; floored at 1 second. | `helao/core/drivers/data/analysis_driver.py:935` |

The analysis modules in `analyses/` (`uvis_bkgsubnorm.py`, `echeuvis_stability.py`) read no server params. They take per-call analysis parameters instead.

Example:
```yaml
params:
  local_only: false
  analyses: [uvis_bkgsubnorm]
```

## Outputs

Both analyses are queued by an `analyze_<module>` endpoint (on eche10, dispatched by the SYNC `dispatch_analysis` post-finish hook; see Notes), which builds a `LocalLoader` on the synced sequence directory and enqueues one analysis per process returned by `select_process_uuids`: the sequence's `run_use == "data"` processes that dispatched `acquire_spec_adv` (`uvis_bkgsubnorm`, `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:219`) or `run_CA` (`echeuvis_stability`, `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:438`). Each runs `calc_output` once and assigns the result to `self.outputs`. Inputs are resolved from one row per dispatched action of every process in the sequence (`local_frame`, `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:114`); the spectra are the spectrometer actions' data files (`parse_spechlo`, `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:52`: `meta.optional.wl`, `data.epoch_s`, the `ch_*` columns). The model's `global_sample_label` is the analysed process's first `samples_in` `global_label`; when that sample is an assembly (the eche10 cell), it is the `global_label` of the assembly's first `solid` part. `local_frame` is built once per `select_process_uuids` call and kept on the loader (`_local_frame`) for the constructors.

### `uvis_bkgsubnorm` (analysis)

Dry UV-Vis background subtraction and normalisation of one sample's UV-Vis acquisition against dark and light references; `DryUvisAnalysis` (analysis name `UVIS_BkgSubNorm`, `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:239`) fills `DryUvisOutputs` at `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:318`. One output record per analysed process; each list field has one entry per pixel (`wavelength`, `mean_ref_*`, `agg_insitu`) or per bin (`bin_*`, `smth_*`, `rscl_*`).

Outputs model `DryUvisOutputs` (`helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:148`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `output_type` | str | scalar | none | always `spectrum.uvis_bkgsubnorm_ref` | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:319` |
| `wavelength` | float | list[float] | nm | wavelength axis of the in-situ spectrum, one entry per spectrometer pixel | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:320` |
| `lower_wl_idx` | int | scalar | none | first pixel index with wavelength above `lower_wl` (default 370) | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:321` |
| `upper_wl_idx` | int | scalar | none | last pixel index with wavelength below `upper_wl` (default 700) | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:322` |
| `mean_ref_dark` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | per-pixel mean of the frames past the first `skip_first_n` whose epoch is within `agg_last_secs` of the last frame (`last_secs_start`, `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:106`), then averaged over the dark references | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:323` |
| `mean_ref_light` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | same for the light references | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:324` |
| `agg_method` | str | scalar | none | `mean` or `median`, copied from `analysis_params` | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:325` |
| `agg_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | per-pixel `agg_method` over the frames past the first `skip_first_n` whose epoch is within `agg_last_secs` of the last frame (`last_secs_start`, `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:106`) | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:326` |
| `bin_wavelength` | float | list[float] | nm | mean wavelength of each `bin_width`-pixel bin inside the cutoffs | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:327` |
| `bin_insitu` | float | list[float] | dimensionless (reference-adjusted transmittance) | `(agg_insitu - mean_ref_dark) / (mean_ref_light - mean_ref_dark)` binned | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:328` |
| `smth_insitu` | float | list[float] | dimensionless (reference-adjusted transmittance) | `bin_insitu` after the Savitzky-Golay filter | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:329` |
| `rscl_insitu` | float | list[float] | dimensionless (reference-adjusted transmittance) | `smth_insitu` after `refadjust` min/max rescaling | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:330` |
| `insitu_min_rescaled` | bool | scalar | none | true when the minimum was shifted up to `min_limit` | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:331` |
| `insitu_max_rescaled` | bool | scalar | none | true when the maximum was scaled down below 1 | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:332` |

S3 artifacts:

| artifact | output_type | content_type | S3 key | written at |
|---|---|---|---|---|
| `scalar` group: every non-list field (includes `output_type`) | `spectrum.uvis_bkgsubnorm_ref` | `application/json` | `analysis/<analysis_uuid>_output_scalar.json` | `helao/core/drivers/data/analyses/base_analysis.py:139-150` |
| `array` group: every list field | `spectrum.uvis_bkgsubnorm_ref` | `application/json` | `analysis/<analysis_uuid>_output_array.json` | `helao/core/drivers/data/analyses/base_analysis.py:139-150` |
| analysis model | not applicable | none set (JSON body, uploaded without a `ContentType`) | `analysis/<analysis_uuid>.json` | `helao/core/drivers/data/analysis_layout.py:437-438` |

How the analysis server ships them (`helao/core/drivers/data/analysis_driver.py:1201`): `calc_output` fills `self.outputs`; `export_analysis` (`helao/core/drivers/data/analyses/base_analysis.py:110`) splits the dumped fields into a `scalar` group (non-list values) and an `array` group (list values) and wraps each in an `AnalysisOutputModel` with `content_type` `application/json`. `publish_outputs` (`helao/core/drivers/data/analysis_layout.py:403`) writes each group with stdlib `json.dump` (`write_json`; a NaN is written as bare `NaN`) to `<ANALYSES root>/<yyyy>/<mmdd>/<HHMMSS>__<analysis_name><suffix>/<analysis_uuid>_output_<group>.json` and uploads it to the S3 key above unless the server param `local_only` is true. The model record is written beside them as `<analysis_uuid>-ana.json` (`helao/core/drivers/data/analysis_layout.py:302`).

### `echeuvis_stability` (analysis)

In-situ ECHE UV-Vis optical stability of one sample from its baseline OCV, in-situ CA and pre-CA OCV spectra (the pre-CA OCV is the OCV just before the analysed CA: the previous CA's recovery OCV, or the baseline OCV for the first CA); `EcheUvisAnalysis` (analysis name `ECHEUVIS_InsituOpticalStability`, `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:458`) fills `EcheUvisOutputs` at `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:614`. One output record per analysed CA process. The reference-dark/light correction is commented out, so the spectra are the raw `ch_*` values.

Outputs model `EcheUvisOutputs` (`helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:321`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `output_type` | str | scalar | none | always `spectrum.echeuvis_stability` | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:615` |
| `wavelength` | float | list[float] | nm | wavelength axis of the baseline spectrum, one entry per pixel | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:616` |
| `lower_wl_idx` | int | scalar | none | first pixel index with wavelength above `lower_wl` (default 430) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:617` |
| `upper_wl_idx` | int | scalar | none | last pixel index with wavelength below `upper_wl` (default 700) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:618` |
| `mean_ref_dark` | float | list[float] | none | always the empty list (reference correction is commented out) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:621` |
| `mean_ref_light` | float | list[float] | none | always the empty list | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:622` |
| `agg_method` | str | scalar | none | `mean` or `median`, copied from `analysis_params` | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:623` |
| `agg_baseline` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | per-pixel `agg_method` of the baseline frames past the first `skip_first_n` whose epoch is within `agg_last_secs` of the last frame (`last_secs_start`, `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:106`) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:624` |
| `agg_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | in-situ CA spectrum, same window rule; when the windowed slice raises for any reason (typically `skip_first_n` leaving no frames), a WARNING is logged and the window is the frames within `agg_last_secs` of the last one, counted over all frames | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:625` |
| `agg_presitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | pre-CA OCV spectrum, same window rule and fallback | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:626` |
| `bin_wavelength` | float | list[float] | nm | mean wavelength of each `bin_width`-pixel bin inside the cutoffs | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:627` |
| `bin_baseline` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | binned baseline | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:628` |
| `bin_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | binned in-situ | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:629` |
| `bin_presitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | binned pre-CA | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:630` |
| `smth_baseline` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | Savitzky-Golay smoothed binned baseline | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:631` |
| `smth_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | smoothed binned in-situ | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:632` |
| `smth_presitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | smoothed binned pre-CA | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:633` |
| `rscl_baseline` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | `refadjust` rescaled baseline | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:634` |
| `rscl_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | `refadjust` rescaled in-situ | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:635` |
| `rscl_presitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | `refadjust` rescaled pre-CA | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:636` |
| `baseline_min_rescaled` | bool | scalar | none | baseline minimum was shifted up | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:637` |
| `baseline_max_rescaled` | bool | scalar | none | baseline maximum was scaled down | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:638` |
| `insitu_min_rescaled` | bool | scalar | none | in-situ minimum was shifted up | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:639` |
| `insitu_max_rescaled` | bool | scalar | none | in-situ maximum was scaled down | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:640` |
| `presitu_min_rescaled` | bool | scalar | none | pre-CA minimum was shifted up | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:641` |
| `presitu_max_rescaled` | bool | scalar | none | pre-CA maximum was scaled down | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:642` |
| `mean_abs_omT_ratio` | float | scalar | none | mean over bins of `abs(log10((1 - rscl_insitu) / (1 - rscl_baseline)))`; may be NaN | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:643` |
| `mean_abs_omT_diff` | float | scalar | none | mean over bins of `abs((1 - rscl_insitu) - (1 - rscl_baseline))` | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:646` |
| `noagg_wavelength` | float | list[float] | nm | wavelengths inside the cutoffs for the in-situ frames | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:647` |
| `noagg_epoch` | float | list[float] | s | epoch time of each in-situ frame after the first `skip_first_n` | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:648` |
| `noagg_presitu_wavelength` | float | list[float] | nm | wavelengths inside the cutoffs for the pre-CA frames | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:649` |
| `noagg_presitu_epoch` | float | list[float] | s | epoch time of each pre-CA frame after the first `skip_first_n` | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:650` |
| `noagg_omt_baseline` | float | list[float] | none | `1 - baseline` spectrum inside the cutoffs (raw values, one per pixel) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:651` |
| `noagg_omt_insitu` | float | array[float, (n_frames, n_pixels)] | none | `1 - spectrum` for every in-situ frame inside the cutoffs | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:652` |
| `noagg_omt_presitu` | float | array[float, (n_frames, n_pixels)] | none | `1 - spectrum` for every pre-CA frame inside the cutoffs | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:653` |
| `noagg_omt_ratio` | float | array[float, (n_frames, n_pixels)] | none | `noagg_omt_insitu` divided by `noagg_omt_baseline` per frame | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:654` |

`noagg_*` arrays have one row per frame kept after skipping the first `skip_first_n` frames and one column per pixel between the two cutoffs.

S3 artifacts: the same three artifacts as for `uvis_bkgsubnorm` (`scalar` group, `array` group, model), with `output_type` `spectrum.echeuvis_stability` and the same shipping path.

## Notes

- `analyses` is read in two places (`make_analysis_app` for the endpoints and the journal recovery with the same class map), so a station config needs it set for either to work.
- `eche10.yml` runs this server as `ANA` (`analyses: [uvis_bkgsubnorm, echeuvis_stability]`, `local_only: true` until its station check passes, so nothing is uploaded yet). Its `SYNC` entry's `postfinish_hooks` dispatch `analyze_uvis_bkgsubnorm` for each finished `UVIS_T` sequence and `analyze_echeuvis_stability` for each `ECHEUVIS_multiCA_led` sequence after the sequence syncs (`helao/core/hooks/builtin/dispatch_analysis.py`); no experiment or sequence dispatches these routes. Other hte configs do not run it.
