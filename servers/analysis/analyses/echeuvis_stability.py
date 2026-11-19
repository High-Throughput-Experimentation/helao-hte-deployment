"""In-situ ECHE-UV-Vis optical stability analysis.

Reads an ``ECHEUVIS_multiCA_led`` sequence through a ``LocalLoader``
(:func:`local_frame`), aligns baseline-OCV, in-situ-CA, and
pre-CA OCV spectra for one in-situ CA process, performs
background-style normalisation, binning, Savitzky-Golay smoothing and
reference clipping, and emits per-sample stability figures of merit via
:class:`EcheUvisAnalysis`.
"""

import sys
from copy import copy
from datetime import datetime
from uuid import UUID

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.stats import binned_statistic

from helao.core.version import get_filehash
from helao.helpers import helao_logging as logging

LOGGER = logging.make_logger(__file__) if logging.LOGGER is None else logging.LOGGER
from helao.core.drivers.data.analyses.base_analysis import BaseAnalysis
from helao.core.drivers.data.loaders.localfs import (
    HelaoAction,
    HelaoProcess,
    LocalLoader,
)
from helao.core.models.analysis import AnalysisDataModel, AnalysisInput, AnalysisOutput
from helao.core.models.run_use import RunUse

ANALYSIS_DEFAULTS = {
    "ev_parts": [1.8, 2.2, 2.6, 3.0],
    "bin_width": 3,
    "window_length": 45,
    "poly_order": 4,
    "lower_wl": 430,
    "upper_wl": 700,
    "max_mthd_allowed": 1.2,
    "max_limit": 0.99,
    "min_mthd_allowed": -0.2,
    "min_limit": 0.01,
    "delta": 1.0,
    "skip_first_n": 4,
    "agg_last_secs": 2,
    "agg_method": "mean",
}


def parse_spechlo(hlod: dict):
    """Decode a spectrometer hlo dict into ``(wavelength, epoch, spectra)``.

    Returns ``False`` and logs the failure when parsing raises an
    exception.
    """
    try:
        wl = np.array(hlod["meta"]["optional"]["wl"])
        epochs = np.array(hlod["data"]["epoch_s"])
        specarr = (
            pd.DataFrame(hlod["data"])
            .sort_index(axis=1)
            .drop([x for x in hlod["data"].keys() if not x.startswith("ch_")], axis=1)
            .to_numpy()
        )
    except Exception:
        LOGGER.error(
            "Failed to parse spectrometer hlo: %s",
            hlod.get("meta", {}).get("optional", {}).get("name", "unknown"),
            exc_info=True,
        )
        return False
    return wl, epochs, specarr


def refadjust(v, min_mthd_allowed, max_mthd_allowed, min_limit, max_limit) -> tuple:
    """Clip and rescale rows of ``v`` to ``[min_limit, max_limit]``.

    Rows whose minimum sits in ``[min_mthd_allowed, min_limit)`` are
    shifted up; rows whose maximum sits in ``[max_limit,
    max_mthd_allowed]`` are scaled down to one.

    Returns:
        ``(min_rescaled_mask, max_rescaled_mask, adjusted_array)``.
    """
    w = copy(v)
    min_rescaled = np.bitwise_and(
        (w.min(axis=-1) >= min_mthd_allowed),
        (w.min(axis=-1) < min_limit),
    )
    w[min_rescaled] = (
        w[min_rescaled] - w[min_rescaled].min(axis=-1).reshape(-1, 1) + min_limit
    )
    max_rescaled = np.bitwise_and(
        (w.max(axis=-1) <= max_mthd_allowed),
        (w.max(axis=-1) >= max_limit),
    )
    w[max_rescaled] = w[max_rescaled] / (
        w[max_rescaled].max(axis=-1).reshape(-1, 1) + 0.02
    )

    return min_rescaled, max_rescaled, w


def last_secs_start(ep, skip: int, secs: float) -> int:
    """First frame index, into the UNSLICED frame array, past ``skip`` and inside the last ``secs``.

    Raises ``ValueError`` when ``skip`` leaves no frames.
    """
    return skip + np.where((ep[skip:] - ep.max()) >= -secs)[0].min()


def local_frame(local_loader: LocalLoader) -> pd.DataFrame:
    """One row per dispatched action of every process ``local_loader`` indexed.

    Stands in for the retired DB query: the columns the input resolvers select
    on, plus the loaded process (``prc``) and action (``act``) records.
    """
    rows = []
    for idx, prow in local_loader.processes.iterrows():
        prc = local_loader.get_prc(idx)
        sample = (prc.json.get("samples_in") or [{}])[0]
        if sample.get("sample_type") == "assembly":
            # a cell assembly carries the solid as one of its parts
            solids = [
                p for p in sample.get("parts", []) if p.get("sample_type") == "solid"
            ]
            sample = solids[0] if solids else sample
        for abbr in prc.json.get("dispatched_actions_abbr", []):
            act = local_loader.resolve_action(
                abbr["action_uuid"], abbr["action_output_dir"]
            )
            rows.append(
                {
                    "process_uuid": prow.process_uuid,
                    "run_use": str(prc.json.get("run_use") or "data"),
                    "experiment_name": prow.experiment_name,
                    "global_label": sample.get("global_label"),
                    "action_uuid": str(act.action_uuid),
                    "action_name": act.action_name,
                    "action_timestamp": str(act.action_timestamp),
                    "prc": prc,
                    "act": act,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "process_uuid",
            "run_use",
            "experiment_name",
            "global_label",
            "action_uuid",
            "action_name",
            "action_timestamp",
            "prc",
            "act",
        ],
    )


class EcheUvisInputs(AnalysisInput):
    """Resolved baseline/in-situ/pre-situ processes and actions for one sample.

    Attributes:
        baseline: Pre-CA OCV process used as the optical baseline.
        baseline_spec_act: Spectrometer action paired with the baseline.
        baseline_ocv_act: ``run_OCV`` action of the baseline.
        insitu: In-situ CA process under analysis.
        insitu_spec_act: Spectrometer action during the CA hold.
        insitu_ca_act: ``run_CA`` action for the in-situ process.
        presitu: Pre-CA OCV process (the OCV just before this CA: the previous CA's recovery OCV, or the baseline OCV for the first CA) used as the recovery reference.
        presitu_spec_act: Spectrometer action during the pre-CA OCV.
        presitu_ocv_act: ``run_OCV`` action for the pre-CA OCV.
        process_params: ``process_params`` dict from the in-situ row.
    """

    # ref_darks: list[HelaoProcess]
    # ref_dark_spec_acts: list[HelaoAction]
    # ref_lights: list[HelaoProcess]
    # ref_light_spec_acts: list[HelaoAction]
    baseline: HelaoProcess
    baseline_spec_act: HelaoAction
    baseline_ocv_act: HelaoAction
    insitu: HelaoProcess
    insitu_spec_act: HelaoAction
    insitu_ca_act: HelaoAction
    presitu: HelaoProcess
    presitu_spec_act: HelaoAction
    presitu_ocv_act: HelaoAction
    process_params: dict
    # solid_samples: list

    def __init__(self, insitu_process_uuid: UUID, frame: pd.DataFrame):
        """Resolve the baseline / in-situ / pre-situ acts from ``frame``.

        Args:
            insitu_process_uuid: Process UUID of the in-situ CA run.
            frame: :func:`local_frame` of the sequence.
        """
        frame = frame.sort_values("action_timestamp", kind="stable")
        data = frame[frame.run_use == "data"]
        ins = frame[frame.process_uuid == insitu_process_uuid]
        self.insitu = ins.iloc[0].prc
        self.global_label = ins.iloc[0].global_label
        self.process_params = self.insitu.process_params
        self.insitu_spec_act = ins[ins.action_name == "acquire_spec_extrig"].iloc[0].act
        self.insitu_ca_act = ins[ins.action_name == "run_CA"].iloc[0].act

        # the data OCV/CA action just before this CA is its presitu reference:
        # the OCV after the previous CA, or the baseline OCV for the first CA
        eche_acts = data[data.action_name.isin(["run_OCV", "run_CA"])]
        presitu_ocv_idx = (
            list(eche_acts.action_uuid).index(str(self.insitu_ca_act.action_uuid)) - 1
        )
        self.presitu_ocv_act = eche_acts.iloc[presitu_ocv_idx].act
        self.presitu = eche_acts.iloc[presitu_ocv_idx].prc
        ocv_specs = data[
            data.action_name.isin(["run_OCV", "acquire_spec_extrig"])
            & (data.experiment_name == "ECHEUVIS_sub_OCV_led")
        ]
        presitu_spec_idx = (
            list(ocv_specs.action_uuid).index(str(self.presitu_ocv_act.action_uuid)) - 1
        )
        self.presitu_spec_act = ocv_specs.iloc[presitu_spec_idx].act

        # the sample's first OCV experiment is the optical baseline
        bdf = data[
            (data.experiment_name == "ECHEUVIS_sub_OCV_led")
            & (data.global_label == self.global_label)
        ]
        self.baseline = bdf.iloc[0].prc
        self.baseline_spec_act = (
            bdf[bdf.action_name == "acquire_spec_extrig"].iloc[0].act
        )
        self.baseline_ocv_act = data[data.action_name == "run_OCV"].iloc[0].act

    # @property
    # def ref_dark_spec(self):
    #     return [x.hlo for x in self.ref_dark_spec_acts]

    # @property
    # def ref_light_spec(self):
    #     return [x.hlo for x in self.ref_light_spec_acts]

    @property
    def baseline_spec(self):
        """Loaded ``.hlo`` payload for the baseline spectrometer action."""
        return self.baseline_spec_act.hlo

    @property
    def baseline_ocv(self):
        """Loaded ``.hlo`` payload for the baseline OCV action."""
        return self.baseline_ocv_act.hlo

    @property
    def insitu_spec(self):
        """Loaded ``.hlo`` payload for the in-situ spectrometer action."""
        return self.insitu_spec_act.hlo

    @property
    def insitu_ca(self):
        """Loaded ``.hlo`` payload for the in-situ CA action."""
        return self.insitu_ca_act.hlo

    @property
    def presitu_spec(self):
        """Loaded ``.hlo`` payload for the pre-CA spectrometer action."""
        return self.presitu_spec_act.hlo

    @property
    def presitu_ocv(self):
        """Loaded ``.hlo`` payload for the pre-CA OCV action."""
        return self.presitu_ocv_act.hlo

    def get_datamodels(
        self, global_sample_label: str, *args, **kwargs
    ) -> list[AnalysisDataModel]:
        """Build :class:`AnalysisDataModel` entries for each spec action.

        Args:
            global_sample_label: Override for the resulting
                ``global_sample_label`` field; falls back to the analysed
                process's first ``samples_in`` ``global_label`` for
                data/baseline inputs.
        """
        action_keys = [k for k in vars(self).keys() if "spec_act" in k]
        inputs = []
        for ak in action_keys:
            euis = vars(self)[ak]
            ru = (
                ak.split("_spec")[0]
                .replace("insitu", "data")
                .replace("presitu", "preca_baseline")
            )
            if not isinstance(euis, list):
                euis = [euis]
            for eui in euis:
                filename, filetype, datakeys = eui.hlo_file_tup
                raw_data_path = f"raw_data/{eui.action_uuid}/{filename}"
                if global_sample_label is not None:
                    global_sample = global_sample_label
                elif ru in ["data", "baseline", "preca_baseline"]:
                    global_sample = self.global_label
                else:
                    global_sample = None
                adm = AnalysisDataModel(
                    action_uuid=eui.action_uuid,
                    run_use=RunUse(ru),
                    raw_data_path=raw_data_path,
                    global_sample_label=global_sample,
                    file_type=filetype,
                    file_name=filename,
                    data_keys=datakeys,
                )
                inputs.append(adm)
        return inputs


class EcheUvisOutputs(AnalysisOutput):
    """Per-sample output payload for :class:`EcheUvisAnalysis`.

    Attributes:
        wavelength: Full spectrometer wavelength axis.
        lower_wl_idx: Index of the lower wavelength cutoff.
        upper_wl_idx: Index of the upper wavelength cutoff.
        mean_ref_dark: Mean dark-reference vector (currently empty).
        mean_ref_light: Mean light-reference vector (currently empty).
        agg_method: Aggregation method (``"mean"`` or ``"median"``).
        agg_baseline: Aggregated baseline OCV spectrum.
        agg_insitu: Aggregated in-situ CA spectrum.
        agg_presitu: Aggregated pre-CA OCV spectrum.
        bin_wavelength: Binned wavelength axis.
        bin_baseline: Binned baseline spectrum.
        bin_insitu: Binned in-situ spectrum.
        bin_presitu: Binned pre-CA spectrum.
        smth_baseline: Smoothed binned baseline.
        smth_insitu: Smoothed binned in-situ.
        smth_presitu: Smoothed binned pre-CA.
        rscl_baseline: Rescaled baseline.
        rscl_insitu: Rescaled in-situ.
        rscl_presitu: Rescaled pre-CA.
        baseline_min_rescaled: Whether the baseline min was rescaled.
        baseline_max_rescaled: Whether the baseline max was rescaled.
        insitu_min_rescaled: Whether the in-situ min was rescaled.
        insitu_max_rescaled: Whether the in-situ max was rescaled.
        presitu_min_rescaled: Whether the pre-CA min was rescaled.
        presitu_max_rescaled: Whether the pre-CA max was rescaled.
        mean_abs_omT_ratio: Mean over wavelengths of
            ``|log10((1-T_insitu)/(1-T_baseline))|``.
        mean_abs_omT_diff: Mean absolute ``(1-T)`` difference.
        noagg_wavelength: Wavelength axis for un-aggregated in-situ.
        noagg_epoch: Epoch axis for un-aggregated in-situ.
        noagg_presitu_wavelength: Wavelength axis for un-aggregated
            pre-CA.
        noagg_presitu_epoch: Epoch axis for un-aggregated pre-CA.
        noagg_omt_baseline: ``1-T`` reference-adjusted baseline.
        noagg_omt_insitu: Per-frame ``1-T`` for in-situ.
        noagg_omt_presitu: Per-frame ``1-T`` for pre-CA.
        noagg_omt_ratio: Per-frame ratio in-situ/baseline.
    """

    wavelength: list
    lower_wl_idx: int
    upper_wl_idx: int
    mean_ref_dark: list  # mean over start and end reference dark spectra
    mean_ref_light: list  # mean over start and end reference light spectra
    agg_method: str
    agg_baseline: list  # mean over final t seconds of OCV
    agg_insitu: list  # mean over final t seconds of CA
    agg_presitu: list  # mean over final t seconds of CA
    bin_wavelength: list
    bin_baseline: list
    bin_insitu: list
    bin_presitu: list
    smth_baseline: list
    smth_insitu: list
    smth_presitu: list
    rscl_baseline: list
    rscl_insitu: list
    rscl_presitu: list
    baseline_min_rescaled: bool
    baseline_max_rescaled: bool
    insitu_min_rescaled: bool
    insitu_max_rescaled: bool
    presitu_min_rescaled: bool
    presitu_max_rescaled: bool
    mean_abs_omT_ratio: float  # mean over wavelengths
    mean_abs_omT_diff: float  # mean over wavelengths
    noagg_wavelength: list
    noagg_epoch: list
    noagg_presitu_wavelength: list
    noagg_presitu_epoch: list
    noagg_omt_baseline: list
    noagg_omt_insitu: list
    noagg_omt_presitu: list
    noagg_omt_ratio: list


class EcheUvisAnalysis(BaseAnalysis):
    """In-situ ECHE-UVIS optical-stability analysis for one CA process.

    Attributes:
        analysis_name: Fixed analysis name string.
        analysis_timestamp: Time the analysis instance was built.
        analysis_uuid: Generated analysis UUID.
        analysis_params: Effective parameters (defaults merged with
            caller overrides).
        ca_potential_vrhe: CA potential vs. RHE used in the in-situ
            process.
        process_uuid: UUID of the in-situ CA process.
        process_timestamp: Timestamp of that process.
        process_name: Technique name from the row.
        run_type: Run type (e.g. ``echeuvis``).
        technique_name: Technique-name string.
        inputs: Resolved :class:`EcheUvisInputs`.
        outputs: Populated :class:`EcheUvisOutputs` after
            :meth:`calc_output`.
        analysis_codehash: Hash of the analysis source file.
    """

    analysis_name: str
    analysis_timestamp: datetime
    analysis_uuid: UUID
    analysis_params: dict
    ca_potential_vrhe: float | None
    process_uuid: UUID
    process_timestamp: datetime
    process_name: str
    run_type: str
    technique_name: str
    inputs: AnalysisInput
    outputs: EcheUvisOutputs
    analysis_codehash: str

    @classmethod
    def select_process_uuids(cls, local_loader) -> list:
        """The sequence's ``run_use == data`` CA processes (the in-situ targets)."""
        f = local_loader._local_frame = local_frame(local_loader)
        sel = f[(f.run_use == "data") & (f.action_name == "run_CA")]
        return list(dict.fromkeys(sel.process_uuid))

    def __init__(
        self,
        process_uuid: UUID,
        local_loader: LocalLoader,
        analysis_params: dict,
    ):
        """Build inputs from the loader's sequence and generate the UUID.

        Args:
            process_uuid: UUID of the in-situ CA process.
            local_loader: ``LocalLoader`` bound to the sequence.
            analysis_params: Overrides merged into
                :data:`ANALYSIS_DEFAULTS`.
        """
        self.analysis_name = "ECHEUVIS_InsituOpticalStability"
        self.analysis_timestamp = datetime.now()
        self.analysis_params = copy(ANALYSIS_DEFAULTS)
        self.analysis_params.update(analysis_params)
        # select_process_uuids stores the frame on the loader (one build per sequence)
        frame = getattr(local_loader, "_local_frame", None)
        if frame is None:
            frame = local_frame(local_loader)
        self.inputs = EcheUvisInputs(process_uuid, frame)
        prc = self.inputs.insitu
        self.process_uuid = process_uuid
        self.process_timestamp = prc.process_timestamp
        self.process_name = prc.technique_name
        self.run_type = prc.json.get("run_type")
        self.run_use = "data"
        self.technique_name = prc.technique_name
        self.campaign_name = prc.json.get("campaign_name")
        self.campaign_uuid = prc.json.get("campaign_uuid")
        self.ca_potential_vrhe = self.inputs.process_params.get("CA_potential_vsRHE")
        self.analysis_codehash = get_filehash(sys._getframe().f_code.co_filename)
        self.analysis_codepath = sys._getframe().f_code.co_filename
        self.analysis_classname = self.__class__.__name__
        self.analysis_uuid = self.gen_uuid()

    def calc_output(self) -> bool:
        """Calculate stability FOMs and intermediate vectors.

        Parses the three spectrometer hlos, aggregates the last
        ``agg_last_secs`` seconds of each (skipping ``skip_first_n``
        frames), bins, smooths and rescales the spectra, and finally
        populates :attr:`outputs`.

        Returns:
            ``True`` on success, ``False`` when any spectrometer parse
            fails.
        """
        # rdtups = [parse_spechlo(x) for x in self.inputs.ref_dark_spec]
        # rltups = [parse_spechlo(x) for x in self.inputs.ref_light_spec]
        btup = parse_spechlo(self.inputs.baseline_spec)
        itup = parse_spechlo(self.inputs.insitu_spec)
        ptup = parse_spechlo(self.inputs.presitu_spec)

        # if any([x is False for x in rdtups + rltups + [btup, itup]]):
        if any([x is False for x in [btup, itup, ptup]]):
            return False

        ap = self.analysis_params
        aggfunc = np.mean if ap["agg_method"] == "mean" else np.median
        wl = btup[0]
        wlindlo = np.where(wl > ap["lower_wl"])[0].min()
        wlindhi = np.where(wl < ap["upper_wl"])[0].max()

        skip, secs = ap["skip_first_n"], ap["agg_last_secs"]
        # aggregate baseline insitu OCV spectra over final t seconds, omitting first n
        agg_baseline = aggfunc(btup[2][last_secs_start(btup[1], skip, secs) :], axis=0)

        # aggregate insitu CA spectra over final t seconds, omitting first n
        try:
            agg_insitu = aggfunc(
                itup[2][last_secs_start(itup[1], skip, secs) :], axis=0
            )
        except Exception:
            LOGGER.warning(
                f"Cannot skip first {ap['skip_first_n']} spectra of insitu CA, aggregating last {ap['agg_last_secs']} seconds.",
                exc_info=True,
            )
            agg_insitu = aggfunc(
                itup[2][np.where((itup[1] - itup[1].max()) >= -secs)[0].min() :],
                axis=0,
            )

        # aggregate presitu OCV spectra over final t seconds, omitting first n
        try:
            agg_presitu = aggfunc(
                ptup[2][last_secs_start(ptup[1], skip, secs) :], axis=0
            )
        except Exception:
            LOGGER.warning(
                f"Cannot skip first {ap['skip_first_n']} spectra of presitu CA, aggregating last {ap['agg_last_secs']} seconds.",
                exc_info=True,
            )
            agg_presitu = aggfunc(
                ptup[2][np.where((ptup[1] - ptup[1].max()) >= -secs)[0].min() :],
                axis=0,
            )

        inds = range(len(wl[wlindlo:wlindhi]))
        nbins = np.round(len(wl[wlindlo:wlindhi]) / ap["bin_width"]).astype(int)
        refadj_baseline = (
            # (agg_baseline - mean_ref_dark) / (mean_ref_light - mean_ref_dark)
            agg_baseline
        )[wlindlo:wlindhi]
        refadj_insitu = (
            # (agg_insitu - mean_ref_dark) / (mean_ref_light - mean_ref_dark)
            agg_insitu
        )[wlindlo:wlindhi]
        refadj_presitu = (
            # (agg_presitu - mean_ref_dark) / (mean_ref_light - mean_ref_dark)
            agg_presitu
        )[wlindlo:wlindhi]
        bin_wl = binned_statistic(inds, wl[wlindlo:wlindhi], "mean", nbins).statistic
        bin_baseline = binned_statistic(inds, refadj_baseline, "mean", nbins).statistic
        bin_insitu = binned_statistic(inds, refadj_insitu, "mean", nbins).statistic
        bin_presitu = binned_statistic(inds, refadj_presitu, "mean", nbins).statistic
        smth_baseline = savgol_filter(
            bin_baseline, ap["window_length"], ap["poly_order"], delta=ap["delta"]
        )
        smth_insitu = savgol_filter(
            bin_insitu, ap["window_length"], ap["poly_order"], delta=ap["delta"]
        )
        smth_presitu = savgol_filter(
            bin_presitu, ap["window_length"], ap["poly_order"], delta=ap["delta"]
        )
        baseline_min_rscl, baseline_max_rscl, rscl_baseline = refadjust(
            smth_baseline,
            ap["min_mthd_allowed"],
            ap["max_mthd_allowed"],
            ap["min_limit"],
            ap["max_limit"],
        )
        insitu_min_rscl, insitu_max_rscl, rscl_insitu = refadjust(
            smth_insitu,
            ap["min_mthd_allowed"],
            ap["max_mthd_allowed"],
            ap["min_limit"],
            ap["max_limit"],
        )
        presitu_min_rscl, presitu_max_rscl, rscl_presitu = refadjust(
            smth_presitu,
            ap["min_mthd_allowed"],
            ap["max_mthd_allowed"],
            ap["min_limit"],
            ap["max_limit"],
        )

        wls_insitu = itup[0][wlindlo:wlindhi]
        eps_insitu = itup[1][ap["skip_first_n"] :]
        arr_insitu = itup[2][ap["skip_first_n"] :]
        refadj_arr_insitu = (
            # (arr_insitu - mean_ref_dark) / (mean_ref_light - mean_ref_dark)
            arr_insitu
        )[:, wlindlo:wlindhi]
        omt_arr_insitu = 1 - refadj_arr_insitu
        omt_refadj_baseline = 1 - refadj_baseline
        arr_omt_ratio = omt_arr_insitu / omt_refadj_baseline

        wls_presitu = ptup[0][wlindlo:wlindhi]
        eps_presitu = ptup[1][ap["skip_first_n"] :]
        arr_presitu = ptup[2][ap["skip_first_n"] :]
        refadj_arr_presitu = (
            # (arr_presitu - mean_ref_dark) / (mean_ref_light - mean_ref_dark)
            arr_presitu
        )[:, wlindlo:wlindhi]
        omt_arr_presitu = 1 - refadj_arr_presitu

        # create output model
        self.outputs = EcheUvisOutputs(
            output_type="spectrum.echeuvis_stability",
            wavelength=list(wl),
            lower_wl_idx=wlindlo,
            upper_wl_idx=wlindhi,
            # mean_ref_dark=list(mean_ref_dark),
            # mean_ref_light=list(mean_ref_light),
            mean_ref_dark=[],
            mean_ref_light=[],
            agg_method=ap["agg_method"],
            agg_baseline=list(agg_baseline),
            agg_insitu=list(agg_insitu),
            agg_presitu=list(agg_presitu),
            bin_wavelength=list(bin_wl),
            bin_baseline=list(bin_baseline),
            bin_insitu=list(bin_insitu),
            bin_presitu=list(bin_presitu),
            smth_baseline=list(smth_baseline),
            smth_insitu=list(smth_insitu),
            smth_presitu=list(smth_presitu),
            rscl_baseline=list(rscl_baseline),
            rscl_insitu=list(rscl_insitu),
            rscl_presitu=list(rscl_presitu),
            baseline_min_rescaled=baseline_min_rscl,
            baseline_max_rescaled=baseline_max_rscl,
            insitu_min_rescaled=insitu_min_rscl,
            insitu_max_rescaled=insitu_max_rscl,
            presitu_min_rescaled=presitu_min_rscl,
            presitu_max_rescaled=presitu_max_rscl,
            mean_abs_omT_ratio=np.mean(
                np.abs(np.log10((1 - rscl_insitu) / (1 - rscl_baseline)))
            ),
            mean_abs_omT_diff=np.mean(np.abs((1 - rscl_insitu) - (1 - rscl_baseline))),
            noagg_wavelength=wls_insitu.tolist(),
            noagg_epoch=eps_insitu.tolist(),
            noagg_presitu_wavelength=wls_presitu.tolist(),
            noagg_presitu_epoch=eps_presitu.tolist(),
            noagg_omt_baseline=omt_refadj_baseline.tolist(),
            noagg_omt_insitu=omt_arr_insitu.tolist(),
            noagg_omt_presitu=omt_arr_presitu.tolist(),
            noagg_omt_ratio=arr_omt_ratio.tolist(),
        )
        return True
