"""uvis_bkgsubnorm / echeuvis_stability: output tag, aggregation window, fallback.

Frame k of every spectrum holds the value k (light references k + 100), epochs
0..9 s. With skip_first_n=4 and agg_last_secs=2 the window is the frames whose
epoch is within 2 s of the last one and past the first 4: frames 7, 8, 9, so
every aggregate is mean(7, 8, 9) = 8.0 (light: 108.0).
"""

from types import SimpleNamespace

import numpy as np

from helao.deploy.hte.servers.analysis.analyses import echeuvis_stability as eche
from helao.deploy.hte.servers.analysis.analyses import uvis_bkgsubnorm as dry

WL = np.linspace(400.0, 800.0, 60)
PARAMS = {
    "lower_wl": 420,
    "upper_wl": 780,
    "window_length": 5,
    "poly_order": 2,
    "skip_first_n": 4,
    "agg_last_secs": 2,
    "agg_method": "mean",
}


def _hlo(epochs, values):
    """Spectrometer payload: frame i has every channel equal to values[i]."""
    data = {"epoch_s": [float(e) for e in epochs]}
    data.update({f"ch_{i:03d}": [float(v) for v in values] for i in range(len(WL))})
    return {"meta": {"optional": {"wl": WL.tolist()}}, "data": data}


def _ramp(offset=0.0, n=10):
    return _hlo(np.arange(float(n)), np.arange(float(n)) + offset)


def test_dry_window_is_last_secs_after_skip():
    ana = object.__new__(dry.DryUvisAnalysis)
    ana.analysis_params = {**dry.ANALYSIS_DEFAULTS, **PARAMS}
    ana.inputs = SimpleNamespace(
        ref_dark_spec=[_ramp()],
        ref_light_spec=[_ramp(100.0)],
        insitu_spec=_ramp(),
    )
    assert ana.calc_output() is True
    assert ana.outputs.agg_insitu[0] == 8.0
    assert ana.outputs.mean_ref_dark[0] == 8.0
    assert ana.outputs.mean_ref_light[0] == 108.0
    assert ana.outputs.output_type == "spectrum.uvis_bkgsubnorm_ref"


def test_eche_window_is_last_secs_after_skip():
    ana = object.__new__(eche.EcheUvisAnalysis)
    ana.analysis_params = {**eche.ANALYSIS_DEFAULTS, **PARAMS}
    ana.inputs = SimpleNamespace(
        baseline_spec=_ramp(), insitu_spec=_ramp(), presitu_spec=_ramp()
    )
    assert ana.calc_output() is True
    out = ana.outputs
    assert (out.agg_baseline[0], out.agg_insitu[0], out.agg_presitu[0]) == (
        8.0,
        8.0,
        8.0,
    )
    assert out.output_type == "spectrum.echeuvis_stability"


def test_eche_short_insitu_falls_back_to_whole_epoch_vector():
    # 3 frames (epochs 0..2) are fewer than skip_first_n=4; the whole vector
    # spans 2 s <= agg_last_secs, so the fallback averages frames 0, 1, 2 -> 1.0
    ana = object.__new__(eche.EcheUvisAnalysis)
    ana.analysis_params = {**eche.ANALYSIS_DEFAULTS, **PARAMS}
    ana.inputs = SimpleNamespace(
        baseline_spec=_ramp(), insitu_spec=_ramp(n=3), presitu_spec=_ramp()
    )
    assert ana.calc_output() is True
    assert ana.outputs.agg_insitu[0] == 1.0
