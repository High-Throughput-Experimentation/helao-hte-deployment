"""Parent-repo static sweeps, applied to this repo's own files.

The parent no longer tracks this deployment, so its git-based sweeps skip it.
Each test reuses the parent helper and only supplies the file list.
"""

import ast
import subprocess
from pathlib import Path

from helao.core.tests.test_artifact_hash_gate import scan_source
from helao.helpers.lib_exports import check_library_exports, iter_library_files
from helao.hexagon.tests.test_no_legacy_app_attribute import _app_attribute_sites

ROOT = Path(__file__).resolve().parents[1]
# hash-gate hits allowed here: (path relative to ROOT, scope) -> why
ALLOW: dict[tuple[str, str], str] = {}


def _py_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "*.py"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0 and proc.stdout:
        names = [n for n in proc.stdout.split("\0") if n]
    else:  # not a git checkout
        names = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py")]
    return sorted(ROOT / n for n in names)


def _gate_files() -> list[Path]:
    return [
        p
        for p in _py_files()
        if not p.name.startswith(("test_", "unit_test_"))
        and not p.name.endswith("_fixtures.py")
        and "/smoke/" not in p.relative_to(ROOT).as_posix()
    ]


def _hits() -> dict:
    return {
        (p.relative_to(ROOT).as_posix(), name): ln
        for p in _gate_files()
        for name, ln in scan_source(p.read_text(encoding="utf-8"))
    }


def test_library_exports():
    assert len(list(iter_library_files(ROOT))) > 0, "no library files found"
    problems = check_library_exports(ROOT)
    assert not problems, "\n".join(problems)


def test_record_writes_rehash_or_are_allowlisted():
    assert len(_gate_files()) > 100, "hash-gate sweep found too few files"
    bad = [f"{p}:{ln} {n}" for (p, n), ln in _hits().items() if (p, n) not in ALLOW]
    assert not bad, "record write without log_artifact_hashes:\n" + "\n".join(bad)


def test_allowlist_has_no_stale_entries():
    stale = sorted(set(ALLOW) - set(_hits()))
    assert not stale, f"ALLOW entries no longer matched by a real hit: {stale}"


def test_no_module_reaches_a_host_through_app():
    files = _py_files()
    assert len(files) > 100, f"sweep found only {len(files)} files"
    findings = []
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        findings += [f"{p.relative_to(ROOT)}:{ln}" for ln in _app_attribute_sites(tree)]
    assert not findings, "`.app` read off a host object:\n  " + "\n  ".join(findings)
