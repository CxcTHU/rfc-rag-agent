# 阶段 18 之后增量：中文全文语料扩充与拒答边界校准

> 本文件记录在 `claude/phase-18-corpus-evaluation-quality` 分支、阶段 18 主体完成之后，
> 由用户驱动追加的一段工作。是否将其单列为新阶段（如 `phase-19`）或并入阶段 18，
> 由用户人工核验时决定；当前**未提交、未打 tag、未推送**。

## 背景

用户合法下载了约 324 篇堆石混凝土相关中文文献（`G:\Codex\program\papers_NEW`），
要求载入语料库供 reading agent 做后续分析。这把语料从阶段 18 的“深度全文约 16 篇 +
115 篇仅题录”推进到真正的中文全文规模。

## 做了什么

### 1. 中文全文批量导入

- 新增 `scripts/import_papers_corpus.py`：扫描目录中的 PDF，逐文件容错（单篇坏 PDF 不中断整批）、
  `content_hash` 去重、进度与失败汇总；标题取文件名，`source_type=institutional_access_pdf`。
- 文件构成：322 PDF + 2 真 CAJ。
- 加密处理：约 55 篇是 AES 加密 PDF（知网常见），新增依赖 `cryptography>=3.1`（`pyproject.toml`），
  pypdf 即可解密读取。
- **诚实结果**：322 篇中**入库 298 篇**；未入库 24 篇 = 8 篇扫描件（无文字层，需 OCR）+
  16 篇文件损坏/无有效文字。按用户决定，这 24 篇**放弃**，不做 OCR/修复。

### 2. PDF 解析（中文）

- 复用阶段 18 的 `app/services/ingestion/pdf_text.py`（标题层级、表格、断词、去噪）。
- 其中文章节识别（摘要/关键词/结论/参考文献/“一、引言”/“（三）结论”等）此前已就绪，
  对中文 PDF 有效；正文核心术语“堆石混凝土”在多数 chunk 中完整保留（少量页眉/标题有
  逐字空格，属 PDF 抽取常态，不影响关键词命中）。

### 3. 向量索引（确定性 + 真实 Jina）

- 语料：documents **465**、chunks **8918**、深度全文（institutional+open_access）**约 340 篇**。
- 确定性索引（离线回归用）已全覆盖 8918。
- 真实 Jina 语义索引（中文语义检索用）已全覆盖 8918；为遵守 Jina 100k tokens/分钟限额，
  给 `VectorIndexService.build_index` 新增 `sleep_seconds`（批间限速）与 `max_retries`
  （瞬断/限流退避重试），并在 `scripts/build_vector_index.py` 暴露 `--sleep-seconds`、`--max-retries`。
  以 `--batch-size 16 --sleep-seconds 10 --max-retries 5` 限速跑通，幂等可续。

### 4. 中文全文问答验收

- 新增 `data/evaluation/cn_fulltext_queries.csv` + `cn_fulltext_results.csv`：用真实 MIMO+Jina
  跑 8 题（概念/填充/界面ITZ/尺寸效应/温控/对比 + 2 题需拒答）。
- 结论：可答题给出**忠实、带引用**的中文回答，引用可溯源到具体中文论文（含学位论文）；
  对比题在缺资料时诚实声明不硬编；off-topic 不胡编。真实 API 偶发超时（重跑即过）。

### 5. off-topic 拒答边界校准（闭环阶段 18 high 风险）

- 问题根因：`EvidenceConfidence` 把中文按**单字**切词（`EVIDENCE_TOKEN_RE`），off-topic 中文句子的
  常见单字在大段 RFC 证据里偶然命中，覆盖率超过 0.20 阈值 → 误判“有依据”，`refused=False`。
- 修复：在 `app/services/brain/workflow.py` 增加**主题门** `has_topic_anchor(query)` 与
  `CORE_DOMAIN_TERMS` 核心领域词表。只有查询提到本语料核心领域词（堆石混凝土/自密实/混凝土/坝/
  抗压/填充/界面/温控/rock-filled/concrete/dam/itz/seismic… 中英文）时才认为同主题；否则判为
  off-topic 拒答。判据作用在**改写后（含 history）**的查询上，故合法追问不受影响。
- 验证：off-topic **5/5 拒答**（原 1/5）、on-topic **8/8 不误拒**；难评测集 refusal **5/5**（原 1/5）；
  brain 单测全过；全量 **382 passed**。

## 质量门槛变化

- `data/evaluation/stage18_corpus_stats.csv`：deep_fulltext 16 → 340、chunks → 8918、papers_NEW 入库 298。
- `data/evaluation/stage18_quality_summary.csv` / `docs/stage18_quality_report.md` / `/quality-report`：
  refusal_boundary 由 high 闭环为 pass；overall quality gate **review_required/high → review_required/medium**
  （仅余阶段 16 `user_mixed_itz_strength` 的 ITZ Answer Coverage medium carry-forward）。

## 数据安全与合规

- 中文全文是用户**合法下载**的文献；只存本地 DB（`data/app.sqlite`，gitignore）与 `data/raw`（gitignore），
  原始 PDF 不进 Git、不公开分发。
- `cryptography` 仅用于读取用户已合法获取的加密 PDF，不绕任何 DRM/授权。
- 真实 API key / Bearer token / 供应商原始响应不写入代码、CSV、文档、测试或 Obsidian。
- deterministic 索引仍负责离线回归；真实 Jina/MIMO 只作真实检索/分析与发布前校准，不作 CI 前提。

## 如何用 reading agent 分析

`.env` 已配置真实 MIMO+Jina：
```
python -m uvicorn app.main:app   # http://127.0.0.1:8000 工作台
# 或 POST /chat {"question":"...","retrieval_mode":"hybrid","top_k":8}
# 或 POST /agent/query {"question":"...","top_k":8}
```
检索基于 Jina 语义召回 298 篇中文全文，回答带引用溯源；明显无关问题会被拒答。

## 未提交状态

本增量与阶段 18 主体同在 `claude/phase-18-corpus-evaluation-quality` 分支，**尚未 git add/commit/tag/push**，
等待用户人工核验后再决定如何分组提交（建议见交接说明）。
