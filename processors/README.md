# processors

Finish-hook post-processors for the `hte` deployment. Each module defines a `PostProcess` class that a server's `prefinish_hooks` (or an orchestrator's `prefinish_experiment_hooks` / `prefinish_sequence_hooks`) names by module; the hook runs when an action (or experiment/sequence) finishes and either rewrites the record's `files` list (`HloPostProcessor`, `helao/core/hooks/loader.py:57`) or edits the record in place (`MetaProcessor`, `helao/core/hooks/loader.py:69`). `libs/hispec_calibrate_downsample_parquet.py` is the calibration library behind `hispec_process_all`.

## Outputs

Registration rule for the three file processors: the list returned by `process()` replaces `action.files` (`helao/core/hooks/loader.py:57`). The syncer uploads the record's `files` entries minus those with `nosync` true, so a file is uploaded only if it is returned in that list and its `nosync` is false. A file written into the action directory but not returned is local only.

### `hispec_process_all.PostProcess` (processor)

Runs at the finish of every action on a server whose config has `prefinish_hooks: {hispec_process_all: ["*"]}` (the `ANDOR` server in `helao/deploy/hte/configs/hispec.yml:142-143`; no other `hte` config references it). For each `andor_helao__file` of an action whose experiment is `HISPEC_sub_SpEC` it writes one wavelength-melted parquet dataset, partitioned by `cycle` and `direction`, one row per (binned spectrum, wavelength); writer `helao/deploy/hte/processors/hispec_process_all.py:89`. Writes no `action_params` or `action_output` keys.

Inputs parsed:
- The action's `andor_helao__file` data file (`helao/deploy/hte/processors/hispec_process_all.py:46`), read by `hlo_to_parquet(..., HISPEC=True)` into a temporary parquet (`:57`, deleted at `:66`). That function subtracts the first tick time from `t_s` (`helao/helpers/hlo_data.py:409`), drops the last data column (`:411`) and mean-aggregates the wavelength columns into integer-nanometre bins (`:412`).
- The CV data of the parent experiment: `HelaoData(exp_yml_path).act[3].data[1]`, columns `t_s`, `Ewe_V`, `cycle`, `I_A` (`helao/deploy/hte/processors/hispec_process_all.py:48-50`, `:59`). The fourth action of the experiment is assumed to be the CV.
- The action param `comment` (`:67`), optional, appended to the output name.

Dataset (directory `<data stem>.parquet`, or `<data stem>_<comment>.parquet` when the `comment` param is non-empty, written by `pq.write_to_dataset` with `partition_cols=["cycle", "direction"]` and `basename_template="part-{i}.parquet"`; `helao/deploy/hte/processors/hispec_process_all.py:68-94`). Each partition is one file `<dataset>/cycle=<c>/direction=<d>/part-0.parquet`; the partition values live in the directory names, not in the part files. Columns inside each part file (melted layout, sorted by `t_s` then `wl_nm`, `:83-87`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `t_s` | float | scalar per row | s | time of the spectrum since the first spectrum, averaged within a voltage bin and rounded to 3 decimals | `helao/helpers/hlo_data.py:409`, `helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:615`, renamed at `helao/deploy/hte/processors/hispec_process_all.py:76` |
| `U_V` | float | scalar per row | V | 1 mV voltage bin of the fitted sawtooth voltage, `round(Ewe_V / 0.001) * 0.001`; the `U (V)` index of the calibrated frame | `helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:603`, `:613`, inserted at `helao/deploy/hte/processors/hispec_process_all.py:74` |
| `J_A` | float | scalar per row | A | CV current interpolated onto `t_s` with a smoothing spline | `helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:709`, renamed at `helao/deploy/hte/processors/hispec_process_all.py:78` |
| `wl_nm` | float | scalar per row | nm | wavelength of the spectrometer column (integer-valued: the bin floor); from the melted column labels | `helao/deploy/hte/processors/hispec_process_all.py:83-85` |
| `intensity` | float | scalar per row | spectrometer counts (as stored in the source file) | mean spectrometer signal of that wavelength bin over the rows in the voltage bin | `helao/deploy/hte/processors/hispec_process_all.py:83` |
| `__index_level_0__` | int | scalar per row | none | pandas index of the sorted frame, stored because it is not a range index | `helao/deploy/hte/processors/hispec_process_all.py:90` |

The part-file columns and dtypes above were checked on a synthetic input through the same calls; `cycle` is a float column before partitioning and is not in the part files.

Partition values (directory names):

| partition | type | meaning | written at |
|---|---|---|---|
| `cycle=<c>` | float, rendered by pyarrow as an integer when whole | CV cycle index of the spectrum from the fitted sawtooth interval table | `helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:425` |
| `direction=<d>` | str | `anodic` or `cathodic` scan direction, with misclassified runs flipped | `helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:457`, `:459`, `:504` |

Registration in the record's `files` list: one new `FileInfo` per `part-*.parquet` found under the dataset (`helao/deploy/hte/processors/hispec_process_all.py:100-115`), a copy of the source entry with `file_type` `andor_spec_parquet__file` (`:105`), `file_name` the part path relative to the action directory with forward slashes (`<dataset>/cycle=<c>/direction=<d>/part-0.parquet`, `:106-112`), `nosync` false (`:113`, so uploaded) and `data_keys` the melted columns `t_s, U_V, J_A, cycle, direction, wl_nm, intensity` (`:114`). The original `andor_helao__file` entry is kept (`:121`). An action of another experiment, or an exception (logged, `:117`), leaves only the original entry.

Side file (local only, not registered): the calibration library writes `interpolation.json` into the process's current working directory, not the action directory, overwriting the previous one (`helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:262`):

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| `interpolation.json` | JSON object `{amplitude, period, phase, offset}`, floats | fixed name in the working directory | fitted sawtooth parameters of the CV voltage waveform | `helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:255-263` |

### `hlo_to_csv.PostProcess` (processor)

Runs at the finish of every action on a server whose config lists `hlo_to_csv` under `prefinish_hooks`; no `hte` config does, so it is wired only by name from other deployments' configs. For each data file whose `file_type` ends with `helao__file` and whose name ends `.hlo` or `.jsonl` it writes one CSV, one row per data row; writer `helao/deploy/hte/processors/hlo_to_csv.py:49`. Writes no `action_params` or `action_output` keys.

Inputs parsed: the action's data file, read with `read_hlo` (`helao/deploy/hte/processors/hlo_to_csv.py:37-41`); the action param `comment` (`:43`).

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| CSV copy | CSV with header, no index column | the data file name with its data suffix replaced by `.csv` (`data_sibling`), or `<stem>_<comment>.csv` when the `comment` param is non-empty | the data file's columns, one CSV column per key `read_hlo` returns, in file order; value types are those of the source file (`unknown (dynamic)`: the keys come from the action that wrote the data) | `helao/deploy/hte/processors/hlo_to_csv.py:42-49` |

Registration: a copy of the source `FileInfo` with `file_type` having `helao__file` replaced by `csv__file` and `file_name` the CSV base name (`helao/deploy/hte/processors/hlo_to_csv.py:50-55`); `nosync` and `data_keys` are inherited from the source entry (not reset), so the CSV is uploaded unless the source is `nosync`. The source entry is kept (`:61`).

### `spec_melt_wls.PostProcess` (processor)

Runs at the finish of every action on a server whose config lists `spec_melt_wls` under `prefinish_hooks`; no `hte` config does, so it is wired only by name from other deployments' configs. For each `spec_r_helao__file` or `spec_t_helao__file` it writes one wavelength-melted parquet file, one row per (spectrum, wavelength), and deletes the source data file; writer `helao/deploy/hte/processors/spec_melt_wls.py:69`. Writes no `action_params` or `action_output` keys.

Inputs parsed: the action's spectrum data file read with `read_hlo`; header `optional.wl` gives the wavelengths, rounded to 3 decimals, and the `ch_*` columns (sorted by name) are paired with them (`helao/deploy/hte/processors/spec_melt_wls.py:38-62`); the action param `comment` (`:44`).

Parquet file `<data stem>.parquet` (or `<data stem>_<comment>.parquet`), sorted by `t_s` then `wl_nm` (`helao/deploy/hte/processors/spec_melt_wls.py:45-49`, `:67`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `t_s` | float | scalar per row | s | `epoch_s` minus its minimum over the file | `helao/deploy/hte/processors/spec_melt_wls.py:52` |
| `epoch_s` | float | scalar per row | s | epoch time of the spectrum, from the source data | `helao/deploy/hte/processors/spec_melt_wls.py:56` |
| `peak_intensity` | unknown (dynamic) | scalar per row | spectrometer counts (as stored in the source file) | `peak_intensity` column of the source data, written by the spectrometer server | `helao/deploy/hte/processors/spec_melt_wls.py:56` |
| `wl_nm` | float | scalar per row | nm | wavelength of the channel, the `optional.wl` entry paired with the `ch_*` column | `helao/deploy/hte/processors/spec_melt_wls.py:58-65` |
| `intensity` | unknown (dynamic) | scalar per row | spectrometer counts (as stored in the source file) | value of the `ch_*` column at that wavelength | `helao/deploy/hte/processors/spec_melt_wls.py:63` |
| `__index_level_0__` | int | scalar per row | none | pandas index of the sorted frame, stored because it is not a range index | `helao/deploy/hte/processors/spec_melt_wls.py:69` |

The column set was checked on a synthetic frame through the same calls. The source `error_code` column is dropped (`:53`). Any other source column that is neither `ch_*` nor one of `t_s, epoch_s, peak_intensity` is melted as a wavelength row and makes the float cast at `:65` raise; the exception is caught, logged and the source file is kept (`:99-103`).

Registration: a copy of the source `FileInfo` with `file_type` ending `_parquet__file` instead of `_helao__file` (`spec_r_parquet__file` or `spec_t_parquet__file`), `file_name` the parquet base name, `nosync` false and `data_keys` the five columns above (`helao/deploy/hte/processors/spec_melt_wls.py:75-87`). The source entry is not kept: the `.hlo`/`.jsonl` is deleted, and for a `.jsonl` its `.meta.json` too (`:90-95`). A source file of another type is passed through unchanged (`:96-97`).

### `append_params.PostProcess` (processor)

Runs at experiment or sequence finalization on an orchestrator whose config lists `append_params` under `prefinish_experiment_hooks` or `prefinish_sequence_hooks`; no `hte` config does, so it is wired only by name from other deployments' configs. It adds one constant marker key to the record's params; writer `helao/deploy/hte/processors/append_params.py:20`, `:22`. Writes no files.

Inputs parsed: the in-memory experiment or sequence record (`MetaProcessor.meta`, selected by `meta_type`, `helao/deploy/hte/processors/append_params.py:19`, `:21`).

| key | in | type | structure | meaning | set at |
|---|---|---|---|---|---|
| `appended_exp_param` | `experiment_params` | str | scalar | constant `"yes"`, experiments only | `helao/deploy/hte/processors/append_params.py:20` |
| `appended_seq_param` | `sequence_params` | str | scalar | constant `"yes"`, sequences only | `helao/deploy/hte/processors/append_params.py:22` |

### `libs/hispec_calibrate_downsample_parquet.py` (script)

Library called by `hispec_process_all`; its pipeline entry `fully_read_and_calibrate_parquet` returns a DataFrame and writes a file only when `write_file=True` (`helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:835-840`). `hispec_process_all` passes `write_file=False` (`helao/deploy/hte/processors/hispec_process_all.py:61`), so through that caller the only file it writes is `interpolation.json` (documented above). The returned frame is the content of the dataset above. The `__main__` block (`:845-851`, hard-coded developer paths) calls it with `write_file=True`.

Inputs parsed: a CV DataFrame or `.hlo` path (`read_CV_hlo`, `:25`), columns `Ewe_V`, `t_s`, `cycle`, `I_A` by default; a spectra parquet with a `t_s` column and one column per wavelength (`read_spec_times_from_parquet`, `read_spectra_parquet`, `:130`, `:156`).

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| calibrated parquet | parquet, zstd, wide layout: `t (s)`, `J (A)`, `direction`, `cycle`, one column per wavelength, index `U (V)` | `<output_path>spectra_calibrated.parquet` (default `spectra_calibrated.parquet` in the working directory); only when `write_file=True` or via `__main__` | calibrated, 1 mV-downsampled spectra of a CV | `helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:840` |
| `interpolation.png` | PNG | fixed name in the working directory; only when `plotbl=True` (not passed by `fully_read_and_calibrate_parquet`) | sawtooth fit against the CV voltage | `helao/deploy/hte/processors/libs/hispec_calibrate_downsample_parquet.py:252` |
