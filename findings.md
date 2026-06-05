# Findings & Decisions

## Requirements
- 用户要求本线程设置并执行阶段 6 goal，持续推进到“检索优化与评测”完整完成。
- 用户要求线程名称为 `阶段6-检索优化与评测`。
- 用户要求先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 用户要求确认阶段 5 已完成并合并，确认 `phase-5-complete` tag 指向阶段 5 最终功能提交，不移动已有阶段 tag。
- 用户要求目标分支为 `codex/phase-6-evaluation`。
- 用户要求正式开发前用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 6 不做 Agent 工具调用、不做复杂 LangGraph workflow、不做登录系统、不做部署优化。
- 阶段 6 核心目标是检索质量、问答质量和评测可复现：评测计划、baseline、错误案例、优化方案、指标对比和文档收尾。
- 用户后续明确：开发过程中先不要写入 Obsidian 小 Phase 汇报；等阶段 6 全部开发工作完成后，再统一按 `obsidian-vault/模板/Phase 汇报模板.md` 补齐每个小 Phase 笔记。
- 用户后续再次明确：对话中也不需要输出完整 Phase 汇报，完整 10 项汇报只放在最终 Obsidian 知识库中。

## Current Project Findings
- 当前主线分支 `main` 已合并阶段 5，HEAD 为 `ae539f5 Revert "docs: add phase 1 phase reports"`。
- 阶段 5 合并提交为 `9456a59 merge phase 5 frontend`。
- `phase-5-complete` tag 指向 `8c885e6cc714cc985933438697a7eb2523b26722`，提交信息为 `feat: complete phase 5 frontend workspace`。
- `phase-5-complete` 是 `main` 的祖先，说明阶段 5 已合并。
- 当前已创建并切换到 `codex/phase-6-evaluation`。
- 切换前工作区有一个 Obsidian 阶段汇报索引本地改动；按规则保留，不回退。
- 旧 `task_plan.md`、`findings.md`、`progress.md` 仍记录阶段 5 工作记忆，Phase 0 已重写为阶段 6 工作记忆。
- 当前项目已有 126 个自动化测试历史通过记录。

## Architecture Findings
- `app/main.py` 使用 `create_app()` 组装 FastAPI 应用，注册 frontend、health、documents、search、chat、sources 路由。
- 当前 RAG 主链路是：source registry -> documents/chunks -> embedding -> retrieval -> prompt -> chat model -> citations -> frontend。
- 阶段 6 主要落在 retrieval/evaluation 层，少量影响 chat retrieve 路径和前端检索入口。
- 后端分层清楚：API、schema、service、db、model provider、frontend。阶段 6 应继续把核心逻辑放在 service 和 scripts，不把评测规则塞到 API 或前端。

## Existing Evaluation Findings
- `scripts/evaluate_keyword_search.py` 读取 `data/evaluation/keyword_queries.csv`，输出 `keyword_results.csv`，当前历史结果为 15/15。
- `scripts/evaluate_vector_search.py` 使用同一批 keyword queries，对比 `keyword_results.csv`，输出 `vector_results.csv`，当前 deterministic embedding 历史结果为 11/15。
- `scripts/evaluate_chat.py` 读取 `chat_queries.csv`，输出 `chat_results.csv`，当前历史结果为 6/6。
- 现有评测以 pass/fail 为主，已经具备 baseline，但缺少统一评测计划、错误案例表、Recall@K/Citation Accuracy/Faithfulness 等指标说明和优化前后对比表。
- deterministic embedding 适合稳定测试，但不能代表真实语义模型效果。
- Phase 1 新增 `docs/evaluation_plan.md`，把 Recall@K、Citation Accuracy、Faithfulness、Answer Coverage、Refusal Quality 映射到现有 CSV 字段和后续错误案例表。
- Phase 1 新增 `tests/test_evaluation_plan.py`，用文档断言保证评测计划覆盖核心指标和关键评测文件。
- Phase 2 复跑 baseline：keyword 15/15，vector 11/15，chat 6/6。
- Phase 2 新增 `scripts/analyze_retrieval_errors.py` 和 `data/evaluation/retrieval_error_cases.csv`。
- 当前错误案例共 4 个，全部为 vector 的 `keyword_only_pass`：`filling_capacity_en`、`mesoscopic_modeling`、`peridynamics`、`construction_management`。
- Phase 4 新增 `scripts/evaluate_hybrid_search.py` 和 `data/evaluation/hybrid_results.csv`。
- Phase 4 评测结果：hybrid 15/15，rescued_vector=4，regressed_keyword=0。
- Phase 4 刷新错误案例表后，4 个 vector 失败的 `after_status` 均为 `fixed_by_hybrid`。
- Phase 4 复跑 chat：6/6，refused=1，citation_failures=0。

## Retrieval Findings
- `KeywordSearchService` 已有领域同义词扩展、标题/heading/content 加权、泛词降权、metadata source 限制和来源均衡。
- `VectorSearchService` 当前只做 query embedding 与 chunk embedding 的余弦相似度排序。
- `CitationAnswerService` 的 `auto` 模式当前先尝试 vector，有结果就直接使用；只有 vector 无结果时才 fallback 到 keyword。
- 因为 vector 当前 11/15 弱于 keyword 15/15，chat 的 `auto` 模式可能在部分问题上过早接受较弱向量结果。
- 阶段 6 的保守优化方向是 hybrid search 或 rerank：合并 keyword 与 vector，再按归一化分数、来源类型、期望可靠性和去重规则排序。
- Phase 3 已实现 `HybridSearchService`：多取 keyword/vector 候选，按 `chunk_id` 去重，对两路分数按各自最大分归一化，以 keyword_weight=0.7、vector_weight=0.3、both_match_bonus=0.15 组合排序。
- Phase 3 新增 `POST /search/hybrid`，不改变既有 `POST /search` 和 `POST /search/vector`。
- Phase 3 新增 chat `retrieval_mode="hybrid"`，但不改变 `auto` 的旧行为，避免阶段 6 中途扰动既有 chat baseline。

## API Contract Findings
- `POST /search` 当前请求字段为 `query`、`top_k`，返回 `SearchResponse`。
- `POST /search/vector` 当前请求字段为 `query`、`top_k`，返回 provider、model_name 和 results。
- `POST /chat` 支持 `retrieval_mode` 为 `auto`、`vector`、`keyword`、`hybrid`。
- `POST /search/hybrid` 返回字段与 vector response 类似：query、top_k、provider、model_name、results。

## Frontend Findings
- Phase 5 只做最小前端接入：`app/frontend/index.html` 的搜索模式新增 `hybrid`，聊天检索模式新增 `hybrid`。
- `app/frontend/static/app.js` 新增 `apiEndpoints.hybridSearch = "/search/hybrid"`，`submitSearch()` 按 `keyword`、`vector`、`hybrid` 选择对应后端入口。
- 前端改动没有调整页面布局和状态模型，仍沿用原有搜索结果渲染函数，因此不会把阶段 6 扩大成前端重构。
- 浏览器 smoke check 确认本地工作台标题为 `RFC RAG 工作台`，搜索模式包含 `keyword`、`vector`、`hybrid`，聊天检索模式包含 `auto`、`hybrid`、`vector`、`keyword`。
- 当前分支服务在 8001 端口验证 `/search/hybrid` 可返回 5 条结果，`filling capacity rock-filled concrete` 的第一条命中为本地全文资料，说明前端入口对应的新后端路由可用。

## Phase 6 Closeout Findings
- 普通项目文档已同步：`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- `AGENT.MD` 的默认下一步已从阶段 6 校准为阶段 7：Agent 化。
- `docs/data_sources.md` 已说明阶段 6 没有新增外部资料来源，`hybrid_results.csv` 和 `retrieval_error_cases.csv` 是评测产物，不是新的来源。
- 最终评测结果稳定：keyword 15/15、vector 11/15、hybrid 15/15、chat 6/6、error cases 4 个均为 `fixed_by_hybrid`、全量测试 141 passed。
- Obsidian 本地知识库已在开发、测试和普通文档完成后统一回填，包含首页、阶段索引、阶段 6 阶段页、阶段汇报索引、Phase 0-6 汇报、评测体系分类和阶段 6 知识点。
- `obsidian-vault/` 被 `.gitignore` 排除，符合 AGENT 中“本地知识库不得提交到 Git”的规则。

## Data Findings
- `data/app.sqlite` 当前历史记录包含 sources=125、documents=136、chunks=997、chunk_embeddings=997。
- `data/evaluation/keyword_queries.csv` 是关键词和向量 baseline 共用评测集。
- `data/evaluation/chat_queries.csv` 是引用式问答评测集。
- `docs/data_sources.md` 的来源治理关系不需要在 Phase 0 改动；阶段 6 如果不新增数据来源，只需阶段收尾时说明数据边界未变。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 阶段 6 先写 `docs/evaluation_plan.md` | 先定义质量标准，再优化，避免凭感觉调参 |
| baseline 复跑后再做优化 | 用当前项目状态确认起点，避免只依赖历史记录 |
| 优先 hybrid search 或轻量 rerank | 复用现有关键词和向量链路，低风险、可解释、容易测试 |
| 不依赖外部模型 key 完成阶段 6 | 本地 deterministic provider 必须仍能完整回归 |
| 保持 `/search` 与 `/search/vector` 兼容 | 阶段 6 不能破坏阶段 1/2/5 已有入口 |
| 新增 `/search/hybrid` 而不是改写 `/search/vector` | 让优化方案有独立入口，保留 baseline 可对比 |
| chat 支持显式 hybrid，但暂不改变 auto | 先评测检索优化，避免自动模式改变导致 chat baseline 含义漂移 |
| 前端只暴露 hybrid 模式，不重构工作台 | 阶段 6 的重点是评测和检索质量；前端只需要让新模式可选、可验证 |
| Obsidian 小 Phase 汇报阶段末统一回填 | 用户明确要求开发过程中不写入、不在对话输出完整 Phase 汇报，全部开发和普通文档完成后再写入知识库 |
| 阶段 7 默认从 Agent 化开始 | 阶段 6 已完成评测闭环，下一步可以把稳定 search/chat/source 能力包装为受控工具 |

## Planned File Changes
| Area | Planned Files |
|------|---------------|
| 评测计划 | `docs/evaluation_plan.md` |
| 检索优化 | `app/services/retrieval/*.py` |
| API/schema | `app/api/search.py`, `app/schemas/search.py` |
| 问答检索模式 | `app/services/generation/answer_service.py`, `app/schemas/chat.py`, `app/api/chat.py` if needed |
| 评测脚本 | `scripts/evaluate_*.py`, possible new scripts |
| 评测数据 | `data/evaluation/*.csv` |
| 测试 | `tests/test_*search*.py`, `tests/test_evaluate_*.py`, `tests/test_chat_api.py` if needed |
| 前端最小更新 | `app/frontend/*` only if new search mode needs UI exposure |
| 文档 | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | 阶段 6 页面、Phase 汇报、首页、阶段索引、分类页和知识点 |

## Term Explanations
| Term | Explanation |
|------|-------------|
| baseline | 优化前的稳定对照成绩，本项目包括 keyword、vector 和 chat 三条评测线 |
| Recall@K | 前 K 条结果能否召回正确资料，阶段 6 可用期望标题/正文/source_type 命中近似计算 |
| Citation Accuracy | 回答引用编号是否有效、是否能对应返回来源、是否命中期望来源 |
| Faithfulness | 回答是否忠实于检索上下文，不把资料中没有的内容说成事实 |
| Answer Coverage | 回答是否覆盖用户问题需要的关键点 |
| Refusal Quality | 该拒答时拒答，不该拒答时不误拒 |
| hybrid search | 混合检索，把关键词和向量召回结果合并、去重、归一化和排序 |
| rerank | 重排，对初步召回结果再次排序 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| 旧 planning 文件仍是阶段 5 内容 | Phase 0 重写为阶段 6 工作记忆 |
| 切换分支前存在一个 Obsidian 索引本地改动 | 保留该改动，避免覆盖用户工作 |
| 评测指标容易写成抽象口号 | Phase 1 将每个指标绑定到当前脚本字段或后续 CSV 字段 |
| 提前写入了 Phase 0-2 Obsidian 汇报 | 根据用户最新口径撤回提前写入内容，改为阶段完成后统一补写 |

## Resources
- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `scripts/evaluate_keyword_search.py`
- `scripts/evaluate_vector_search.py`
- `scripts/evaluate_chat.py`
- `app/services/retrieval/keyword_search.py`
- `app/services/retrieval/vector_search.py`
- `app/services/generation/answer_service.py`
- `app/api/search.py`
- `app/schemas/search.py`
- `data/evaluation/`

## Current Hypotheses
- Hybrid search should improve or at least stabilize deterministic vector weakness by letting keyword matches rescue weak vector results.
- Chat `auto` mode may eventually benefit from hybrid retrieval, but Phase 3 should first implement and evaluate retrieval-level hybrid before changing chat behavior.
- Error case analysis should become the main teaching artifact for explaining “为什么要优化检索”。
- Phase 2 结果强化了 hybrid search 优先级：4 个失败不是 keyword 也失败，而是 vector 单独失败，所以合并 keyword evidence 是最低风险修复方向。
- Phase 4 已验证该假设：hybrid 救回全部 4 个 vector-only 失败，且没有相对 keyword baseline 的退化。
