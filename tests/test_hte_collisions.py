from pathlib import Path

from harness.hte_collisions import scan_collisions

HTE = Path(__file__).resolve().parents[1]
EXP = HTE / "experiments"
SEQ = HTE / "sequences"


def test_hte_seq_libraries_have_no_collisions():
    # the one known collision, ECHEUVIS_postseq in ECHEUVIS_seq.py and
    # HISPEC_seq.py, was deleted with the in-sequence analysis path
    assert scan_collisions(SEQ) == {}


def test_seq_collision_detected_in_real_dir_copy(tmp_path):
    # non-vacuity: a copy of the real library plus one duplicate def must be caught
    import shutil

    shutil.copytree(SEQ, tmp_path / "s")
    (tmp_path / "s" / "zz_seq.py").write_text(
        "def UVIS_T():\n    return []\n", encoding="utf-8"
    )
    assert scan_collisions(tmp_path / "s") == {"UVIS_T": ["UVIS_T_seq.py", "zz_seq.py"]}


def test_exp_collision_detected_in_synthetic_pair(tmp_path):
    for mod in ("twin_a_exp", "twin_b_exp"):
        (tmp_path / f"{mod}.py").write_text(
            "def shared_sub_exp():\n    return []\n", encoding="utf-8"
        )
    assert scan_collisions(tmp_path) == {
        "shared_sub_exp": ["twin_a_exp.py", "twin_b_exp.py"]
    }


def test_hte_exp_libraries_have_no_collisions():
    assert scan_collisions(EXP) == {}


def test_exp_collision_detected_in_real_dir_copy(tmp_path):
    # non-vacuity: a copy of the real library plus one duplicate def must be caught
    import shutil

    shutil.copytree(EXP, tmp_path / "e")
    (tmp_path / "e" / "zz_exp.py").write_text(
        "def CCSI_sub_drain():\n    return []\n", encoding="utf-8"
    )
    assert "CCSI_sub_drain" in scan_collisions(tmp_path / "e")
