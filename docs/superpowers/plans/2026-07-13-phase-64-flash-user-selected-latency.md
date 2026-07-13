# Phase 64 Flash 用户显式选择延迟 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使冻结的 Phase 64 A/B 评测以显式请求模型安全对照 Pro 与 Flash，并把模型实际选择纳入功能门禁。

**Architecture:** 复用既有 API `chat_model` 白名单和 SSE metadata，不改前端或默认配置。E2E 基础执行器负责将可选模型放入 JSON 请求、提取安全的 metadata 模型标识；Phase 64 评测器为每个 variant 固定模型并将错配视为失败。Flash 只发生在评测请求，B 的既有 route-first 与 GLM-Rerank 保持不变。

**Tech Stack:** Python 3、FastAPI SSE、pytest、CSV/JSON 安全评测元数据。

## Global Constraints

- A 请求模型固定为 `deepseek-v4-pro`，B 请求模型固定为 `deepseek-v4-flash`。
- 生产前端的用户模型选择与默认模型不得改写。
- B 保留真实 `paratera / GLM-Rerank`，不得启用 BGE 或最终答案语义缓存。
- 输出不得包含回答正文、完整证据、供应商原始载荷、隐藏推理或凭据。
- 未获得单独授权不得执行 `git add`、commit、tag、push 或 PR。

---

### Task 1: E2E 请求模型与观察模型合同

**Files:**
- Modify: `scripts/evaluate_phase63_e2e.py`
- Modify: `tests/test_evaluate_phase63_e2e.py`

**Interfaces:**
- Consumes: `execute_case(case, *, base_url, token, timeout_seconds, keep_conversation, capture_answer=False)`。
- Produces: `execute_case(..., chat_model: str | None = None)`；结果包含
  `requested_chat_model` 和 `observed_chat_model` 两个安全字段。

- [ ] **Step 1: 写失败测试**

```python
def test_phase63_e2e_output_keeps_safe_selected_model_diagnostics() -> None:
    assert "requested_chat_model" in OUTPUT_FIELDS
    assert "observed_chat_model" in OUTPUT_FIELDS
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_evaluate_phase63_e2e.py::test_phase63_e2e_output_keeps_safe_selected_model_diagnostics -q`

Expected: FAIL，因为输出 schema 尚未包含这两个字段。

- [ ] **Step 3: 最小实现**

在 `evaluate_events` 读取 `metadata["chat_model"]`；在 `execute_case` 新增可选
`chat_model`，仅在它非空时加入 SSE JSON body。结果写入请求值和观察值；若二者均有
且不等，设 `ok=False`、`error_category="selected_chat_model_mismatch"`。把两个字段
加入 `OUTPUT_FIELDS`，不存储任何回答文本。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `python -m pytest tests/test_evaluate_phase63_e2e.py -q`

Expected: PASS。

### Task 2: Phase 64 固定 Pro/Flash 配对合同

**Files:**
- Modify: `scripts/evaluate_phase64_latency_ab.py`
- Modify: `tests/test_evaluate_phase64_latency_ab.py`

**Interfaces:**
- Consumes: `execute_case(..., chat_model=...)` 的安全结果字段。
- Produces: 固定的 `PHASE63_CHAT_MODEL=deepseek-v4-pro` 与
  `PHASE64_CHAT_MODEL=deepseek-v4-flash`；每个 run 行记录并验证相应模型。

- [ ] **Step 1: 写失败测试**

```python
def test_phase64_variant_models_are_explicit_and_distinct() -> None:
    assert selected_chat_model_for_variant("phase63") == "deepseek-v4-pro"
    assert selected_chat_model_for_variant("phase64") == "deepseek-v4-flash"
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_evaluate_phase64_latency_ab.py::test_phase64_variant_models_are_explicit_and_distinct -q`

Expected: FAIL，因为 variant 模型选择函数尚不存在。

- [ ] **Step 3: 最小实现**

添加狭窄的 variant-to-model helper；把模型通过 `execute_case` 传递，并要求结果的
`observed_chat_model` 等于该 helper 选择。保持现有随机交替顺序、P50/P95、功能与盲评
计算不变；错配结果不可成为通过行。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `python -m pytest tests/test_evaluate_phase64_latency_ab.py tests/test_evaluate_phase63_e2e.py -q`

Expected: PASS。

### Task 3: B 的 Flash 非思考最终生成回归

**Files:**
- Modify: `tests/test_phase64_short_loop.py`

**Interfaces:**
- Consumes: `phase64_final_answer_provider(provider, settings)`。
- Produces: 对 `deepseek-v4-flash` 的 B provider 保留 `model_name` 并加
  `thinking={"type": "disabled"}`，不改变输入 provider。

- [ ] **Step 1: 写失败测试**

```python
def test_phase64_final_provider_disables_thinking_for_flash_b(monkeypatch) -> None:
    provider = OpenAICompatibleChatModelProvider(model_name="deepseek-v4-flash", ...)
    final_provider = phase64_final_answer_provider(provider, get_settings())
    assert final_provider.model_name == "deepseek-v4-flash"
    assert final_provider.extra_body["thinking"] == {"type": "disabled"}
```

- [ ] **Step 2: 运行测试确认现有行为或 RED**

Run: `python -m pytest tests/test_phase64_short_loop.py::test_phase64_final_provider_disables_thinking_for_flash_b -q`

Expected: PASS if the existing `deepseek-v4` B predicate already covers Flash; otherwise FAIL and continue to the minimal predicate repair.

- [ ] **Step 3: 最小实现（仅在 RED 时）**

将 B-only 的 DeepSeek V4 判断扩展到 `deepseek-v4-flash`，保留 Pro、非 DeepSeek 与 A
不变；不得新建 BGE 或 fallback 路径。

- [ ] **Step 4: 运行定向回归**

Run: `python -m pytest tests/test_phase64_short_loop.py -q`

Expected: PASS。

### Task 4: 安全评测与阶段记录

**Files:**
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `handoff.md`
- Modify: `obsidian-agent开发/阶段/阶段 64 - 主流 Agent 延迟优化/01-开发记录.md`

- [ ] **Step 1: 静态和定向验证**

Run: `python -m py_compile scripts/evaluate_phase63_e2e.py scripts/evaluate_phase64_latency_ab.py`

Run: `python -m pytest tests/test_evaluate_phase63_e2e.py tests/test_evaluate_phase64_latency_ab.py tests/test_phase64_short_loop.py -q --tb=short`

Expected: PASS。

- [ ] **Step 2: 更新安全工作记忆**

记录 Flash 仅为用户显式选择的 B 测试 lane、Pro A 冻结、GLM-Rerank 保留，以及尚未运行的
真实配对评测；不写入任何原始请求、回答、证据、provider 载荷或凭据。

- [ ] **Step 3: 运行格式检查**

Run: `git diff --check`

Expected: 无实际空白错误；Windows CRLF 提示不视为错误。
