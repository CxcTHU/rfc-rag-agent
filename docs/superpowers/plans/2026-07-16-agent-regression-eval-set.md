# Agent Regression Evaluation Set Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fixed, reusable Agent regression evaluation set that measures answer quality, tool-selection behavior, refusal behavior, citation/source sufficiency, and latency budgets across future phases.

**Architecture:** Add a versioned CSV case registry under `data/evaluation/`, backed by a small parser/validator module and integrated into the existing Phase 66 HTTP evaluator. The fixed set becomes the stable "common suite"; Phase 66 can continue using its own file, but the evaluator will understand the richer common schema and enforce expected tools, forbidden tools, refusal expectations, source/citation floors, and latency budgets.

**Tech Stack:** Python 3.13, CSV, stdlib dataclasses, pytest, existing `scripts/evaluate_phase66_runtime_convergence.py` HTTP evaluator.

## Global Constraints

- `AGENT.MD` is the project rule source; do not commit, tag, push, or create a PR before user verification.
- Preserve the existing dirty worktree; do not overwrite unrelated Phase 65/66 changes.
- The common suite must be deterministic as data: stable case IDs, stable questions, stable expected contracts.
- The common suite must not require external secrets for validation-only tests.
- The first version must reuse the existing 30 text + 4 image Phase 66 cases so user-facing continuity is preserved.
- Latency gates must use the actual request elapsed time after the HTTP request completes, not pre-request timing.
- The default Agent model for normal user-facing evaluation is `deepseek-v4-flash`; Pro is an explicit operator choice.

---

## File Structure

- Create `data/evaluation/agent_regression_cases.csv`
  - Canonical fixed common regression set.
  - Stores case metadata and expected runtime contract.

- Create `scripts/agent_regression_cases.py`
  - Owns CSV parsing and validation.
  - Produces typed `AgentRegressionCase` values.
  - Keeps schema validation independent from the Phase 66 evaluator.

- Create `tests/test_agent_regression_cases.py`
  - Unit tests for loader validation and real CSV coverage.

- Modify `scripts/evaluate_phase66_runtime_convergence.py`
  - Accept the richer common CSV schema without breaking existing Phase66 CSV files.
  - Add contract checks into observation rows.
  - Add summary-level `contract_violation_count`.

- Modify `tests/test_evaluate_phase66_runtime_convergence.py`
  - Add tests for expected tools, forbidden tools, refusal expectations, source/citation floors, and latency budgets.

- Modify `docs/phase_reviews/phase-66.md`
  - Document that the old Phase66 case file remains historical, while `agent_regression_cases.csv` is the new fixed common suite.

---

### Task 1: Create the canonical common regression CSV

**Files:**
- Create: `data/evaluation/agent_regression_cases.csv`

**Interfaces:**
- Consumes: Existing questions from `data/evaluation/phase66_runtime_convergence_cases.csv`.
- Produces: A stable CSV schema consumed by `scripts.agent_regression_cases.load_agent_regression_cases(path: Path) -> tuple[AgentRegressionCase, ...]`.

- [ ] **Step 1: Create the CSV with explicit runtime contracts**

Create `data/evaluation/agent_regression_cases.csv` with exactly this header:

```csv
case_id,suite,modality,question,image_path,intent_category,expected_tools,forbidden_tools,expected_refusal,expected_min_sources,expected_min_citations,latency_budget_ms,notes
```

Seed it with these rows:

```csv
case_id,suite,modality,question,image_path,intent_category,expected_tools,forbidden_tools,expected_refusal,expected_min_sources,expected_min_citations,latency_budget_ms,notes
agent_reg_text_001,agent_common_v1,text,请说明堆石混凝土 RFC 相比常规混凝土筑坝工法的主要优势。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,fast RFC overview with citations
agent_reg_text_002,agent_common_v1,text,请总结 RFC 施工中自密实混凝土填充堆石空隙时的质量控制点。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,construction quality control
agent_reg_text_003,agent_common_v1,text,请根据知识库说明 RFC 温控或绝热温升研究通常关注哪些工程风险。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,thermal risk retrieval
agent_reg_text_004,agent_common_v1,text,请追踪 GB/T 50080 与混凝土拌合物性能试验之间的关系。,,standard_text,hybrid_search_knowledge,,false,2,1,20000,standard relation
agent_reg_text_005,agent_common_v1,text,请比较 GB/T 50080 与 GB/T 50081 在混凝土性能试验对象上的区别。,,standard_text,hybrid_search_knowledge,,false,2,1,20000,standard comparison
agent_reg_text_006,agent_common_v1,text,请说明骨料或堆石材料性质如何影响 RFC 力学性能。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,material properties
agent_reg_text_007,agent_common_v1,text,请检索包含 cement silica fume water aggregate 的 concrete mix proportion 表格并概括用途。,,table_lookup,search_tables,search_figures,false,1,1,22000,table retrieval
agent_reg_text_008,agent_common_v1,text,请从资料表格中列出堆石混凝土配合比参数。,,table_lookup,search_tables,search_figures,false,1,1,22000,table parameter extraction
agent_reg_text_009,agent_common_v1,text,请说明表格检索证据和普通文本证据在回答配合比问题时的区别。,,table_explanation,search_tables|hybrid_search_knowledge,search_figures,false,2,1,26000,table plus text explanation
agent_reg_text_010,agent_common_v1,text,请展示堆石混凝土破坏形态的图片作为证据。,,pure_figure_lookup,search_figures,hybrid_search_knowledge,false,1,1,14000,pure figure lookup should stay slim
agent_reg_text_011,agent_common_v1,text,请检索与大坝裂缝或混凝土缺陷图示相关的图片证据。,,pure_figure_lookup,search_figures,hybrid_search_knowledge,false,1,1,14000,pure figure lookup should stay slim
agent_reg_text_012,agent_common_v1,text,请说明图像证据在 RFC 质量审查中的适用边界。,,figure_explanation,search_figures|hybrid_search_knowledge,,false,2,1,32000,explanatory visual question may use both tools
agent_reg_text_013,agent_common_v1,text,彩票号码明天应该买什么。,,off_topic_refusal,,hybrid_search_knowledge|search_tables|search_figures,true,0,0,6000,domain refusal
agent_reg_text_014,agent_common_v1,text,请预测某支股票下周涨跌并给出投资建议。,,off_topic_refusal,,hybrid_search_knowledge|search_tables|search_figures,true,0,0,6000,financial advice refusal
agent_reg_text_015,agent_common_v1,text,帮我写一段和水工混凝土无关的娱乐八卦。,,off_topic_refusal,,hybrid_search_knowledge|search_tables|search_figures,true,0,0,6000,off-topic refusal
agent_reg_text_016,agent_common_v1,text,请再次说明 RFC 的优势但不要使用图片。,,text_only_constraint,hybrid_search_knowledge,search_figures,false,3,2,18000,text only no figure
agent_reg_text_017,agent_common_v1,text,不要表格只用文字说明 RFC 施工质量控制要点。,,text_only_constraint,hybrid_search_knowledge,search_tables,false,3,2,18000,text only no table
agent_reg_text_018,agent_common_v1,text,请用资料说明堆石混凝土和自密实混凝土之间的关系。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,concept relation
agent_reg_text_019,agent_common_v1,text,请说明 RFC 研究中试件强度测试通常怎样引用标准。,,standard_text,hybrid_search_knowledge,,false,2,1,20000,strength testing standard
agent_reg_text_020,agent_common_v1,text,请给出堆石混凝土施工过程的主要风险和监测要点。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,construction monitoring
agent_reg_text_021,agent_common_v1,text,请用一句话总结 RFC 的工程价值并给出引用。,,citation_contract,hybrid_search_knowledge,,false,2,1,16000,short answer still cited
agent_reg_text_022,agent_common_v1,text,请解释为什么 RFC 问答需要可追溯引用。,,citation_contract,hybrid_search_knowledge,,false,2,1,18000,citation rationale
agent_reg_text_023,agent_common_v1,text,请说明图表证据不足时系统应该如何处理。,,safe_insufficiency,hybrid_search_knowledge,,false,1,1,18000,insufficient evidence policy
agent_reg_text_024,agent_common_v1,text,请说明检索不到可靠证据时是否应该拒答。,,safe_insufficiency,hybrid_search_knowledge,,false,1,1,18000,reliable evidence refusal policy
agent_reg_text_025,agent_common_v1,text,请概括 RFC 与传统大体积混凝土温控问题的联系。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,thermal control relation
agent_reg_text_026,agent_common_v1,text,请说明自密实混凝土流动性对 RFC 填充效果的影响。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,flowability effect
agent_reg_text_027,agent_common_v1,text,请列出 RFC 质量评价中常见的材料参数。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,quality material parameters
agent_reg_text_028,agent_common_v1,text,请说明图像描述证据和原始图片证据的区别。,,figure_explanation,search_figures|hybrid_search_knowledge,,false,2,1,32000,image evidence distinction
agent_reg_text_029,agent_common_v1,text,请用中文回答 RFC 施工质量控制的三个要点。,,knowledge_text,hybrid_search_knowledge,,false,3,2,18000,Chinese concise answer
agent_reg_text_030,agent_common_v1,text,请用英文简要解释 rock-filled concrete 的 core idea。,,knowledge_text,hybrid_search_knowledge,,false,2,1,18000,English answer
agent_reg_image_001,agent_common_v1,image,请描述这张用户上传图片是否与 RFC 或混凝土工程相关。,data/user_uploads/2026-06-20/512f4df6505c435f835a7ddbeee4670a.png,user_image_only,analyze_user_image,,false,0,0,30000,user image description
agent_reg_image_002,agent_common_v1,image,请结合知识库判断这张图是否能支撑 RFC 施工或质量问题。,data/user_uploads/2026-06-20/c0a8591d94984d9faf2ba35233a7849c.png,user_image_plus_hybrid,analyze_user_image|hybrid_search_knowledge,,false,1,1,45000,user image plus KB
agent_reg_image_003,agent_common_v1,image,请寻找与这张图相似或相关的资料图片证据。,data/user_uploads/2026-06-20/363216cafd334ea5bc48069ad46c87be.png,user_image_plus_figure,analyze_user_image|search_figures,,false,1,1,45000,user image plus figure search
agent_reg_image_004,agent_common_v1,image,如果这张图无法可靠判断工程相关性请安全拒答。,data/user_uploads/2026-07-08/f0339352cc51403083fa95b9e09e4be8.png,user_image_safe_failure,analyze_user_image,,true,0,0,30000,user image safe refusal
```

- [ ] **Step 2: Confirm the file has 34 cases**

Run:

```powershell
python -c "import csv; rows=list(csv.DictReader(open('data/evaluation/agent_regression_cases.csv', encoding='utf-8-sig'))); print(len(rows)); print(rows[0]['case_id'], rows[-1]['case_id'])"
```

Expected:

```text
34
agent_reg_text_001 agent_reg_image_004
```

- [ ] **Step 3: Verification checkpoint**

Do not commit. Report the new CSV path and row count for user review.

---

### Task 2: Add a typed loader and schema validator

**Files:**
- Create: `scripts/agent_regression_cases.py`

**Interfaces:**
- Consumes: `data/evaluation/agent_regression_cases.csv`.
- Produces:
  - `AgentRegressionCase`
  - `parse_pipe_list(value: str) -> tuple[str, ...]`
  - `load_agent_regression_cases(path: Path) -> tuple[AgentRegressionCase, ...]`

- [ ] **Step 1: Write the failing tests first**

Create `tests/test_agent_regression_cases.py` with:

```python
from pathlib import Path

import pytest

from scripts.agent_regression_cases import load_agent_regression_cases, parse_pipe_list


ROOT = Path(__file__).resolve().parents[1]


def test_parse_pipe_list_trims_and_drops_empty_values() -> None:
    assert parse_pipe_list(" search_figures | hybrid_search_knowledge | ") == (
        "search_figures",
        "hybrid_search_knowledge",
    )


def test_common_agent_regression_suite_is_fixed_and_covered() -> None:
    cases = load_agent_regression_cases(ROOT / "data" / "evaluation" / "agent_regression_cases.csv")

    assert len(cases) == 34
    assert sum(1 for case in cases if case.modality == "text") == 30
    assert sum(1 for case in cases if case.modality == "image") == 4
    assert {case.suite for case in cases} == {"agent_common_v1"}
    assert len({case.case_id for case in cases}) == len(cases)


def test_common_agent_regression_suite_contains_tool_and_refusal_contracts() -> None:
    cases = {
        case.case_id: case
        for case in load_agent_regression_cases(ROOT / "data" / "evaluation" / "agent_regression_cases.csv")
    }

    assert cases["agent_reg_text_010"].expected_tools == ("search_figures",)
    assert cases["agent_reg_text_010"].forbidden_tools == ("hybrid_search_knowledge",)
    assert cases["agent_reg_text_013"].expected_refusal is True
    assert cases["agent_reg_text_016"].forbidden_tools == ("search_figures",)
    assert cases["agent_reg_image_002"].expected_tools == (
        "analyze_user_image",
        "hybrid_search_knowledge",
    )


def test_loader_rejects_image_case_without_image_path(tmp_path: Path) -> None:
    path = tmp_path / "cases.csv"
    path.write_text(
        "case_id,suite,modality,question,image_path,intent_category,expected_tools,"
        "forbidden_tools,expected_refusal,expected_min_sources,expected_min_citations,"
        "latency_budget_ms,notes\n"
        "bad,agent_common_v1,image,question,,user_image_only,analyze_user_image,,false,0,0,1,note\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="image_path"):
        load_agent_regression_cases(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_agent_regression_cases.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'scripts.agent_regression_cases'`.

- [ ] **Step 3: Implement the loader**

Create `scripts/agent_regression_cases.py`:

```python
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


VALID_MODALITIES = {"text", "image"}
VALID_REFUSAL_VALUES = {"true", "false"}
REQUIRED_COLUMNS = {
    "case_id",
    "suite",
    "modality",
    "question",
    "image_path",
    "intent_category",
    "expected_tools",
    "forbidden_tools",
    "expected_refusal",
    "expected_min_sources",
    "expected_min_citations",
    "latency_budget_ms",
    "notes",
}


@dataclass(frozen=True)
class AgentRegressionCase:
    case_id: str
    suite: str
    modality: Literal["text", "image"]
    question: str
    image_path: str
    intent_category: str
    expected_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    expected_refusal: bool | None
    expected_min_sources: int
    expected_min_citations: int
    latency_budget_ms: float | None
    notes: str


def parse_pipe_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value or "").split("|") if item.strip())


def parse_optional_bool(value: str) -> bool | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in VALID_REFUSAL_VALUES:
        raise ValueError(f"expected_refusal must be true or false, got {value!r}")
    return normalized == "true"


def parse_non_negative_int(value: str, *, column: str, case_id: str) -> int:
    try:
        parsed = int(str(value or "0").strip())
    except ValueError as exc:
        raise ValueError(f"{case_id} {column} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{case_id} {column} must be non-negative")
    return parsed


def parse_optional_positive_float(value: str, *, column: str, case_id: str) -> float | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        parsed = float(normalized)
    except ValueError as exc:
        raise ValueError(f"{case_id} {column} must be a number") from exc
    if parsed <= 0:
        raise ValueError(f"{case_id} {column} must be positive")
    return parsed


def load_agent_regression_cases(path: Path) -> tuple[AgentRegressionCase, ...]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or ())
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(f"agent regression case file missing columns: {', '.join(missing)}")
        rows = list(reader)

    cases: list[AgentRegressionCase] = []
    seen_ids: set[str] = set()
    for row_index, row in enumerate(rows, start=2):
        case_id = str(row.get("case_id", "")).strip()
        suite = str(row.get("suite", "")).strip()
        modality = str(row.get("modality", "")).strip().lower()
        question = str(row.get("question", "")).strip()
        image_path = str(row.get("image_path", "")).strip().replace("\\", "/")
        intent_category = str(row.get("intent_category", "")).strip()

        if not case_id:
            raise ValueError(f"row {row_index} requires case_id")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)
        if not suite:
            raise ValueError(f"{case_id} requires suite")
        if modality not in VALID_MODALITIES:
            raise ValueError(f"{case_id} modality must be text or image")
        if not question:
            raise ValueError(f"{case_id} requires question")
        if modality == "image" and not image_path:
            raise ValueError(f"{case_id} image case requires image_path")
        if not intent_category:
            raise ValueError(f"{case_id} requires intent_category")

        cases.append(
            AgentRegressionCase(
                case_id=case_id,
                suite=suite,
                modality=modality,  # type: ignore[arg-type]
                question=question,
                image_path=image_path,
                intent_category=intent_category,
                expected_tools=parse_pipe_list(str(row.get("expected_tools", ""))),
                forbidden_tools=parse_pipe_list(str(row.get("forbidden_tools", ""))),
                expected_refusal=parse_optional_bool(str(row.get("expected_refusal", ""))),
                expected_min_sources=parse_non_negative_int(
                    str(row.get("expected_min_sources", "0")),
                    column="expected_min_sources",
                    case_id=case_id,
                ),
                expected_min_citations=parse_non_negative_int(
                    str(row.get("expected_min_citations", "0")),
                    column="expected_min_citations",
                    case_id=case_id,
                ),
                latency_budget_ms=parse_optional_positive_float(
                    str(row.get("latency_budget_ms", "")),
                    column="latency_budget_ms",
                    case_id=case_id,
                ),
                notes=str(row.get("notes", "")).strip(),
            )
        )

    if not cases:
        raise ValueError("agent regression case file must not be empty")
    return tuple(cases)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_agent_regression_cases.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Verification checkpoint**

Do not commit. Report the loader path and test result.

---

### Task 3: Make the Phase 66 HTTP evaluator understand common-suite contracts

**Files:**
- Modify: `scripts/evaluate_phase66_runtime_convergence.py`
- Modify: `tests/test_evaluate_phase66_runtime_convergence.py`

**Interfaces:**
- Consumes:
  - Existing `Phase66HttpCase`
  - New `AgentRegressionCase`
- Produces:
  - Observation fields:
    - `intent_category`
    - `expected_tool_names`
    - `forbidden_tool_names`
    - `contract_violations`
    - `contract_violation_count`
  - Summary field:
    - `contract_violation_count`

- [ ] **Step 1: Write a failing unit test for tool contracts**

Append this test to `tests/test_evaluate_phase66_runtime_convergence.py`:

```python
from pathlib import Path

from scripts.evaluate_phase66_runtime_convergence import (
    collect_http_observations,
)


def test_collect_http_observations_enforces_expected_and_forbidden_tools(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.csv"
    cases_path.write_text(
        "case_id,suite,modality,question,image_path,intent_category,expected_tools,"
        "forbidden_tools,expected_refusal,expected_min_sources,expected_min_citations,"
        "latency_budget_ms,notes\n"
        "case_1,agent_common_v1,text,请展示图片证据。,,pure_figure_lookup,"
        "search_figures,hybrid_search_knowledge,false,1,1,999999,note\n",
        encoding="utf-8",
    )

    def fake_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str):
        return 200, {
            "answer": "ok",
            "tool_calls": [
                {"tool_name": "search_figures"},
                {"tool_name": "hybrid_search_knowledge"},
            ],
            "sources": [{"id": 1}],
            "citations": [1],
            "refused": False,
        }

    summary = collect_http_observations(
        variant="b",
        base_url="http://127.0.0.1:8000",
        cases_path=cases_path,
        output_root=tmp_path / "out",
        timeout_seconds=1.0,
        token="",
        post_json=fake_post_json,
    )

    assert summary["contract_violation_count"] == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_evaluate_phase66_runtime_convergence.py::test_collect_http_observations_enforces_expected_and_forbidden_tools -q
```

Expected: fail because `contract_violation_count` is not yet produced.

- [ ] **Step 3: Extend `Phase66HttpCase` with optional contract fields**

In `scripts/evaluate_phase66_runtime_convergence.py`, import the loader:

```python
from scripts.agent_regression_cases import load_agent_regression_cases, parse_pipe_list
```

Change the dataclass to:

```python
@dataclass(frozen=True)
class Phase66HttpCase:
    case_id: str
    modality: Literal["text", "image"]
    question: str
    image_path: str = ""
    intent_category: str = ""
    expected_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    expected_refusal: bool | None = None
    expected_min_sources: int = 0
    expected_min_citations: int = 0
    latency_budget_ms: float | None = None
```

- [ ] **Step 4: Make `load_http_cases()` support both schemas**

Replace the beginning of `load_http_cases()` with this branch:

```python
def load_http_cases(path: Path) -> tuple[Phase66HttpCase, ...]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
        fieldnames = set(rows[0].keys()) if rows else set()

    if "suite" in fieldnames and "intent_category" in fieldnames:
        return tuple(
            Phase66HttpCase(
                case_id=case.case_id,
                modality=case.modality,
                question=case.question,
                image_path=case.image_path,
                intent_category=case.intent_category,
                expected_tools=case.expected_tools,
                forbidden_tools=case.forbidden_tools,
                expected_refusal=case.expected_refusal,
                expected_min_sources=case.expected_min_sources,
                expected_min_citations=case.expected_min_citations,
                latency_budget_ms=case.latency_budget_ms,
            )
            for case in load_agent_regression_cases(path)
        )
```

Keep the existing simple Phase66 CSV parsing path after this branch so `data/evaluation/phase66_runtime_convergence_cases.csv` still works.

- [ ] **Step 5: Add contract checking helper**

Add:

```python
def contract_violations_for_observation(
    *,
    case: Phase66HttpCase,
    observed_tools: tuple[str, ...],
    source_count: int,
    citation_count: int,
    refused: bool,
    elapsed_ms: float,
) -> tuple[str, ...]:
    violations: list[str] = []
    observed_set = set(observed_tools)
    for expected_tool in case.expected_tools:
        if expected_tool not in observed_set:
            violations.append(f"missing_tool:{expected_tool}")
    for forbidden_tool in case.forbidden_tools:
        if forbidden_tool in observed_set:
            violations.append(f"forbidden_tool:{forbidden_tool}")
    if case.expected_refusal is not None and refused is not case.expected_refusal:
        violations.append(f"refusal_mismatch:expected_{str(case.expected_refusal).lower()}")
    if source_count < case.expected_min_sources:
        violations.append(f"source_floor:{source_count}<{case.expected_min_sources}")
    if citation_count < case.expected_min_citations:
        violations.append(f"citation_floor:{citation_count}<{case.expected_min_citations}")
    if case.latency_budget_ms is not None and elapsed_ms > case.latency_budget_ms:
        violations.append(f"latency_budget:{elapsed_ms:.3f}>{case.latency_budget_ms:.3f}")
    return tuple(violations)
```

- [ ] **Step 6: Add contract fields to response observations**

Inside `safe_observation_from_response()`, after computing `refused`, add:

```python
    contract_violations = contract_violations_for_observation(
        case=case,
        observed_tools=tool_names,
        source_count=source_count,
        citation_count=citation_count,
        refused=refused,
        elapsed_ms=elapsed_ms,
    )
```

Then add these keys to the returned dict:

```python
        "intent_category": case.intent_category,
        "expected_tool_names": "|".join(case.expected_tools),
        "forbidden_tool_names": "|".join(case.forbidden_tools),
        "contract_violations": "|".join(contract_violations),
        "contract_violation_count": len(contract_violations),
```

- [ ] **Step 7: Add contract fields to transport-error observations**

Inside `safe_observation_from_transport_error()`, set:

```python
        "intent_category": case.intent_category,
        "expected_tool_names": "|".join(case.expected_tools),
        "forbidden_tool_names": "|".join(case.forbidden_tools),
        "contract_violations": "connection_error",
        "contract_violation_count": 1,
```

- [ ] **Step 8: Roll contract violations into summaries**

Inside `collect_results()`, initialize:

```python
    contract_violation_count = 0
```

Inside the observation loop:

```python
        contract_violation_count += int(row.get("contract_violation_count", 0) or 0)
```

Add it to summary:

```python
        "contract_violation_count": contract_violation_count,
```

Update status logic:

```python
    if complete_coverage and unknown_error_count == 0 and failed_case_count == 0 and judge_failed_count == 0 and contract_violation_count == 0:
        status = "collected"
    else:
        status = "review_required"
```

- [ ] **Step 9: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_agent_regression_cases.py tests/test_evaluate_phase66_runtime_convergence.py::test_collect_http_observations_enforces_expected_and_forbidden_tools -q
```

Expected:

```text
5 passed
```

- [ ] **Step 10: Verification checkpoint**

Do not commit. Report new observation and summary fields for user review.

---

### Task 4: Add focused tests for refusal, citation/source floors, and latency budgets

**Files:**
- Modify: `tests/test_evaluate_phase66_runtime_convergence.py`

**Interfaces:**
- Consumes: `contract_violations_for_observation()`.
- Produces: Direct unit-level coverage for contract checks without HTTP.

- [ ] **Step 1: Add direct contract unit tests**

Append:

```python
from scripts.evaluate_phase66_runtime_convergence import (
    Phase66HttpCase,
    contract_violations_for_observation,
)


def test_contract_violations_detect_refusal_source_citation_and_latency_failures() -> None:
    case = Phase66HttpCase(
        case_id="case_1",
        modality="text",
        question="question",
        expected_tools=("hybrid_search_knowledge",),
        forbidden_tools=("search_figures",),
        expected_refusal=False,
        expected_min_sources=2,
        expected_min_citations=1,
        latency_budget_ms=1000.0,
    )

    violations = contract_violations_for_observation(
        case=case,
        observed_tools=("search_figures",),
        source_count=1,
        citation_count=0,
        refused=True,
        elapsed_ms=1500.0,
    )

    assert violations == (
        "missing_tool:hybrid_search_knowledge",
        "forbidden_tool:search_figures",
        "refusal_mismatch:expected_false",
        "source_floor:1<2",
        "citation_floor:0<1",
        "latency_budget:1500.000>1000.000",
    )
```

- [ ] **Step 2: Run the direct test**

Run:

```powershell
python -m pytest tests/test_evaluate_phase66_runtime_convergence.py::test_contract_violations_detect_refusal_source_citation_and_latency_failures -q
```

Expected:

```text
1 passed
```

- [ ] **Step 3: Run the full Phase66 evaluator unit suite**

Run:

```powershell
python -m pytest tests/test_evaluate_phase66_runtime_convergence.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Verification checkpoint**

Do not commit. Report direct contract test coverage.

---

### Task 5: Document how to run the fixed common suite

**Files:**
- Modify: `docs/phase_reviews/phase-66.md`
- Optional create if preferred: `docs/agent_regression_evaluation.md`

**Interfaces:**
- Consumes: `data/evaluation/agent_regression_cases.csv`.
- Produces: User/operator instructions for local A/B, smoke, and release gates.

- [ ] **Step 1: Add documentation section**

Add this section to `docs/phase_reviews/phase-66.md`:

```markdown
## Fixed common Agent regression suite

Phase 66 introduced a reusable common Agent regression suite at:

`data/evaluation/agent_regression_cases.csv`

This file supersedes ad hoc smoke prompts for release evidence. The suite is
versioned as `agent_common_v1` and contains 30 text cases plus 4 image cases.
Each case has an explicit runtime contract:

- expected tools
- forbidden tools
- expected refusal behavior
- minimum source count
- minimum citation count
- latency budget in milliseconds

The historical Phase 66 file remains available at
`data/evaluation/phase66_runtime_convergence_cases.csv`, but new A/B evidence
should prefer the common suite.

Collect candidate observations against a running local Agent:

```powershell
python scripts/evaluate_phase66_runtime_convergence.py `
  --collect-http `
  --variant b `
  --base-url http://127.0.0.1:8000 `
  --cases data/evaluation/agent_regression_cases.csv `
  --output-root output/phase66/evaluation_common/b
```

The resulting `observations.json` includes `contract_violations` per case, and
`summary.json` includes `contract_violation_count`.
```

- [ ] **Step 2: Run documentation-adjacent validation**

Run:

```powershell
python -m pytest tests/test_agent_regression_cases.py tests/test_evaluate_phase66_runtime_convergence.py -q
python -m py_compile scripts\agent_regression_cases.py scripts\evaluate_phase66_runtime_convergence.py
```

Expected:

```text
all selected tests pass
py_compile exits 0
```

- [ ] **Step 3: Verification checkpoint**

Do not commit. Report the docs path and exact run command.

---

## Final Acceptance Checks

Run:

```powershell
python -m pytest tests/test_agent_regression_cases.py tests/test_evaluate_phase66_runtime_convergence.py -q
python -m py_compile scripts\agent_regression_cases.py scripts\evaluate_phase66_runtime_convergence.py
git diff --check -- data/evaluation/agent_regression_cases.csv scripts/agent_regression_cases.py scripts/evaluate_phase66_runtime_convergence.py tests/test_agent_regression_cases.py tests/test_evaluate_phase66_runtime_convergence.py docs/phase_reviews/phase-66.md
```

Expected:

```text
pytest passes
py_compile exits 0
git diff --check reports no whitespace errors
```

Then run one local HTTP collection against the already-running Agent:

```powershell
python scripts/evaluate_phase66_runtime_convergence.py `
  --collect-http `
  --variant b `
  --base-url http://127.0.0.1:8000 `
  --cases data/evaluation/agent_regression_cases.csv `
  --output-root output/phase66/evaluation_common/b `
  --timeout-seconds 180
```

Expected:

```text
output/phase66/evaluation_common/b/observations.json exists
output/phase66/evaluation_common/b/summary.json exists
summary.json contains contract_violation_count
```

## Self-Review

Spec coverage:

- Fixed common test set: Task 1.
- Stable schema and validator: Task 2.
- Evaluator integration: Task 3.
- Runtime contracts for tool calling, refusal, citation/source sufficiency, and latency: Tasks 3 and 4.
- Operator documentation: Task 5.
- No premature commit: all tasks use verification checkpoints instead of commits.

Placeholder scan:

- No `TBD`, `TODO`, or "fill later" placeholders are present.
- Each code-changing task includes concrete code snippets and exact commands.

Type consistency:

- `AgentRegressionCase.expected_tools` and `Phase66HttpCase.expected_tools` both use `tuple[str, ...]`.
- `latency_budget_ms` is `float | None` in both loader and evaluator.
- `contract_violation_count` is produced per observation and aggregated in summary.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-16-agent-regression-eval-set.md`. Two execution options:

1. **Subagent-Driven (recommended by the skill, but not allowed here unless the user explicitly asks for subagents)** - dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** - execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

For this repository and current collaboration mode, use **Inline Execution** unless the user explicitly asks for subagents.
