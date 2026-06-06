# Findings & Decisions

## Requirements

- 用户要求正式进入阶段 11：真实用户问题评测集与跨语言质量提升。
- 线程标题已修改为 `阶段11-真实用户问题评测集与跨语言质量提升`。
- 目标分支为 `codex/phase-11-user-evaluation-query-expansion`。
- 阶段 11 必须从阶段 10 已完成并合并到 `main` 的状态出发。
- 必须确认 `phase-10-complete` 指向阶段 10 最终功能提交，不移动已有阶段 tag。
- 阶段 11 不做登录系统、不做部署优化、不做大规模前端重构、不做写入型 Agent 工具。
- 阶段 11 重点是真实用户问题评测、跨语言 query expansion、质量审阅和可复现指标。
- 开发阶段不写 Obsidian 小 Phase 汇报，收尾时统一补齐。

## Current Project Findings

- 当前工作区已切换到 `codex/phase-11-user-evaluation-query-expansion`。
- `main` 最新合并提交为 `c0bf8d6f9250db9bca00a686aa277f1adc5eb55c`，提交信息为 `merge phase 10 rag quality calibration`。
- `phase-10-complete` 指向 `1454919eb8d9615f5ae32e069c8dcfe56829ba90`。
- 阶段 10 最终全量测试记录为 `216 passed`，阶段 11 启动后的起点全量测试也为 `216 passed`。
- 普通文档仍有阶段 10 分支口径，Phase 6 需要统一校准为阶段 11 完成状态。

## Architecture Findings

- 阶段 8 已把 `/chat` 与 Agent `answer_with_citations` 收敛到 `BrainService`，用户问题评测应优先复用 Brain workflow。
- `BrainService.retrieve()` 支持 `auto`、`vector`、`keyword`、`hybrid`；阶段 11 通过 `default_hybrid`、`keyword_baseline`、`vector_only` 三种配置比较。
- `BrainService._generate_answer_step()` 在生成前调用 evidence confidence；低证据时拒答并清空 sources/citations。
- `VectorSearchService` 使用 topic anchor rerank，且 topic anchor 复用 `keyword_search.expand_query_terms()`。
- `chunk_embeddings` 同时保存 deterministic 64 维索引和 Jina 1024 维索引；阶段 11 自动回归仍默认 deterministic。
- API schema 当前不需要变化；阶段 11 通过新增评测文件、脚本和词表增强推进质量。

## Existing Code Findings

- `app/services/retrieval/keyword_search.py` 的 `SYNONYM_RULES` 是当前最适合扩展跨语言术语的入口。
- `app/services/retrieval/vector_search.py` 的 `topic_anchor_score()` 调用 `expand_query_terms()`，因此扩展 `SYNONYM_RULES` 会同时影响 keyword 召回和 vector 候选内部重排。
- `app/services/retrieval/hybrid_search.py` 保留 keyword/vector 分数，可用于对比用户问题集下不同召回通道的表现。
- `scripts/evaluate_chat.py` 已实现引用有效性、拒答匹配、来源命中和禁止词检查。
- `scripts/evaluate_brain_workflow.py` 已比较 `default_hybrid`、`keyword_baseline`、`vector_only`，适合给用户问题评测脚本复用设计。
- 前端已支持 keyword/vector/hybrid 搜索、chat 检索模式和 Agent 面板；阶段 11 不需要前端重构。

## API Contract Findings

- `POST /search`、`POST /search/vector`、`POST /search/hybrid` 仍只负责返回检索结果。
- `POST /chat` 响应已有 `refused`、`refusal_reason`、`sources`、`citations`、`retrieval_mode`、`model_provider`、`model_name`。
- `POST /agent/query` 响应已有工具调用、来源、引用、拒答和 `reasoning_summary`。
- 阶段 11 不新增 API 必填字段，避免破坏现有前端和测试。

## Evaluation Findings

- 阶段 10 deterministic 结果：keyword 15/15、vector 13/15、hybrid 15/15、chat 6/6、agent 5/5、Brain workflow 18/18。
- 阶段 10 真实模型校准结果：Jina vector 15/15、Jina hybrid 15/15、MIMO + Jina chat 6/6、MIMO + Jina agent 5/5、MIMO + Jina Brain workflow 18/18。
- 现有 `chat_queries.csv` 只有 6 条问题，适合阶段 3-10 回归，但不足以代表真实用户问法。
- 现有 `keyword_queries.csv` 有 15 条检索问题，但没有显式 `language_type` 和 `expected_answer_points` 字段。
- 阶段 11 新增独立 `user_questions.csv`，避免覆盖原有 baseline。
- 用户问题评测经过 Phase 3 增强后达到 `25/30 passed`；其中 `default_hybrid=10/10`、`keyword_baseline=10/10`、`vector_only=5/10`。
- 剩余失败集中在 deterministic `vector_only` 的来源命中不匹配，属于向量 baseline 的主题漂移风险，不应通过隐藏 fallback 掩盖。

## Data Source Findings

- 阶段 11 不新增外部文献来源，不改变 source registry 合规边界。
- `data/evaluation/user_questions.csv`、`data/evaluation/user_question_results.csv` 和 `data/evaluation/user_question_review_samples.csv` 都是评测产物，不是新的资料来源。
- Jina 和 MIMO 仍是模型服务，不是文献资料来源。
- 真实 API key 只允许存在本地 `.env`，不能写入文档、CSV、测试或 Obsidian。
- 评测 CSV 只保存问题、期望条件、来源标题、片段摘要、分数、诊断和审阅字段，不保存受限全文。

## Technical Decisions

| Decision | Reason |
|---|---|
| 新增 `user_questions.csv` 而不是直接扩写 `chat_queries.csv` | 保留阶段 10 chat baseline 可比性 |
| 用户问题评测优先复用 Brain workflow | `/chat` 和 Agent 问答已共享 Brain，一处评测覆盖主链路 |
| 继续默认 deterministic provider | 自动回归不依赖真实 API key、网络和余额 |
| 真实 MIMO + Jina 只作为可选校准 | 真实模型贴近体验，但不适合作为必跑测试 |
| 跨语言增强复用 `SYNONYM_RULES` | 现有 keyword 与 vector topic anchor 已共同依赖该词表 |
| 人工审阅先做抽样表和字段设计 | Faithfulness 与 Answer Coverage 需要人工或裁判模型，不宜只靠规则 |

## Phase Findings

### Phase 0

- 线程标题已修改为阶段 11。
- 已阅读 Planning with Files 技能说明。
- 已阅读阶段启动所需普通文档、阶段 10 旧规划文件和关键代码入口。
- `main` 与 `phase-10-complete` 已确认。
- 已创建并切换阶段 11 分支。
- 三份 Planning with Files 文件已校准为阶段 11。
- 起点全量测试为 `216 passed`。

### Phase 1

- Phase 1 目标是新增独立真实用户问题评测集。
- 问题集显式记录 `language_type` 和 `expected_answer_points`，服务真实问法与人工审阅。
- 已新增 `data/evaluation/user_questions.csv`，包含 10 条问题。
- 覆盖 `zh_colloquial`、`en`、`mixed`、`engineering_cn`、`unsupported` 五类语言/场景标签。
- 新增 `tests/test_user_questions.py`，校验字段、语言覆盖、supported/unsupported 约束。
- Phase 1 测试结果：`3 passed`。

### Phase 2

- Phase 2 目标是把 `user_questions.csv` 接入可复现评测脚本。
- 评测脚本复用 Brain workflow，因为阶段 8 后 `/chat` 与 Agent 引用问答已共用 Brain。
- 自动评测判断来源命中、拒答、引用有效性；`expected_answer_points` 先作为人工审阅字段。
- 已新增 `scripts/evaluate_user_questions.py`。
- 新增 `tests/test_evaluate_user_questions.py`，与 `tests/test_user_questions.py` 组合测试结果为 `6 passed`。
- 修正边界：当 `expected_source_hit=no` 且没有期望标题/正文词时，不把空期望误判为 actual source hit。
- 初次用户问题 baseline 为 `15/30 passed`，`refusal_matched=22/30`，`source_hit_matched=15/30`。

### Phase 3

- Phase 3 目标是针对用户问题失败项扩展跨语言 query expansion。
- 失败主要集中在 freeze-thaw、creep、cost/emission、porosity、rock shear key 和 compactness 等术语没有被中文/英文互相增强。
- 已扩展 `SYNONYM_RULES`，覆盖灌满/密实度、现场判断、界面/ITZ、徐变/creep、冻融/freeze-thaw、孔隙率/porosity、碳排放/成本/工期、钢纤维、剪力键等。
- 已更新 Brain evidence confidence，让它可用扩展后的中英文证据词判断跨语言证据是否足够。
- 新增 Brain workflow 测试，确认中文“孔隙率/抗压表现”可被英文 porosity/void/compressive behavior 证据支持。
- 新增 keyword search 测试，覆盖徐变、孔隙率、剪力键三类阶段 11 术语。
- 用户问题评测从 `15/30` 提升到 `25/30`，其中 `default_hybrid=10/10`、`keyword_baseline=10/10`、`vector_only=5/10`。
- 标准回归保持稳定：vector 13/15、hybrid 15/15、chat 6/6、Brain workflow 18/18。

### Phase 4

- Phase 4 目标是补齐人工审阅抽样与 LLM-as-judge 离线设计。
- 自动脚本能检查拒答、引用和来源命中，但 `expected_answer_points` 的覆盖质量仍需要人工或裁判模型判断。
- 已新增 `docs/stage11_user_evaluation_plan.md`，说明自动评测、人工审阅、LLM-as-judge 的分工。
- 已新增 `data/evaluation/user_question_review_samples.csv`，记录 `faithfulness`、`answer_coverage`、`citation_quality`、`reviewer_notes` 等审阅字段。
- 抽样表覆盖默认混合通过样例、vector-only 失败样例、unsupported 拒答样例、中英混合样例和工程中文样例。
- 新增 `tests/test_stage11_user_evaluation_plan.py`，确认文档路径、核心指标、真实 key 边界、CSV schema、语言覆盖和敏感信息约束。
- Phase 4 测试结果：`10 passed`。

### Phase 5

- Phase 5 目标是确认阶段 11 新增评测集、脚本、query expansion 和审阅设计没有破坏既有 RAG 链路。
- deterministic 评测结果保持稳定：keyword 15/15、vector 13/15、hybrid 15/15、chat 6/6、agent 5/5、Brain workflow 18/18。
- 用户问题评测保持 `25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
- `default_hybrid` 与 `keyword_baseline` 在用户问题集上均为 10/10，说明阶段 11 的跨语言词表增强对默认链路有效。
- `vector_only` 在用户问题集上为 5/10，剩余失败均是 deterministic vector-only source hit mismatch；这是保留给下一阶段的真实向量或更强 rerank 校准问题。
- API 回归测试通过：search/vector/chat/agent 相关测试 `16 passed`。
- 全量测试通过：`230 passed`。
- `scripts/evaluate_model_configs.py --include-real-config` 正常输出 deterministic baseline；real_config 因缺少本地真实评测结果文件标记为 `missing_results`，符合不依赖真实 API key 的边界。

### Phase 6

- Phase 6 目标是把阶段 11 的成果同步到普通文档、Obsidian、本地过程文件和 Git 标记。
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD`，把当前状态校准为阶段 11 完成。
- 已新增 Obsidian 阶段页、阶段 11 Phase 汇报索引、Phase 0-6 小 Phase 汇报、阶段索引、阶段汇报索引、首页和 3 个知识点。
- Obsidian 每篇 Phase 汇报均有 10 个固定小节；Git 状态确认 `obsidian-vault/` 仍被忽略。
- 最终全量测试通过：`230 passed`。
- 阶段最终提交和 `phase-11-complete` tag 将作为本阶段完成标识；tag 必须指向阶段 11 最终功能提交。

## Term Explanations

| Term | Explanation |
|---|---|
| 真实用户问题评测集 | 更贴近真实提问方式的问题集合，用来测试系统能否处理口语、英文、中英混合和工程场景 |
| language_type | 问题语言形态标签，例如中文口语、英文、中英混合、工程中文、unsupported |
| expected_answer_points | 希望回答覆盖的技术要点，主要用于人工审阅和 LLM-as-judge |
| Query Expansion | 把用户问题中的词扩展成中英文同义词，例如“徐变”扩成 `creep` |
| 跨语言术语 gap | 用户和资料使用不同语言表达同一技术概念导致召回困难 |
| topic anchor | 阶段 10 中用于约束 vector 候选排序的主题词信号 |
| Faithfulness | 回答是否忠实于检索来源，没有编造资料外事实 |
| Answer Coverage | 回答是否覆盖问题需要的核心技术点 |
| Citation Quality | 引用编号是否能支持回答中的关键说法 |
| LLM-as-judge | 让模型按 rubric 进行质量裁判；本阶段只用于离线抽检，不进入自动回归 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| README/docs 当前分支口径仍停在阶段 10 分支 | README 与 `docs/progress.md` 最新状态段落 | Phase 6 统一校准 |
| 现有 chat 评测集规模较小 | `chat_queries.csv` 只有 6 条 | 阶段 11 新增独立用户问题集 |
| Faithfulness/Answer Coverage 仍主要靠规则近似 | 阶段 6 evaluation plan | 阶段 11 新增人工审阅抽样和 LLM-as-judge 离线设计 |
| deterministic vector-only 仍有主题漂移 | 用户问题评测 vector_only 5/10 | 保留为 honest baseline，并在下一阶段考虑更强 rerank 或真实 embedding 校准 |

## Resources

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/evaluation_plan.md`
- `docs/agent_design.md`
- `docs/brain_workflow_design.md`
- `docs/model_provider_evaluation.md`
- `docs/stage11_user_evaluation_plan.md`
- `app/services/retrieval/keyword_search.py`
- `app/services/retrieval/vector_search.py`
- `app/services/retrieval/hybrid_search.py`
- `app/services/brain/workflow.py`
- `scripts/evaluate_chat.py`
- `scripts/evaluate_agent.py`
- `scripts/evaluate_brain_workflow.py`
- `scripts/evaluate_user_questions.py`
- `data/evaluation/keyword_queries.csv`
- `data/evaluation/chat_queries.csv`
- `data/evaluation/agent_queries.csv`
- `data/evaluation/user_questions.csv`
- `data/evaluation/user_question_results.csv`
- `data/evaluation/user_question_review_samples.csv`
