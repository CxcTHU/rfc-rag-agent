# RFC-DomainReranker Findings

## 关键发现

- 独立 worktree 初始没有 `.env`，默认会落到 `sqlite:///./data/app.sqlite`。该空库没有 `qa_logs` 表，因此 Step 1 脚本已补充表存在性检查，空库时导出空 QA/chunk 文件但不中断。
- 主工作区存在本地 `.env`。为完成真实 provider 采集，已复制到 reranker worktree 的 gitignored `.env`，未打印密钥，未提交。
- 本地 PostgreSQL dev 容器可用，`export_training_pairs.py` 使用该库成功导出训练准备数据。
- Stage A 第一版真实采集可完成 50 条，但 category 记录不足，缺少明确 `crack` 覆盖。已改进 `collect_real_agent_cases.py` 的类别推断和 balanced selection，第二版覆盖 7 个目标类别。
- Windows 控制台对中文源码显示不稳定。collector 中用于分类的中文关键词已改为 Unicode escape，保持文件 ASCII-only，避免后续语法损坏。
- `build_dataset.py` 的 review CSV 需要字段白名单；否则 dataclass 中的 `group_id` 会让 `csv.DictWriter` 报额外字段错误。已修复并测试。

## 当前数据事实

- `real_agent_cases_execute_v2.jsonl`：50 rows，50 completed，0 errors，50 qa_log_written，1 refused。
- 类别覆盖：construction 9、filling 5、hydration_heat 5、mechanics 8、crack 1、case 1、refusal 1，其余 20 条为原始 eval query 未能归类但仍进入补充样本。
- `summary.json`：`qa_log_pairs=976`、`sampled_chunks=5000`、`eval_queries=107`。
- `dataset_summary.json`：`train_rows=2295`、`val_rows=296`、`test_rows=254`、`total_rows=2845`。
- split 泄漏检查：379 个 unique queries，0 leaks。

## 新词和面试说法

- `qa_logs`：项目数据库里的问答日志表，保存问题、答案、检索 chunk id、引用位置和拒答信息。面试可以说：它把线上/本地 Agent 的回答行为转成可监督的 query-document 关系。
- `hard negative`：和正例来自同一文档或相近上下文、但未被引用的负例。面试可以说：它比随机负例更难，能迫使 reranker 学会细粒度区分。
- `easy negative`：来自不同文档的随机或弱相关负例。面试可以说：它帮助模型保持基础相关性边界。
- `query/group split`：按 query 的稳定 hash 分组切分 train/val/test。面试可以说：同一个问题的正负例不会跨集合泄漏，评估更可信。
- `dry-run`：脚本只产出计划或模板数据，不调用真实模型、不写入生产型数据表。面试可以说：这是把成本和副作用显式化的工程保护。
- `--execute --log-answers`：Stage A 的双重授权开关。`--execute` 允许真实 provider 调用，`--log-answers` 允许写入 `qa_logs`；缺一不可。

## 风险和人工核验重点

- 当前 synthetic queries 是 dry-run 模板问题，不代表真实 LLM 合成质量。进入训练前建议先真实生成 300-500 条并抽查。
- `real_agent_cases_execute.jsonl` 是第一版采集，类别覆盖不完整；最终建议以 `real_agent_cases_execute_v2.jsonl` 为人工核验对象。
- 由于真实采集运行过两版，数据库中新增的 `qa_logs` 包含两批 50 条样本；当前 `qa_log_pairs=976` 已包含两批新增引用关系。
- Codex 桌面右上角可能仍显示主工作区/阶段 52 分支，但实际文件操作均在 `G:\Codex\program\rfc-rag-agent-reranker` 执行。提交前需要人工再次确认 workspace 绑定。
