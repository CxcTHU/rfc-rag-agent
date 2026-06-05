# 数据来源登记

本文件用于记录后续采集的堆石混凝土相关资料来源。

## 登记模板

```text
source_id:
标题:
URL:
来源类型:
作者或机构:
发布时间:
访问时间:
是否允许全文保存:
可信度评级:
备注:
```

## 当前状态

已完成阶段 4 source registry 来源治理。

阶段 4 已新增数据库表 `sources`，作为本项目的 source registry。它统一承接：

- `docs/data_sources.md` 中的人读来源登记。
- `data/fulltext_manifest.csv` 中的 PDF manifest。
- `data/source_candidates.csv` 中的公开学术 API 候选。
- `data/metadata/rfc_papers_metadata.csv` 中的题录元数据。
- `data/imports/metadata_corpus/*.md` 中的题录卡片。

当前同步结果：

- 输入来源候选：283 条。
- 写入 `sources` 表：125 条。
- 更新已有来源：132 次。
- 合并重复来源：26 次。
- 状态分布：`candidate=8`、`collected=117`。
- 全文保存权限分布：`institutional_access=2`、`metadata_only=110`、`open_access=10`、`unknown=3`。
- 可信度分布：`high=125`。

阶段 1 第一批试导入资料登记仍保留在下方，作为早期人工来源记录和历史审计依据。

本批资料采用“资料卡”形式导入：保存题录、公开摘要的转述、检索关键词和来源链接，不保存受版权限制的论文全文。

## 已登记来源（阶段 1 试导入）

| source_id | 标题 | 来源类型 | 作者或机构 | 发布时间 | URL | 是否允许全文保存 | 可信度评级 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rfc_seed_001 | 堆石混凝土及堆石混凝土大坝 / Study on rock-fill concrete dam | CNKI 摘要页、论文题录与公开摘要整理 | 金峰, 安雪晖, 石建军, 张楚汉 | 2005 | https://kns.cnki.net/kcms2/article/abstract?v=7jvqSXIa2LXUBdK4dw0XCLkKcRO8rkZ6LMUUPnH8IpFJ2iR8zuGHA1e5WffpBNepiDh_rfta6rS4U4LuO-qJaLhUnh5c-5CkPCagNMPVSAWdW7j2g4YjWYemqq7ziqRMfVTwwnFVvAbh46kqvSqjJUorkuOpi55gjpt5EPsoavCGJgU1GTvfUw==&uniplatform=NZKPT&language=CHS | 否，仅保存转述整理 | 高 | 用户补充确认的堆石混凝土开篇之作；ResearchGate 与行业页面作为辅助线索 |
| rfc_seed_002 | 堆石混凝土大坝施工方法 | 专利题录与公开资料整理 | 金峰, 安雪晖 | 2003 | https://www.civil.tsinghua.edu.cn/heen/info/1159/1950.htm | 否，仅保存转述整理 | 高 | 金峰教授主页列出的 RFC 施工方法专利 |
| rfc_seed_003 | 自密实混凝土充填堆石体试验研究 | 论文题录与引用线索整理 | 安雪晖, 金峰, 石建军 | 2005 | https://cjxy.usc.edu.cn/info/2369/1623.htm | 否，仅保存转述整理 | 中高 | 通过作者主页论文列表和相关引用页确认 |
| rfc_seed_004 | 自密实堆石混凝土力学性能的试验研究 | 公开摘要整理 | 石建军, 张志恒, 金峰, 张楚汉 | 2007 | https://rockmech.whrsm.ac.cn/CN/abstract/abstract25492.shtml | 否，仅保存转述整理 | 高 | 期刊官网摘要页 |
| rfc_seed_005 | Rock-filled concrete, the new norm of SCC in hydraulic engineering in China | 论文题录与摘要整理 | Xuehui An, Qiong Wu, Feng Jin 等 | 2014 | https://www.sciencedirect.com/science/article/pii/S0958946514001413 | 否，仅保存转述整理 | 高 | Cement and Concrete Composites 论文页 |
| rfc_seed_006 | Experimental study of filling capacity of self-compacting concrete and its influence on the properties of rock-filled concrete | 论文题录与摘要整理 | Yuetao Xie, David J. Corr, Mohend Chaouche, Feng Jin, Surendra P. Shah | 2014 | https://www.scholars.northwestern.edu/en/publications/experimental-study-of-filling-capacity-of-self-compacting-concret | 否，仅保存转述整理 | 高 | Northwestern Scholars 题录页 |
| rfc_seed_007 | Lattice Boltzmann-Discrete Element Modeling Simulation of SCC Flowing Process for Rock-Filled Concrete | 开放获取论文整理 | Song-Gui Chen, Chuan-Hu Zhang, Feng Jin 等 | 2019 | https://www.mdpi.com/1996-1944/12/19/3128 | 可开放访问，本项目仍只保存转述整理 | 高 | MDPI Materials 开放论文 |
| rfc_seed_008 | A Brief Review of Rock-Filled Concrete Dams and Prospects for Next-Generation Concrete Dam Construction Technology | 开放获取综述整理 | Feng Jin, Duruo Huang, Michel Lino, Hu Zhou | 2023 | https://www.engineering.org.cn/engi/CN/PDF/10.1016/j.eng.2023.09.020 | 可开放访问，本项目仍只保存转述整理 | 高 | Engineering 开放综述 |
| rfc_seed_009 | Filling the gaps in large concrete dams | 高校公开网页整理 | Tsinghua University | 2021 | https://www.tsinghua.edu.cn/en/info/1418/10419.htm | 否，仅保存转述整理 | 中高 | 清华大学英文新闻/特写 |
| rfc_seed_010 | 堆石混凝土绝热温升性能初步研究 | 论文题录与公开摘要整理 | 金峰, 李乐, 周虎, 安雪晖 | 2008 | https://sjwj.cbpt.cnki.net/portal/journal/portal/client/paper/65e4dbdb69e5e0bc75cdedaf22704c3e | 否，仅保存转述整理 | 高 | 覆盖水化热、温控和抗裂主题 |

## 后续补充方向

- 增加更多工程应用案例资料，覆盖不同坝型和施工场景。
- 增加规范、规程或行业标准的公开目录信息，但不保存受版权限制全文。
- 对每条资料补充主题标签，例如概念、施工、质量控制、温控、力学性能、工程应用。

## 全文来源目录

阶段 1 已开始从资料卡扩展到论文原文导入。全文 PDF 的来源分类、访问权限和本地文件名见：

- `docs/source_catalog.md`
- `data/fulltext_manifest.csv`

全文 PDF 保存在 `data/fulltext/`，该目录已加入 `.gitignore`，用于本地私有资料库，不提交到 GitHub。

## 题录元数据来源目录

阶段 1 已新增题录优先语料库，用于在不下载更多全文的情况下扩大检索覆盖面。

当前题录文件：
- `data/metadata/rfc_papers_metadata.csv`
- `data/metadata/rfc_papers_metadata.jsonl`
- `data/imports/metadata_corpus/*.md`

当前来源：
- OpenAlex
- Crossref
- 后续可合并 Semantic Scholar、CNKI 导出、Google Scholar 辅助工具导出、Zotero/EndNote/RIS 导出

当前规模：
- 116 条题录记录。
- 69 条包含公开摘要。
- 115 条已作为 `metadata_record` 文档进入 SQLite 检索库。

合规说明：
- 题录语料只保存公开元数据和摘要，不保存未授权全文。
- Google Scholar 不作为直接网页爬取主链路；如需使用，优先通过可导出的题录文件进入本项目。
- CNKI 机构账号获取的内容优先走题录导出或本地私有导入，不公开再分发全文。

## Source Registry 关系说明

阶段 4 之后，来源治理以 `sources` 表为准，文档关系如下：

```text
docs/data_sources.md
  人读来源说明和合规边界

data/fulltext_manifest.csv
  PDF 全文清单，包含本地路径和访问权限

data/source_candidates.csv
  学术 API 发现的候选来源

data/metadata/rfc_papers_metadata.csv
  题录 CSV，适合批量导入和评测

data/imports/metadata_corpus/*.md
  题录 Markdown 卡片，可进入 documents/chunks

sources
  数据库来源登记库，统一保存来源元数据、去重键、权限、可信度、状态和 document 关联

documents/chunks
  已导入并可检索、可引用的内容库
```

同步入口：

```powershell
python scripts/sync_sources.py
```

来源评测入口：

```powershell
python scripts/evaluate_sources.py
```

重新索引入口：

```text
POST /sources/{source_id}/reindex
```

设计原则：

- `sources` 管“这条资料来源是什么、是否可信、能否保存、是否已导入”。
- `documents/chunks` 管“这条资料实际进入 RAG 检索后的正文和片段”。
- `fulltext_permission` 与 `trust_level` 分开记录，避免把版权/授权问题和来源质量混在一起。
- 对受限全文，保留题录、摘要、合法来源链接和本地授权路径，不公开分发全文。
