"""Dry UV-Vis background-subtraction + normalisation analysis.

Reads a ``UVIS_T`` sequence through a ``LocalLoader`` (:func:`local_frame`),
averages start/end dark and light reference spectra, normalises the
sample spectrum, bins, smooths and reference-adjusts the result, and
emits :class:`DryUvisOutputs` via :class:`DryUvisAnalysis`.
"""

import sys
from copy import copy
from datetime import datetime
from uuid import UUID

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.stats import binned_statistic

from helao.core.drivers.data.analyses.base_analysis import BaseAnalysis
from helao.core.drivers.data.loaders.localfs import (
    HelaoAction,
    HelaoProcess,
    LocalLoader,
)
from helao.core.models.analysis import AnalysisDataModel, AnalysisInput, AnalysisOutput
from helao.core.version import get_filehash

from .echeuvis_stability import (
    last_secs_start,
    local_frame,
    parse_spechlo,
    refadjust,
)

ANALYSIS_DEFAULTS = {
    "ev_parts": [1.8, 2.2, 2.6, 3.0],
    "bin_width": 3,
    "window_length": 45,
    "poly_order": 4,
    "lower_wl": 370,
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


class DryUvisInputs(AnalysisInput):
    """Reference darks/lights and the sample acquisition for one dry UV-Vis run.

    Attributes:
        ref_darks: Processes whose ``run_use=='ref_dark'``.
        ref_dark_spec_acts: Corresponding spectrometer actions.
        ref_lights: Processes whose ``run_use=='ref_light'``.
        ref_light_spec_acts: Corresponding spectrometer actions.
        insitu_spec_act: Sample-acquisition spectrometer action.
        process_params: ``process_params`` from the in-situ process.
    """

    ref_darks: list[HelaoProcess]
    ref_dark_spec_acts: list[HelaoAction]
    ref_lights: list[HelaoProcess]
    ref_light_spec_acts: list[HelaoAction]
    insitu_spec_act: HelaoAction
    process_params: dict

    def __init__(self, insitu_process_uuid: UUID, frame: pd.DataFrame):
        """Resolve ref-dark/light and sample spectrometer actions from ``frame``.

        Args:
            insitu_process_uuid: Process UUID of the sample acquisition.
            frame: :func:`local_frame` of the sequence.
        """
        spec = frame[frame.action_name == "acquire_spec_adv"].sort_values(
            "action_timestamp", kind="stable"
        )
        darks = spec[spec.run_use == "ref_dark"]
        lights = spec[spec.run_use == "ref_light"]
        self.ref_darks = list(darks.prc)
        self.ref_dark_spec_acts = list(darks.act)
        self.ref_lights = list(lights.prc)
        self.ref_light_spec_acts = list(lights.act)
        row = spec[spec.process_uuid == insitu_process_uuid].iloc[0]
        self.insitu = row.prc
        self.insitu_spec_act = row.act
        self.global_label = row.global_label
        self.process_params = self.insitu.process_params

    @property
    def ref_dark_spec(self) -> list:
        """List of loaded HLO payloads for the dark-reference actions."""
        return [x.hlo for x in self.ref_dark_spec_acts]

    @property
    def ref_light_spec(self) -> list:
        """List of loaded HLO payloads for the light-reference actions."""
        return [x.hlo for x in self.ref_light_spec_acts]

    @property
    def insitu_spec(self):
        """Loaded HLO payload for the sample-acquisition action."""
        return self.insitu_spec_act.hlo

    def get_datamodels(
        self, global_sample_label: str, *args, **kwargs
    ) -> list[AnalysisDataModel]:
        """Emit :class:`AnalysisDataModel` entries for every spec action.

        Args:
            global_sample_label: Override label; falls back to
                the analysed process's first ``samples_in``
                ``global_label`` for data/baseline inputs.
        """
        action_keys = [k for k in vars(self).keys() if "spec_act" in k]
        inputs = []
        for ak in action_keys:
            euis = vars(self)[ak]
            ru = ak.split("_spec")[0].replace("insitu", "data")
            if not isinstance(euis, list):
                euis = [euis]
            for eui in euis:
                filename, filetype, datakeys = eui.hlo_file_tup
                raw_data_path = f"raw_data/{eui.action_uuid}/{filename}"
                if global_sample_label is not None:
                    global_sample = global_sample_label
                elif ru in ["data", "baseline"]:
                    global_sample = self.global_label
                else:
                    global_sample = None
                adm = AnalysisDataModel(
                    action_uuid=eui.action_uuid,
                    run_use=ru,
                    raw_data_path=raw_data_path,
                    global_sample_label=global_sample,
                    file_type=filetype,
                    file_name=filename,
                    data_keys=datakeys,
                )
                inputs.append(adm)
        return inputs


class DryUvisOutputs(AnalysisOutput):
    """Output payload for :class:`DryUvisAnalysis`.

    Attributes:
        wavelength: Full wavelength axis.
        lower_wl_idx: Index of the lower wavelength cutoff.
        upper_wl_idx: Index of the upper wavelength cutoff.
        mean_ref_dark: Mean dark-reference spectrum.
        mean_ref_light: Mean light-reference spectrum.
        agg_method: Aggregation method (``"mean"`` or ``"median"``).
        agg_insitu: Aggregated in-situ spectrum.
        bin_wavelength: Binned wavelength axis.
        bin_insitu: Binned in-situ spectrum.
        smth_insitu: Smoothed binned spectrum.
        rscl_insitu: Reference-rescaled spectrum.
        insitu_min_rescaled: Whether the spectrum minimum was rescaled.
        insitu_max_rescaled: Whether the spectrum maximum was rescaled.
    """

    wavelength: list
    lower_wl_idx: int
    upper_wl_idx: int
    mean_ref_dark: list  # mean over start and end reference dark insitutra
    mean_ref_light: list  # mean over start and end reference light insitutra
    agg_method: str
    agg_insitu: list  # mean over final t seconds of OCV
    bin_wavelength: list
    bin_insitu: list
    smth_insitu: list
    rscl_insitu: list
    insitu_min_rescaled: bool
    insitu_max_rescaled: bool


class DryUvisAnalysis(BaseAnalysis):
    """Dry UV-Vis background-subtraction + normalisation analysis.

    Attributes:
        analysis_name: Fixed analysis name string.
        analysis_timestamp: Time the analysis instance was built.
        analysis_uuid: Generated analysis UUID.
        analysis_params: Effective parameters (defaults merged with
            caller overrides).
        process_uuid: UUID of the sample-acquisition process.
        process_timestamp: Timestamp of that process.
        process_name: Technique name from the row.
        run_type: Run type string.
        technique_name: Technique-name string.
        inputs: Resolved :class:`DryUvisInputs`.
        outputs: Populated :class:`DryUvisOutputs` after
            :meth:`calc_output`.
        action_attr: Attribute name used to find spec actions
            (``"spec_act"``).
        analysis_codehash: Hash of the analysis source file.
    """

    analysis_name: str
    analysis_timestamp: datetime
    analysis_uuid: UUID
    analysis_params: dict
    process_uuid: UUID
    process_timestamp: datetime
    process_name: str
    run_type: str
    technique_name: str
    inputs: DryUvisInputs
    outputs: DryUvisOutputs
    action_attr: str
    analysis_codehash: str

    @classmethod
    def select_process_uuids(cls, local_loader) -> list:
        """The sequence's ``run_use == data`` acquisitions (references excluded)."""
        f = local_loader._local_frame = local_frame(local_loader)
        sel = f[(f.run_use == "data") & (f.action_name == "acquire_spec_adv")]
        return list(dict.fromkeys(sel.process_uuid))

    def __init__(
        self,
        process_uuid: UUID,
        local_loader: LocalLoader,
        analysis_params: dict,
    ):
        """Build inputs from the loader's sequence and stamp analysis metadata.

        Args:
            process_uuid: Target sample-acquisition process UUID.
            local_loader: ``LocalLoader`` bound to the sequence.
            analysis_params: Overrides merged into
                :data:`ANALYSIS_DEFAULTS`.
        """
        self.analysis_name = "UVIS_BkgSubNorm"
        self.action_attr = "spec_act"
        self.analysis_timestamp = datetime.now()
        self.analysis_params = copy(ANALYSIS_DEFAULTS)
        self.analysis_params.update(analysis_params)
        # select_process_uuids stores the frame on the loader (one build per sequence)
        frame = getattr(local_loader, "_local_frame", None)
        if frame is None:
            frame = local_frame(local_loader)
        self.inputs = DryUvisInputs(process_uuid, frame)
        prc = self.inputs.insitu
        self.process_uuid = process_uuid
        self.process_timestamp = prc.process_timestamp
        self.process_name = prc.technique_name
        self.run_type = prc.json.get("run_type")
        self.run_use = "data"
        self.technique_name = prc.technique_name
        self.campaign_name = prc.json.get("campaign_name")
        self.campaign_uuid = prc.json.get("campaign_uuid")
        self.analysis_codehash = get_filehash(sys._getframe().f_code.co_filename)
        self.analysis_codepath = sys._getframe().f_code.co_filename
        self.analysis_classname = self.__class__.__name__
        self.analysis_uuid = self.gen_uuid()

    def calc_output(self) -> bool:
        """Run the background-subtraction/normalisation pipeline.

        Aggregates the last ``agg_last_secs`` seconds of dark/light
        references and the sample spectrum, subtracts and normalises,
        bins, smooths and rescales, and finally writes
        :attr:`outputs`. Returns ``False`` if any spectrometer parse
        fails.
        """
        rdtups = [parse_spechlo(x) for x in self.inputs.ref_dark_spec]
        rltups = [parse_spechlo(x) for x in self.inputs.ref_light_spec]
        btup = parse_spechlo(self.inputs.insitu_spec)

        if any([x is False for x in rdtups + rltups + [btup]]):
            return False

        ap = self.analysis_params
        aggfunc = np.mean if ap["agg_method"] == "mean" else np.median
        wl = btup[0]
        wlindlo = np.where(wl > ap["lower_wl"])[0].min()
        wlindhi = np.where(wl < ap["upper_wl"])[0].max()

        skip, secs = ap["skip_first_n"], ap["agg_last_secs"]
        # mean aggregate initial and final reference dark spectra
        mean_ref_dark = np.vstack(
            [arr[last_secs_start(ep, skip, secs) :] for wl, ep, arr in rdtups]
        ).mean(axis=0)

        # mean aggregate initial and final reference light spectra
        mean_ref_light = np.vstack(
            [arr[last_secs_start(ep, skip, secs) :] for wl, ep, arr in rltups]
        ).mean(axis=0)

        # aggregate the sample spectra over final t seconds, omitting first n
        agg_insitu = aggfunc(btup[2][last_secs_start(btup[1], skip, secs) :], axis=0)

        inds = range(len(wl[wlindlo:wlindhi]))
        nbins = np.round(len(wl[wlindlo:wlindhi]) / ap["bin_width"]).astype(int)
        refadj_insitu = (
            (agg_insitu - mean_ref_dark) / (mean_ref_light - mean_ref_dark)
        )[wlindlo:wlindhi]
        bin_wl = binned_statistic(inds, wl[wlindlo:wlindhi], "mean", nbins).statistic
        bin_insitu = binned_statistic(inds, refadj_insitu, "mean", nbins).statistic
        smth_insitu = savgol_filter(
            bin_insitu, ap["window_length"], ap["poly_order"], delta=ap["delta"]
        )
        insitu_min_rscl, insitu_max_rscl, rscl_insitu = refadjust(
            smth_insitu,
            ap["min_mthd_allowed"],
            ap["max_mthd_allowed"],
            ap["min_limit"],
            ap["max_limit"],
        )

        # create output model
        self.outputs = DryUvisOutputs(
            output_type="spectrum.uvis_bkgsubnorm_ref",
            wavelength=list(wl),
            lower_wl_idx=wlindlo,
            upper_wl_idx=wlindhi,
            mean_ref_dark=list(mean_ref_dark),
            mean_ref_light=list(mean_ref_light),
            agg_method=ap["agg_method"],
            agg_insitu=list(agg_insitu),
            bin_wavelength=list(bin_wl),
            bin_insitu=list(bin_insitu),
            smth_insitu=list(smth_insitu),
            rscl_insitu=list(rscl_insitu),
            insitu_min_rescaled=insitu_min_rscl,
            insitu_max_rescaled=insitu_max_rscl,
        )
        return True
