"""uvis_bkgsubnorm / echeuvis_stability: output tag, aggregation window, fallback.

Frame k of every spectrum holds the value k (light references k + 100), epochs
0..9 s. With skip_first_n=4 and agg_last_secs=2 the window is the frames whose
epoch is within 2 s of the last one and past the first 4: frames 7, 8, 9, so
every aggregate is mean(7, 8, 9) = 8.0 (light: 108.0).
"""

import itertools
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from helao.core.drivers.data.loaders.localfs import LocalLoader
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
    with np.errstate(invalid="ignore"):  # constant spectra give log10(0/0)
        assert ana.calc_output() is True
    assert ana.outputs.agg_insitu[0] == 1.0


# ---------------------------------------------------------------------------
# LocalLoader contract: a sequence tree written in tmp_path, read
# through LocalLoader -> select_process_uuids -> constructor -> export.
# Layout follows helao/core/tests/test_loader_parity.py::_record.
# ---------------------------------------------------------------------------


ECHE_PARAMS = {**PARAMS, "skip_first_n": 1}


def _write_hlo(path: Path, payload: dict) -> None:
    """Legacy ``.hlo``: YAML header, ``%%``, one JSON data line (lists per key)."""
    wl = json.dumps(payload["meta"]["optional"]["wl"])
    body = json.dumps(payload["data"])
    path.write_text(f"optional:\n  wl: {wl}\n%%\n{body}\n", encoding="utf-8")


def _sequence(tmp_path: Path, seq_name: str, experiments: list) -> tuple:
    """Write one sequence and return ``(seq_dir, [process uuid, ...])``.

    ``experiments`` is ``[(experiment_name, [process, ...]), ...]`` in run
    order; a process is ``{"run_use", "label", "params", "actions"}`` with
    ``actions`` a list of ``(action_name, hlo payload or None)``. Every record
    gets a later timestamp than the one before it.
    """
    tick = itertools.count(1)
    seq_dir = tmp_path / "RUNS" / "2026" / "0925" / f"090000__{seq_name}__lab"
    seq_dir.mkdir(parents=True)
    (seq_dir / "20260925.090000000000-seq.yml").write_text(
        json.dumps({"sequence_name": seq_name}), encoding="utf-8"
    )
    puuids = []
    for exp_name, processes in experiments:
        ets = f"20260925.09{next(tick):04d}000000"
        exp_dir = seq_dir / f"{ets}__{exp_name}"
        exp_dir.mkdir()
        (exp_dir / f"{ets}-exp.yml").write_text(
            json.dumps({"experiment_name": exp_name}), encoding="utf-8"
        )
        for pidx, proc in enumerate(processes):
            puuid = str(uuid.uuid4())
            abbr, files = [], []
            for action_name, payload in proc["actions"]:
                n = next(tick)
                act_dir = exp_dir / f"{n}__0__SRV__{action_name}"
                act_dir.mkdir()
                auuid = str(uuid.uuid4())
                act_files = []
                if payload is not None:
                    fd = {
                        "file_name": "spec.hlo",
                        "file_type": "spec_helao__file",
                        "data_keys": sorted(payload["data"]),
                    }
                    _write_hlo(act_dir / "spec.hlo", payload)
                    act_files.append(fd)
                    files.append(dict(fd, action_uuid=auuid, run_use=proc["run_use"]))
                (act_dir / f"20260925.09{n:04d}000000-act.yml").write_text(
                    json.dumps(
                        {
                            "action_name": action_name,
                            "action_uuid": auuid,
                            "action_timestamp": f"2026-09-25T09:{n // 60:02d}:{n % 60:02d}",
                            "files": act_files,
                        }
                    ),
                    encoding="utf-8",
                )
                abbr.append(
                    {
                        "action_uuid": auuid,
                        "action_output_dir": act_dir.relative_to(
                            tmp_path / "RUNS"
                        ).as_posix(),
                    }
                )
            prc = {
                "technique_name": "tech",
                "process_uuid": puuid,
                "run_use": proc["run_use"],
                "run_type": "test",
                "process_params": proc.get("params", {}),
                "samples_in": [proc.get("sample", {"global_label": proc["label"]})],
                "dispatched_actions_abbr": abbr,
                "files": files,
            }
            (exp_dir / f"{pidx}__{puuid}__tech-prc.yml").write_text(
                json.dumps(prc), encoding="utf-8"
            )
            puuids.append(puuid)
    return seq_dir, puuids


def _dry_tree(tmp_path):
    spec = "acquire_spec_adv"
    ref = lambda ru, off: {
        "run_use": ru,
        "label": "ref",
        "actions": [(spec, _ramp(off))],
    }
    smp = lambda lab: {"run_use": "data", "label": lab, "actions": [(spec, _ramp())]}
    return _sequence(
        tmp_path,
        "UVIS_T",
        [
            ("UVIS_sub_measure", [ref("ref_dark", 0.0)]),
            ("UVIS_sub_measure", [ref("ref_light", 100.0)]),
            ("UVIS_sub_measure", [smp("plate__1")]),
            ("UVIS_sub_measure", [smp("plate__2")]),
        ],
    )


def _eche_tree(tmp_path):
    spec = "acquire_spec_extrig"
    lab = "plate__1"
    return _sequence(
        tmp_path,
        "ECHEUVIS_multiCA_led",
        [
            (
                "ECHEUVIS_sub_OCV_led",
                [
                    {
                        "run_use": "data",
                        "label": lab,
                        "actions": [(spec, _ramp()), ("run_OCV", None)],
                    }
                ],
            ),
            (
                "ECHEUVIS_sub_CA_led",
                [
                    {
                        "run_use": "data",
                        "label": lab,
                        "params": {"CA_potential_vsRHE": 1.23},
                        "actions": [(spec, _ramp()), ("run_CA", None)],
                    }
                ],
            ),
        ],
    )


def test_dry_selects_only_the_sequence_data_processes(tmp_path):
    seq_dir, puuids = _dry_tree(tmp_path)
    got = dry.DryUvisAnalysis.select_process_uuids(LocalLoader(str(seq_dir)))
    assert sorted(str(u) for u in got) == sorted(puuids[2:])


def test_eche_selects_only_the_ca_process(tmp_path):
    seq_dir, puuids = _eche_tree(tmp_path)
    got = eche.EcheUvisAnalysis.select_process_uuids(LocalLoader(str(seq_dir)))
    assert [str(u) for u in got] == [puuids[1]]


def test_dry_runs_and_exports_through_local_loader(tmp_path):
    seq_dir, _ = _dry_tree(tmp_path)
    loader = LocalLoader(str(seq_dir))
    puuid = dry.DryUvisAnalysis.select_process_uuids(loader)[0]
    ana = dry.DryUvisAnalysis(puuid, loader, PARAMS)
    assert ana.calc_output() is True
    model, _ = ana.export_analysis("b", "r")
    assert {o["output_type"] for o in model["outputs"]} == {
        "spectrum.uvis_bkgsubnorm_ref"
    }
    assert model["global_sample_label"] == "plate__1"


def test_eche_runs_and_exports_through_local_loader(tmp_path):
    seq_dir, _ = _eche_tree(tmp_path)
    loader = LocalLoader(str(seq_dir))
    puuid = eche.EcheUvisAnalysis.select_process_uuids(loader)[0]
    ana = eche.EcheUvisAnalysis(puuid, loader, ECHE_PARAMS)
    assert ana.calc_output() is True
    model, _ = ana.export_analysis("b", "r")
    assert {o["output_type"] for o in model["outputs"]} == {
        "spectrum.echeuvis_stability"
    }
    assert ana.ca_potential_vrhe == 1.23


def test_loader_frame_built_once_for_n_analyses(tmp_path, monkeypatch):
    seq_dir, _ = _dry_tree(tmp_path)
    calls = []
    real = dry.local_frame

    def counting(loader):
        calls.append(1)
        return real(loader)

    monkeypatch.setattr(dry, "local_frame", counting)
    loader = LocalLoader(str(seq_dir))
    puuids = dry.DryUvisAnalysis.select_process_uuids(loader)
    assert len(puuids) == 2
    for puuid in puuids:
        dry.DryUvisAnalysis(puuid, loader, PARAMS)
    assert len(calls) == 1


def test_eche_label_is_the_solid_part_of_an_assembly(tmp_path):
    spec = "acquire_spec_extrig"
    cell = {
        "global_label": "cell1_we__abc",
        "sample_type": "assembly",
        "parts": [
            {"global_label": "liq__1", "sample_type": "liquid"},
            {"global_label": "plate__1", "sample_type": "solid"},
        ],
    }
    proc = lambda params, last: {
        "run_use": "data",
        "label": "x",
        "sample": cell,
        "params": params,
        "actions": [(spec, _ramp()), (last, None)],
    }
    seq_dir, _ = _sequence(
        tmp_path,
        "ECHEUVIS_multiCA_led",
        [
            ("ECHEUVIS_sub_OCV_led", [proc({}, "run_OCV")]),
            ("ECHEUVIS_sub_CA_led", [proc({"CA_potential_vsRHE": 1.0}, "run_CA")]),
        ],
    )
    loader = LocalLoader(str(seq_dir))
    puuid = eche.EcheUvisAnalysis.select_process_uuids(loader)[0]
    ana = eche.EcheUvisAnalysis(puuid, loader, ECHE_PARAMS)
    assert ana.calc_output() is True
    model, _ = ana.export_analysis("b", "r")
    assert model["global_sample_label"] == "plate__1"


def _first_act(prc):
    return prc.json["dispatched_actions_abbr"][0]["action_uuid"]


def test_eche_two_samples_two_potentials_pick_own_baseline_and_presitu(tmp_path):
    spec = "acquire_spec_extrig"

    def ocv(lab):
        return (
            "ECHEUVIS_sub_OCV_led",
            [
                {
                    "run_use": "data",
                    "label": lab,
                    "actions": [(spec, _ramp()), ("run_OCV", None)],
                }
            ],
        )

    def ca(lab, v):
        return (
            "ECHEUVIS_sub_CA_led",
            [
                {
                    "run_use": "data",
                    "label": lab,
                    "params": {"CA_potential_vsRHE": v},
                    "actions": [(spec, _ramp()), ("run_CA", None)],
                }
            ],
        )

    seq_dir, pu = _sequence(
        tmp_path,
        "ECHEUVIS_multiCA_led",
        [ocv("A"), ca("A", 1.0), ocv("A"), ca("A", 2.0), ocv("B"), ca("B", 1.0)],
    )
    loader = LocalLoader(str(seq_dir))
    got = eche.EcheUvisAnalysis.select_process_uuids(loader)
    assert [str(u) for u in got] == [pu[1], pu[3], pu[5]]
    ins = {
        k: eche.EcheUvisAnalysis(u, loader, ECHE_PARAMS).inputs
        for k, u in zip("a1 a2 b1".split(), got)
    }
    # baseline: the sample's own first OCV
    assert [str(ins[k].baseline.process_uuid) for k in ("a1", "a2", "b1")] == [
        pu[0],
        pu[0],
        pu[4],
    ]
    # presitu: the OCV just before the CA (the OCV after CA 1 for CA 2)
    assert [str(ins[k].presitu.process_uuid) for k in ("a1", "a2", "b1")] == [
        pu[0],
        pu[2],
        pu[4],
    ]
    assert str(ins["a2"].presitu_spec_act.action_uuid) == _first_act(ins["a2"].presitu)
