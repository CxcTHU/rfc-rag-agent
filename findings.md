# Findings & Decisions

## Requirements

- 用户要求正式进入阶段 13：Decompose 与证据合并。
- 线程标题已修改为 `阶段13-Decompose与证据合并`。
- 目标分支为 `codex/phase-13-decompose-evidence-merge`。
- 阶段 13 必须从阶段 12 已完成并合并到 `main` 的状态出发。
- 必须确认 `phase-12-complete` 指向阶段 12 最终功能提交，不移动已有阶段 tag。
- 阶段 13 不做登录系统、不做部署优化、不做写入型 Agent 工具、不把 HyDE 接入默认链路、不引入复杂长期记忆系统。
- 阶段 13 重点是规则式 Decompose、子 query 检索、证据合并、按 `chunk_id` 去重、sub_query provenance 和可解释 rerank。
- 必须保留阶段 11 词表型 query expansion，继续复用 Brain evidence confidence，不绕过拒答边界。
- 必须保证旧 API 兼容：`POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`。
- 开发阶段不写 Obsidian 小 Phase 汇报，收尾时统一补齐。

## Current Project Findings

- 当前工作区已切换到 `codex/phase-13-decompose-evidence-merge`。
- `main` 最新提交为 `5c7bb58a7905472473a12a7c4dfb3908c853f8e0`，提交信息为 `merge phase 12 quality review context calibration`。
- `phase-12-complete` 指向 `d7b5bffa79e763b3c7ac6acf689114506a0e0b5c`。
- 阶段 13 分支从阶段 12 合并后的 `main` 创建，起点没有未提交改动。
- README 和 `docs/progress.md` 仍以阶段 12 完成为最新状态，阶段 13 收尾时需要校准为阶段 13 完成状态。
- 阶段 12 记录的全量测试为 `244 passed`。

## Architecture Findings

- 阶段 8 已把 `/chat` 与 Agent `answer_with_citations` 收敛到 `BrainService`，阶段 13 应优先在 Brain/retrieval 边界接入 Decompose，而不是复制 chat/agent 编排。
- Brain 默认 workflow 为 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer`。
- 阶段 12 的 `rewrite_query` 已处理最小上下文补全；阶段 13 的 Decompose 应发生在补全后的 retrieval question 上。
- `BrainService._generate_answer_step()` 在生成前调用 evidence confidence，阶段 13 合并后的证据必须继续经过这层判断。
- `RetrievalConfig` 已集中控制检索模式、top_k、min_score、history 和 rerank 参数；阶段 13 可优先扩展配置或在 retrieve step 内保守接入。
- `HybridSearchService` 已有 keyword/vector 合并、`chunk_id` 去重、分数归一化和 both-match bonus 思路，阶段 13 可以复用其可解释合并经验。

## Existing Code Findings

- `app/services/brain/service.py` 包含 workflow 编排和检索入口。
- `app/services/brain/config.py` 定义 `RetrievalConfig`、`WorkflowConfig` 和默认 workflow steps。
- `app/services/brain/workflow.py` 定义 `BrainRetrievalOutcome`、`BrainAnswerResult`、`EvidenceConfidence` 和 citation 提取。
- `app/services/retrieval/hybrid_search.py` 是现有混合检索与 both-match 信号参考实现。
- `app/services/retrieval/keyword_search.py` 的 `SYNONYM_RULES` 是阶段 11 词表型 query expansion 的权威来源。
- `app/services/retrieval/vector_search.py` 已有 topic anchor rerank，阶段 13 不应掩盖 vector-only baseline。
- `scripts/evaluate_user_questions.py` 已比较 `default_hybrid`、`keyword_baseline`、`vector_only`，适合阶段 13 复跑不退化。
- `docs/stage13_decompose_plan.md` 当前是预研计划，需要升级为实现设计或补充最终实现说明。

## API Contract Findings

- `POST /chat` 当前支持 `history` 可选字段，旧请求不传 history 仍兼容。
- `POST /agent/query` 当前支持 `history` 可选字段，Agent 不新增写入型工具。
- 基础 search API 不应为了阶段 13 改 schema；如果需要展示 Decompose 细节，应优先在评测产物、workflow step 或内部结构记录。
- 对外 `ChatResponse.question` 应继续保留用户原始问题，避免把拆解后的 query 暴露为替换问题。
- 若返回 sources 仍使用 `ContextSource`，sub_query provenance 需要在不破坏现有 schema 的前提下保存或用于内部排序。

## Evaluation Findings

- 阶段 12 用户问题评测保持 `25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
- 用户问题分配置结果：`default_hybrid=10/10`、`keyword_baseline=10/10`、`vector_only=5/10`。
- 阶段 12 审阅结论：default_hybrid 来源命中可靠，但 deterministic answer 不能证明真实语言表达覆盖度；vector_only 的失败应作为阶段 13 rerank/Decompose/真实 embedding 对比输入。
- 优先验证问题：`user_mixed_cost_emission`、`user_cn_colloquial_compactness`、`user_cn_porosity_compression`、`user_en_freeze_thaw`、`user_cn_creep`。
- unsupported 随机问题必须继续拒答，不能因为拆解逻辑而被误判为可回答。
- 阶段 13 需要新增评测输出，记录子 query、召回来源、去重和 rerank 解释。

## Data Source Findings

- 阶段 13 不新增外部文献来源，不改变 source registry 合规边界。
- 阶段 13 新增的设计文档、评测 CSV 和测试文件都是评测/工程产物，不是资料来源。
- `sources` 仍管理资料来源、可信度、权限和状态；`documents/chunks` 仍管理可检索正文和题录卡片。
- `chunk_embeddings` 是由 chunks 派生的可重建索引数据。
- 真实 API key 只允许存在本地 `.env`，不能写入文档、CSV、测试或 Obsidian。

## Technical Decisions

| Decision | Reason |
|---|---|
| Decompose 放在 Brain/retrieval 边界 | `/chat` 和 Agent 已共享 Brain，避免重复实现 |
| 先做规则式拆解 | 不依赖真实模型，保证本地回归稳定 |
| 子 query 最多 3 个 | 控制召回噪声、成本和上下文长度 |
| 只拆明显并列结构 | 降低误拆解风险，尤其保护 unsupported |
| 保留阶段 11 `SYNONYM_RULES` | keyword、vector topic anchor、evidence confidence 都共享该词表 |
| 合并后按 `chunk_id` 去重 | 避免同一片段重复引用和污染 prompt |
| provenance 先作为内部证据解释 | 保持外部 API schema 兼容 |
| HyDE 只保留离线实验建议 | 避免假想答案污染引用式 RAG 的依据边界 |

## Phase Findings

### Phase 0

- 线程标题已修改为阶段 13。
- 已阅读 Planning with Files 技能说明。
- 已阅读阶段启动所需普通文档、阶段 12 质量审阅报告、阶段 13 预研计划、旧规划文件和关键进度记录。
- `main` 与 `phase-12-complete` 已确认。
- 已创建并切换阶段 13 分支。
- 三份 Planning with Files 文件已校准为阶段 13。
- 起点全量测试通过：`244 passed`。

### Phase 1

- Phase 1 目标是把阶段 13 的预研计划固化为可实现、可测试的设计输入。
- 已将 `docs/stage13_decompose_plan.md` 从预研计划升级为阶段 13 设计文档。
- 文档明确 Decompose 不替换默认 RAG 链路，而是在 Brain 检索阶段增加可解释证据增强路径。
- 拆解规则只覆盖明显并列主题，子 query 最多 3 个；乱字符串、unsupported、单主题问题和无法形成领域主题词的问题不拆。
- 文档建议内部结构：`DecomposedQuery`、`SubQueryRetrievalResult`、`MergedEvidence`，用于服务、评测 CSV 和调试说明，不破坏外部 API schema。
- 评测指标新增 `decompose_applied`、`sub_query_count`、`deduplicated_count`、`provenance_present` 和 `default_hybrid_regressed`。
- 设计测试结果：`7 passed`。

### Phase 2

- Phase 2 目标是把阶段 13 设计落成可单测的 retrieval service。
- 新增 `app/services/retrieval/decompose.py`。
- 新增 `DecomposedQuery`、`SubQueryRetrievalResult`、`MergedEvidence` 和 `DecomposeRetrievalOutcome`。
- `decompose_query()` 只对明显多主题问题拆解，最多 3 个子 query；单主题和 unsupported 问题保持原样。
- `DecomposeRetrievalService.retrieve()` 会对每个 sub query 调用 keyword/vector/hybrid 检索，再合并候选。
- `merge_sub_query_results()` 按 `chunk_id` 去重，并把命中同一 chunk 的 sub query 合并到 `MergedEvidence.sub_queries`。
- 可解释 rerank 记录 topic terms、both_match、source_type、raw_score 和 final_score。
- 新增 `tests/test_decompose_retrieval.py`，覆盖纯规则、unsupported 边界、去重 provenance、解释字段和临时数据库服务调用。
- Phase 2 测试结果：`16 passed`。

### Phase 3

- Phase 3 目标是把 Decompose 检索路径接入 Brain，同时保持旧 API 和默认 workflow 不退化。
- `BrainService._retrieve_with_hybrid()` 现在先调用轻量 `decompose_query()`；只有问题真的被拆解时才调用 `DecomposeRetrievalService`。
- 单主题 hybrid 问题继续走原有 `HybridSearchService`，避免额外检索导致默认链路波动。
- 复杂 hybrid 问题会使用 `MergedEvidence` 作为 Brain 检索结果，后续仍经过 `build_retrieval_outcome()` 和 evidence confidence。
- 初次接入时发现 Brain workflow `default_hybrid` 的 rfc_concept 退化，原因是先执行 Decompose 服务再判断是否拆解；修复后 Brain workflow 恢复 `18/18`。
- 用户问题评测从阶段 12 的 `25/30` 提升到 `29/30`，剩余失败保留在 vector_only 孔隙率问题，符合“不要隐藏 vector-only 边界”的要求。
- API 回归保持通过：search/vector/chat/agent API 18 passed。

### Phase 4

- Phase 4 目标是把阶段 13 的 Decompose 能力变成可复现评测产物。
- 新增 `scripts/evaluate_decompose.py`，默认评测 5 个阶段 13 优先问题和 `user_unsupported_random`。
- 新增 `data/evaluation/stage13_decompose_results.csv`，记录 decompose_applied、sub_query_count、sub_queries、raw/merged/deduplicated count、provenance_present、source_hit、answer_coverage_proxy 和 rerank_explanations。
- 新增 `tests/test_evaluate_decompose.py`。
- 初次评测 5/6，失败项是 unsupported 的 source_hit 口径问题：Brain 已正确拒答且 sources 为空，但通用 `source_matches_expectation()` 对空期望词返回 true。
- 已新增 `actual_source_hit_for_expected_question()`，当 expected_source_hit=no 时，只有实际 sources 非空才视为 actual_source_hit=true。
- 修正后阶段 13 Decompose 评测：`6/6 passed`，`decomposed=3`，`refused=1`，`source_hit_matched=6/6`。

### Phase 5

- Phase 5 目标是确认阶段 13 对既有检索、问答、Agent、Brain workflow 和前端入口不造成破坏。
- 聚焦测试通过：`31 passed`，覆盖 Decompose、评测脚本、Brain/user question/Brain workflow 测试和前端入口测试。
- `scripts/evaluate_decompose.py --include-all` 通过：`10/10`，其中 `decomposed=3`、`refused=1`、`source_hit_matched=10/10`。
- deterministic hybrid 评测通过：`15/15`，`regressed_keyword=0`。
- deterministic vector baseline 为 `13/15`，保留 mesoscopic_modeling 与 construction_management 两个 keyword_only_pass 失败边界。
- 一次并行回归中默认读取 `.env` 的真实 embedding provider，触发 HTTP 429；已按阶段规则改为显式 deterministic provider 复跑，不把真实服务限流作为代码失败。
- 前端不需要在 Phase 5 修改：外部 API schema 未改变，Decompose 细节通过 `stage13_decompose_results.csv` 和内部 `MergedEvidence.explanation` 保留；阶段 13 不做前端重构。

### Phase 6

- Phase 6 目标是把阶段 13 的实现、评测和边界同步到普通文档与 Obsidian 本地知识库，并用最终全量测试、提交和 tag 固定阶段成果。
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD`，将最新状态校准为阶段 13 完成。
- 普通文档记录了 Decompose 数据流、`MergedEvidence`、可解释 rerank、阶段 13 评测脚本、`data/evaluation/stage13_decompose_results.csv` 和下一阶段建议。
- Obsidian 本地知识库已补齐阶段 13 阶段页、阶段汇报目录、Phase 0-6 小 Phase 汇报、阶段汇报索引、阶段索引、首页、RAG/评测分类页和知识点页。
- 每篇 Obsidian 小 Phase 汇报均已校验包含 10 个固定小节；`obsidian-vault/` 仍被 Git 忽略，不纳入提交。
- 最终全量测试通过：`.venv\Scripts\python.exe -m pytest -q` -> `257 passed`。
- 最终提交和 `phase-13-complete` tag 用于固定阶段 13 最终功能状态；既有阶段 tag 不移动。

## Term Explanations

| Term | Explanation |
|---|---|
| Decompose | 把一个复杂问题拆成多个子 query 分别检索，例如把“成本工期和碳排放”拆成三条检索任务 |
| Sub query | 从原问题中拆出的子问题，用来单独召回某一类证据 |
| Evidence merge | 多个子 query 的召回结果合并成统一证据池 |
| `chunk_id` 去重 | 同一个资料片段只保留一次，避免重复进入回答上下文 |
| Provenance | 证据来源说明，记录某个 chunk 是被哪个 sub query 召回的 |
| Rerank | 对候选证据重新排序，把更贴题、更可信的片段放前面 |
| Both-match signal | 同一 chunk 同时被关键词和向量检索命中，说明结果更稳 |
| MergedEvidence | 阶段 13 新增的内部证据结构，既像普通检索结果一样能进 Brain，又额外记录 sub query 来源和 rerank 解释 |
| Obsidian Phase 汇报 | 本项目本地知识库中的阶段记录，每个小 Phase 固定包含目标、任务、修改内容、关键模块、问题、术语、验证、遗留问题、下一步和面试表达 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| README/docs 最新状态仍停在阶段 12 | README 与 docs/progress 最新段落 | 阶段 13 收尾统一校准 |
| Brain default_hybrid 初次接入出现 5/6 | `data/evaluation/brain_workflow_results.csv` 中 rfc_concept 拒答 | 已修复为先判断是否拆解再执行 Decompose 服务 |
| Decompose 评测初次 unsupported source_hit 不匹配 | `stage13_decompose_results.csv` 中 unsupported 已拒答但 actual_source_hit=yes | 已修正阶段 13 脚本：expected_source_hit=no 时以是否返回 sources 判断 |
| 并行评测触发真实 embedding HTTP 429 | `evaluate_hybrid_search.py` 默认读取 `.env` provider，真实服务返回 concurrency limit | 显式使用 `--provider deterministic` 复跑 hybrid/vector，作为自动回归证据 |

## Resources

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage12_quality_review.md`
- `docs/stage13_decompose_plan.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `app/services/brain/service.py`
- `app/services/brain/config.py`
- `app/services/brain/workflow.py`
- `app/services/retrieval/hybrid_search.py`
- `app/services/retrieval/keyword_search.py`
- `app/services/retrieval/vector_search.py`
- `scripts/evaluate_user_questions.py`
- `data/evaluation/user_questions.csv`
- `data/evaluation/user_question_results.csv`
