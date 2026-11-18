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

Both analyses are queued by an `analyze_<module>` endpoint, run `calc_output` once per sample process and assign the result to `self.outputs`. Inputs are the spectrometer actions' data files read through the loader (`parse_spechlo`, `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:88`: `meta.optional.wl`, `data.epoch_s`, the `ch_*` columns).

### `uvis_bkgsubnorm` (analysis)

Dry UV-Vis background subtraction and normalisation of one sample's UV-Vis acquisition against dark and light references; `DryUvisAnalysis` (analysis name `UVIS_BkgSubNorm`, `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:303`) fills `DryUvisOutputs` at `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:405`. One output record per analysed process; each list field has one entry per pixel (`wavelength`, `mean_ref_*`, `agg_insitu`) or per bin (`bin_*`, `smth_*`, `rscl_*`).

Outputs model `DryUvisOutputs` (`helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:215`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `wavelength` | float | list[float] | nm | wavelength axis of the in-situ spectrum, one entry per spectrometer pixel | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:406` |
| `lower_wl_idx` | int | scalar | none | first pixel index with wavelength above `lower_wl` (default 370) | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:407` |
| `upper_wl_idx` | int | scalar | none | last pixel index with wavelength below `upper_wl` (default 700) | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:408` |
| `mean_ref_dark` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | per-pixel mean of the frames from index `i0` to the end, where `i0` is the first index of `ep[skip_first_n:] - ep.max() >= -agg_last_secs` (an index into the sliced epoch array applied to the unsliced spectra, so the window starts `skip_first_n` frames early; see Notes), then averaged over the dark references | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:409` |
| `mean_ref_light` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | same for the light references | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:410` |
| `agg_method` | str | scalar | none | `mean` or `median`, copied from `analysis_params` | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:411` |
| `agg_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | per-pixel `agg_method` over the frames from index `i0` to the end, where `i0` is the first index of `ep[skip_first_n:] - ep.max() >= -agg_last_secs` (an index into the sliced epoch array applied to the unsliced spectra, so the window starts `skip_first_n` frames early; see Notes) | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:412` |
| `bin_wavelength` | float | list[float] | nm | mean wavelength of each `bin_width`-pixel bin inside the cutoffs | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:413` |
| `bin_insitu` | float | list[float] | dimensionless (reference-adjusted transmittance) | `(agg_insitu - mean_ref_dark) / (mean_ref_light - mean_ref_dark)` binned | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:414` |
| `smth_insitu` | float | list[float] | dimensionless (reference-adjusted transmittance) | `bin_insitu` after the Savitzky-Golay filter | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:415` |
| `rscl_insitu` | float | list[float] | dimensionless (reference-adjusted transmittance) | `smth_insitu` after `refadjust` min/max rescaling | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:416` |
| `insitu_min_rescaled` | bool | scalar | none | true when the minimum was shifted up to `min_limit` | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:417` |
| `insitu_max_rescaled` | bool | scalar | none | true when the maximum was scaled down below 1 | `helao/deploy/hte/servers/analysis/analyses/uvis_bkgsubnorm.py:418` |

S3 artifacts:

| artifact | output_type | content_type | S3 key | written at |
|---|---|---|---|---|
| `scalar` group: every non-list field | none: the outputs model has no `output_type` (see Notes) | `application/json` | `analysis/<analysis_uuid>_output_scalar.json` | `helao/core/drivers/data/analyses/base_analysis.py:139-150` |
| `array` group: every list field | none: the outputs model has no `output_type` (see Notes) | `application/json` | `analysis/<analysis_uuid>_output_array.json` | `helao/core/drivers/data/analyses/base_analysis.py:139-150` |
| analysis model | not applicable | none set (JSON body, uploaded without a `ContentType`) | `analysis/<analysis_uuid>.json` | `helao/core/drivers/data/analysis_layout.py:437-438` |

How the analysis server ships them (`helao/core/drivers/data/analysis_driver.py:1201`): `calc_output` fills `self.outputs`; `export_analysis` (`helao/core/drivers/data/analyses/base_analysis.py:110`) splits the dumped fields into a `scalar` group (non-list values) and an `array` group (list values) and wraps each in an `AnalysisOutputModel` with `content_type` `application/json`. `publish_outputs` (`helao/core/drivers/data/analysis_layout.py:403`) writes each group with stdlib `json.dump` (`write_json`; a NaN is written as bare `NaN`) to `<ANALYSES root>/<yyyy>/<mmdd>/<HHMMSS>__<analysis_name><suffix>/<analysis_uuid>_output_<group>.json` and uploads it to the S3 key above unless the server param `local_only` is true. The model record is written beside them as `<analysis_uuid>-ana.json` (`helao/core/drivers/data/analysis_layout.py:302`).

As shipped, neither outputs model carries an `output_type` attribute, and `export_analysis` reads `self.outputs.output_type` (`helao/core/drivers/data/analyses/base_analysis.py:147`), so the call raises `AttributeError` after `calc_output` has succeeded. No output group, model record or S3 object is written for these two analyses until that is fixed; the tables describe what the code builds up to that point.

### `echeuvis_stability` (analysis)

In-situ ECHE UV-Vis optical stability of one sample from its baseline OCV, in-situ CA and post-CA OCV spectra; `EcheUvisAnalysis` (analysis name `ECHEUVIS_InsituOpticalStability`, `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:502`) fills `EcheUvisOutputs` at `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:714`. One output record per analysed CA process. The reference-dark/light correction is commented out, so the spectra are the raw `ch_*` values.

Outputs model `EcheUvisOutputs` (`helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:367`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `wavelength` | float | list[float] | nm | wavelength axis of the baseline spectrum, one entry per pixel | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:715` |
| `lower_wl_idx` | int | scalar | none | first pixel index with wavelength above `lower_wl` (default 430) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:716` |
| `upper_wl_idx` | int | scalar | none | last pixel index with wavelength below `upper_wl` (default 700) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:717` |
| `mean_ref_dark` | float | list[float] | none | always the empty list (reference correction is commented out) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:720` |
| `mean_ref_light` | float | list[float] | none | always the empty list | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:721` |
| `agg_method` | str | scalar | none | `mean` or `median`, copied from `analysis_params` | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:722` |
| `agg_baseline` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | per-pixel `agg_method` of the baseline frames in the window: the frames from index `i0` to the end, where `i0` is the first index of `ep[skip_first_n:] - ep.max() >= -agg_last_secs` (an index into the sliced epoch array applied to the unsliced spectra, so the window starts `skip_first_n` frames early; see Notes) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:723` |
| `agg_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | in-situ CA spectrum, same window rule (on a failure the fallback indexes `itup[1][0]`, a scalar, instead; `echeuvis_stability.py:610-616`) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:724` |
| `agg_presitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | post-CA OCV spectrum, same window rule (same fallback, `:635-641`) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:725` |
| `bin_wavelength` | float | list[float] | nm | mean wavelength of each `bin_width`-pixel bin inside the cutoffs | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:726` |
| `bin_baseline` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | binned baseline | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:727` |
| `bin_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | binned in-situ | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:728` |
| `bin_presitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | binned post-CA | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:729` |
| `smth_baseline` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | Savitzky-Golay smoothed binned baseline | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:730` |
| `smth_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | smoothed binned in-situ | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:731` |
| `smth_presitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | smoothed binned post-CA | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:732` |
| `rscl_baseline` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | `refadjust` rescaled baseline | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:733` |
| `rscl_insitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | `refadjust` rescaled in-situ | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:734` |
| `rscl_presitu` | float | list[float] | spectrometer `ch_*` value (as stored in the source file) | `refadjust` rescaled post-CA | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:735` |
| `baseline_min_rescaled` | bool | scalar | none | baseline minimum was shifted up | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:736` |
| `baseline_max_rescaled` | bool | scalar | none | baseline maximum was scaled down | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:737` |
| `insitu_min_rescaled` | bool | scalar | none | in-situ minimum was shifted up | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:738` |
| `insitu_max_rescaled` | bool | scalar | none | in-situ maximum was scaled down | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:739` |
| `presitu_min_rescaled` | bool | scalar | none | post-CA minimum was shifted up | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:740` |
| `presitu_max_rescaled` | bool | scalar | none | post-CA maximum was scaled down | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:741` |
| `mean_abs_omT_ratio` | float | scalar | none | mean over bins of `abs(log10((1 - rscl_insitu) / (1 - rscl_baseline)))`; may be NaN | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:742` |
| `mean_abs_omT_diff` | float | scalar | none | mean over bins of `abs((1 - rscl_insitu) - (1 - rscl_baseline))` | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:745` |
| `noagg_wavelength` | float | list[float] | nm | wavelengths inside the cutoffs for the in-situ frames | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:746` |
| `noagg_epoch` | float | list[float] | s | epoch time of each in-situ frame after the first `skip_first_n` | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:747` |
| `noagg_presitu_wavelength` | float | list[float] | nm | wavelengths inside the cutoffs for the post-CA frames | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:748` |
| `noagg_presitu_epoch` | float | list[float] | s | epoch time of each post-CA frame after the first `skip_first_n` | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:749` |
| `noagg_omt_baseline` | float | list[float] | none | `1 - baseline` spectrum inside the cutoffs (raw values, one per pixel) | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:750` |
| `noagg_omt_insitu` | float | array[float, (n_frames, n_pixels)] | none | `1 - spectrum` for every in-situ frame inside the cutoffs | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:751` |
| `noagg_omt_presitu` | float | array[float, (n_frames, n_pixels)] | none | `1 - spectrum` for every post-CA frame inside the cutoffs | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:752` |
| `noagg_omt_ratio` | float | array[float, (n_frames, n_pixels)] | none | `noagg_omt_insitu` divided by `noagg_omt_baseline` per frame | `helao/deploy/hte/servers/analysis/analyses/echeuvis_stability.py:753` |

`noagg_*` arrays have one row per frame kept after skipping the first `skip_first_n` frames and one column per pixel between the two cutoffs.

S3 artifacts: the same three artifacts as for `uvis_bkgsubnorm` (`scalar` group, `array` group, model), with the same `output_type` caveat and the same shipping path.

## Notes

- `analyses` is read in two places (`make_analysis_app` for the endpoints and the journal recovery with the same class map), so a station config needs it set for either to work.
- The `hte` configs only carry this server commented out (`analyses: [icpms_local, xrfs_local]`).
- Neither `DryUvisOutputs` nor `EcheUvisOutputs` has an `output_type` field (both extend `pydantic.BaseModel`, not `AnalysisOutput`), but `export_analysis` reads `self.outputs.output_type` (`helao/core/drivers/data/analyses/base_analysis.py:147`); the call raises `AttributeError` and nothing is published. Checked: `"output_type" in DryUvisOutputs.model_fields` is `False`, likewise for `EcheUvisOutputs`.
- Aggregation window index mismatch: the start index is computed on `ep[skip_first_n:]` but applied to the unsliced spectra array (`uvis_bkgsubnorm.py:352-380`, `echeuvis_stability.py:585-591`, `:622-628`), so the window starts `skip_first_n` frames early. With the defaults (`skip_first_n=4`, `agg_last_secs=2`) and 1 s frames `ep=0..9`, frames 3..9 (6 s) are aggregated, not 7..9.
