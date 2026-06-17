# 阶段 42：生成质量校准与生产体验完善

## 目标

阶段 42 从阶段 41 合并后的本地 `main -> d7dfca1 Merge phase 41 post-import retrieval optimization` 出发，目标分支为 `codex/phase-42-generation-quality-and-experience`。阶段 41 已让导入后语料进入完整检索链路：`documents=753`，`indexable child chunks=19300`，GLM 与 deterministic embedding 全覆盖，GLM FAISS 可 `faiss_only` 加载，Stage 30 保持 `91.52 / A / pass`。

本阶段只推进两条主线：

```text
主线 A：生成质量校准
Stage 38 24 cases + Stage 41 12 queries
-> 扩展 Judge 评测集（约 36 cases）
-> 默认 dry-run，显式 --execute 才运行真实 Judge
-> 低分样例归因
-> prompt_builder.py 微调
-> Judge 复跑并诚实记录 gate

主线 C：生产体验完善
长回答段落级分段渲染
-> 会话 hard delete API/UX 回归
-> 会话重命名 API + 前端 right-click context menu
-> 桌面与 390x844 移动端 smoke
```

## 当前基线

- 默认 Agent 链路继续使用 `tool_calling_agent`。
- Stage 38 当前最优策略继续是 `structured_final_answer`，历史真实 Judge 为 `answer_coverage=0.808 / citation_support=0.867 / safety_leak_check=1.000 / gate=pass`。
- Stage 41 新语料检索集为 12 queries，GLM 检索评测为 `p@1=0.833 / p@3=0.833 / p@5=1.000 / coverage=0.972`。
- 前端继续是原生 HTML/CSS/JS，不引入 React、Vue、Node 或构建链。
- Phase 40 已有 `AbortController` 停止生成、token buffer + `requestAnimationFrame` flush、最终 HTML sanitizer，但尚未做长回答段落级分段渲染。

## Phase 顺序

阶段 42 严格按 `task_plan.md` 推进，并在每个 Phase 完成后更新 `task_plan.md`、`findings.md`、`progress.md`：

1. Phase 0：启动校准与规划落盘。
2. Phase 1：设计文档与测试合同。
3. Phase 2：Judge 评测集扩展。
4. Phase 3：低分样例分析与 prompt 微调。
5. Phase 4：长回答分段渲染。
6. Phase 5：会话管理 UX。
7. Phase 6：全量回归与 Stage 30。
8. Phase 7：浏览器 smoke。
9. Phase 8：文档与 Obsidian 收尾。

开发过程中暂不写 Obsidian 小 Phase 汇报；全部开发、测试和普通文档完成后统一补齐。

## 主线 A：Judge 评测扩展

阶段 42 新增独立的扩展 Judge 输入与结果，避免覆盖 Stage 38 历史结果。评测集来源为：

- `scripts.evaluate_stage38_tool_calling_quality.EVAL_CASES` 中 24 条 Stage 38 case。
- `data/evaluation/stage41_post_import_retrieval_queries.csv` 中 12 条 Stage 41 新语料 query。

扩展脚本必须继续默认 dry-run。只有显式 `--execute` 才允许调用真实 answer provider 与 Judge provider。真实结果 CSV 只允许保存：

- query id、category、strategy、status。
- answer provider/model 与 judge provider/model 名称。
- citation/source/tool 调用计数。
- `faithfulness`、`answer_coverage`、`citation_support`、`refusal_correctness`、`conciseness`、`safety_leak_check`。
- `risk_level`、短理由、next_action、脱敏错误摘要。

不得保存 raw answer、raw provider JSON、`raw_response`、`reasoning_content`、hidden thought、API key、Bearer token、Authorization header、完整 chunk 正文或受限全文。

Gate 继续使用六指标门槛：`faithfulness`、`answer_coverage`、`citation_support`、`refusal_correctness`、`conciseness`、`safety_leak_check` 均值均需 `>= 0.80`，且不能有 high risk。若扩展到新语料后 gate 未 pass，必须诚实记录 `review_required` 或 `blocked`，不得用 dry-run 或 skipped 伪装成功。

## 主线 A：Prompt 微调边界

低分样例先归因为：

- prompt citation gap。
- context/retrieval gap。
- answer coverage gap。
- refusal boundary gap。
- judge artifact。

只有归因为 prompt citation gap 或 answer coverage gap 时，才优先微调 `app/services/generation/prompt_builder.py`。微调方向限定为：更贴近事实句的 `[N]` 引用、覆盖上下文支持的多个要点、对新语料术语给出简短解释、证据不足时明确说明缺口。

本阶段不改变 Stage 30 评分规则、默认 provider 拓扑、数据源边界、tool-calling loop 架构或 deterministic validator 生产接入状态。

## 主线 C：长回答分段渲染

Phase 40 已完成 token flush 节流，但最终 `finalizeAgentStreamingMessage()` 仍会对长回答执行一次性 `innerHTML` 替换。阶段 42 采用段落级分段插入：

```text
answer text
-> normalize citations
-> renderAnswerWithCitationLinks
-> sanitizeRenderedHtml
-> split rendered HTML into bounded paragraph/line segments
-> append chunks to .answer-text with insertAdjacentHTML / DocumentFragment
```

实现要求：

- 不做完整虚拟列表，不重构滚动容器。
- 不引入 React/Vue/Node。
- 保持 citation popover、invalid citation、sanitize、AbortController、停止生成、stored conversation render 可用。
- 大于约 2000 token 的回答不应因单次大段 `innerHTML` 替换造成严重卡顿。

## 主线 C：会话删除与重命名

会话删除沿用当前无认证系统下的 hard delete 策略：删除 conversation 时级联删除 messages。后端已存在 `DELETE /conversations/{conversation_id}`，本阶段需要补齐设计记录、回归测试和前端 UX 验证。

会话重命名新增：

```text
PATCH /conversations/{conversation_id}
body: {"title": "..."}
-> normalize_conversation_title
-> updated_at 刷新
-> 返回 ConversationItem
```

前端采用左侧会话列表的 right-click context menu：用户右键会话后在指针附近选择重命名或删除；右键打开菜单不会切换当前会话。重命名继续复用 PATCH API，空标题按 schema/仓储规则归一为默认标题。重命名成功后刷新会话列表并保持当前会话状态一致。

## 验证合同

阶段 42 收尾至少运行：

```powershell
python -m pytest tests/test_stage42_design.py -q
python -m pytest -q
python scripts/score_stage30_quality.py
python scripts/run_production_smoke.py
```

真实 Judge 运行必须显式：

```powershell
python scripts/judge_stage42_generation_quality.py --execute
```

浏览器 smoke 覆盖桌面与 `390x844` 移动端：

- Agent 问答与新语料检索。
- 长回答分段渲染。
- 会话删除。
- 会话重命名 right-click context menu。
- 停止生成仍可用。
- 无横向溢出，console errors=0。

## 安全与提交边界

阶段 42 不做：

- 不改变 Stage 30 评分规则、权重、等级阈值或 release decision。
- 不改变 provider 拓扑或数据源边界。
- 不新增外部数据源、爬虫、PDF 下载或受限全文写入。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk 正文或受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 阶段 42 开发完成后不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR，停在用户人工核验前。

## 完成标准

- `docs/stage42_generation_quality_and_experience.md` 与 `tests/test_stage42_design.py` 完成。
- Judge 覆盖 Stage 38 + Stage 41 新语料，有可追踪 CSV 与 gate 结论。
- prompt 微调如有落地，已通过回归；如 gate 未 pass，已诚实记录。
- 长回答段落级分段渲染可用。
- 会话 hard delete 与 inline rename 前后端状态一致。
- Stage 30 维持 `91.52 / A / pass` 或更高。
- 全量 pytest 通过。
- 桌面 + 移动浏览器 smoke 通过。
- README、`docs/progress.md`、`docs/architecture.md`、`docs/phase_reviews/phase-42.md` 与 Obsidian 草稿完成。
## Final UX And Submission Update

After the original Phase 42 design contract, the conversation UX was refined to match mainstream web chat products. The final frontend contract is:

- Conversation list lives in the left sidebar.
- Right-clicking a conversation opens a pointer-adjacent context menu and must not switch/load that conversation.
- Rename and delete are selected from the context menu; rename continues to call `PATCH /conversations/{conversation_id}` and title normalization still uses `normalize_conversation_title`.
- The message composer is fixed at the bottom of the conversation panel.
- The message area scrolls internally, and the left conversation list has its own scroll container.
- Bottom answer citations collapse into a dark right-aligned source pill that opens the citation detail drawer.

Submission update: Phase 42 was originally stopped before human verification. On 2026-06-17 the user explicitly authorized Phase 42 submission and GitHub merge. No phase tag is created unless separately requested.
