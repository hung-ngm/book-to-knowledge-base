"""The Converter spec (SKILL.md + references/) must agree with the code it drives."""

from __future__ import annotations

import importlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
SPEC_FILES = [SKILL, *sorted((ROOT / "references").glob("*.md"))]


def frontmatter(text: str) -> dict[str, str]:
    block = text.split("---\n", 2)[1]
    return dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)


def test_skill_md_meets_the_agent_skills_limits():
    text = SKILL.read_text(encoding="utf-8")
    meta = frontmatter(text)
    name = meta["name"]
    description = meta["description"].strip('"')

    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) and len(name) <= 64
    assert 1 <= len(description) <= 1024
    assert len(text.splitlines()) < 500


def test_official_agent_skills_validator_accepts_the_skill():
    validator = shutil.which("agentskills") or str(Path(sys.executable).parent / "agentskills")
    if not Path(validator).exists():
        pytest.skip("skills-ref is not installed (uv pip install skills-ref)")
    if ROOT.name != "book-to-knowledge-base":
        pytest.skip("the validator requires the folder to be named after the skill")
    result = subprocess.run([validator, "validate", str(ROOT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("spec", SPEC_FILES, ids=lambda p: p.name)
def test_every_referenced_skill_file_exists(spec):
    text = spec.read_text(encoding="utf-8")
    paths = set(re.findall(r"`((?:references|scripts|tools)/[\w./-]+\.(?:md|py))`", text))
    paths |= {f"references/{m}" for m in re.findall(r"`([\w-]+\.md)`", text) if (ROOT / "references" / m).exists() or m.endswith("-book.md")}
    paths |= {p.replace("$SKILL_ROOT/", "") for p in re.findall(r"\$SKILL_ROOT/([\w./-]+\.py)", text)}
    missing = sorted(p for p in paths if not (ROOT / p).exists())
    assert missing == [], f"{spec.name} names files that do not exist: {missing}"


@pytest.mark.parametrize("spec", SPEC_FILES, ids=lambda p: p.name)
def test_every_cited_remote_helper_exists(spec):
    text = spec.read_text(encoding="utf-8")
    cited = set(re.findall(r"\b(discovery|policy|reader|checkpoint|coverage|provenance)\.([a-z_]+)\(", text))
    for module, func in sorted(cited):
        mod = importlib.import_module(f"book_to_kb.remote.{module}")
        assert callable(getattr(mod, func, None)), f"{spec.name} cites {module}.{func}, which does not exist"


def test_every_kb_command_in_the_spec_exists():
    text = "\n".join(p.read_text(encoding="utf-8") for p in SPEC_FILES)
    cited = set(re.findall(r"\$KB ([a-z-]+)", text))
    help_text = subprocess.run(
        [sys.executable, str(ROOT / "scripts/kb.py"), "--help"], capture_output=True, text=True, check=True
    ).stdout
    missing = sorted(c for c in cited if c not in help_text)
    assert missing == [], f"spec cites kb.py commands that do not exist: {missing}"


def test_remote_policy_env_var_named_in_the_spec_is_the_one_the_code_reads():
    text = (ROOT / "references/search-and-read.md").read_text(encoding="utf-8")
    code = (ROOT / "book_to_kb/remote/policy.py").read_text(encoding="utf-8")
    for var in re.findall(r"\b(BOOK_KB_[A-Z_]+)\b", text):
        assert var in code, f"search-and-read.md names {var}, which policy.py never reads"
