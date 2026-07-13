# Phase 64 官方智谱 Rerank 迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Phase 64 冻结 A/B 的真实 rerank 身份严格迁移为官方智谱 `zhipu / rerank`，并在不回退检索和质量门禁的前提下继续延迟评测。

**Architecture:** 本机被忽略的 `.env` 已保存官方运行时配置；版本化代码不保存凭据。健康契约继续公开安全的 provider/model 字符串，评测器将该对作为两端必需身份，并保留严格 pgvector、冷缓存、A/B 执行图与功能门禁。

**Tech Stack:** Python 3、FastAPI health contract、pytest、Phase 64 CSV/JSON 安全评测产物。

## Global Constraints

- Phase 64 A 与 B 都必须使用 `reranking_provider=zhipu` 与 `reranking_model_name=rerank`。
- 真实 rerank、严格 pgvector、四类冷缓存关闭、Flash/Pro 用户选择和 75 候选池均保持不变。
- 不恢复并行云、BGE 或任意 fallback；不在限流时静默关闭 rerank。
- 不在版本化文件、测试、评测产物或文档中写入 API key、回答、候选正文、原始响应或隐藏推理。
- 未获单独授权不得执行 `git add`、commit、tag、push 或 PR。

---

### Task 1: 冻结合同迁移为官方智谱身份

**Files:**
- Modify: `scripts/evaluate_phase64_latency_ab.py:145-190`
- Modify: `tests/test_evaluate_phase64_latency_ab.py:110-145`

**Interfaces:**
- Consumes: `/health/retrieval-contract` 的 `reranking_enabled`、`reranking_provider` 与 `reranking_model_name`。
- Produces: `validate_frozen_contract(phase63, phase64)` 只在双方报告 `zhipu / rerank` 时返回 `ok=True`。

- [ ] **Step 1: 写失败测试**

```python
def test_frozen_contract_requires_official_zhipu_rerank() -> None:
    contract = _official_contract()
    assert validate_frozen_contract(contract, contract)["ok"] is True
    contract["reranking_provider"] = "paratera"
    assert "phase63_reranking_provider_invalid" in validate_frozen_contract(contract, contract)["violations"]
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/test_evaluate_phase64_latency_ab.py::test_frozen_contract_requires_official_zhipu_rerank -q`

Expected: FAIL，因为评测器仍只接受 `paratera / GLM-Rerank`。

- [ ] **Step 3: 最小实现**

在 `validate_frozen_contract` 将 provider/model 的精确预期替换为 `zhipu` 与
`rerank`；保留所有其余语料、pgvector、缓存和执行图检查。

- [ ] **Step 4: 运行 GREEN**

Run: `python -m pytest tests/test_evaluate_phase64_latency_ab.py -q`

Expected: PASS。

### Task 2: 安全 health 契约回归

**Files:**
- Modify: `tests/test_health_details.py:147-173`

**Interfaces:**
- Consumes: `/health/retrieval-contract` 的安全 provider/model 字段。
- Produces: health 测试验证 `zhipu / rerank`，仍不包含 API key 或内容。

- [ ] **Step 1: 写失败测试**

```python
monkeypatch.setenv("RERANKING_PROVIDER", "zhipu")
monkeypatch.setenv("RERANKING_MODEL_NAME", "rerank")
assert payload["reranking_provider"] == "zhipu"
assert payload["reranking_model_name"] == "rerank"
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/test_health_details.py::test_retrieval_contract_health_is_safe_and_content_free -q`

Expected: FAIL，因为测试 fixture 仍声明旧云身份。

- [ ] **Step 3: 最小实现**

只替换测试环境与断言中的 provider/model；health schema/API 已按配置透传，无需扩展
响应或新增敏感字段。

- [ ] **Step 4: 运行 GREEN**

Run: `python -m pytest tests/test_health_details.py::test_retrieval_contract_health_is_safe_and_content_free -q`

Expected: PASS。

### Task 3: 验证和继续 Phase 64

**Files:**
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `handoff.md`
- Modify: `obsidian-agent开发/阶段/阶段 64 - 主流 Agent 延迟优化.md`

- [ ] **Step 1: 运行定向回归**

Run: `python -m py_compile scripts/evaluate_phase64_latency_ab.py`

Run: `python -m pytest tests/test_evaluate_phase64_latency_ab.py tests/test_health_details.py -q --tb=short`

Expected: PASS。

- [ ] **Step 2: 重启两套本地评测进程并验证契约**

使用本机 `.env` 的官方智谱配置，A 保持 `AGENT_SHORT_LOOP_ENABLED=false`，B 保持
`true`；两端必须通过 `validate_frozen_contract` 后才可发出真实 SSE 请求。

- [ ] **Step 3: 运行小型冻结配对探针**

Run: `python scripts/evaluate_phase64_latency_ab.py --phase63-base-url http://127.0.0.1:8063 --phase64-base-url http://127.0.0.1:8064 --cases data/evaluation/phase64_latency_cases.csv --limit 3 --runs 1 --seed 640013 --out data/evaluation/phase64_zhipu_flash_probe.csv --summary-out data/evaluation/phase64_zhipu_flash_probe_summary.json`

Expected: 输出安全指标；只有完整功能、质量与 P50/P95 门禁通过时才可宣称阶段达标。

- [ ] **Step 4: 更新安全工作记忆并检查差异**

Run: `git diff --check`

Expected: 无实际空白错误；不执行任何 Git submission 动作。
