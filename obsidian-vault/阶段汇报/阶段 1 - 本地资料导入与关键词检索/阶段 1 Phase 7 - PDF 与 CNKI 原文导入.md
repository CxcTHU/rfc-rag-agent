---
stage: "阶段 1"
phase: "Phase 7"
status: "已完成"
---

# 阶段 1 Phase 7 - PDF 与 CNKI 原文导入

所属阶段：[[阶段 1 - 本地资料导入与关键词检索]]
所属汇报索引：[[阶段 1 Phase 汇报索引]]

## 1. 本 Phase 目标

从摘要型资料卡扩展到论文原文，让开放 PDF 和机构授权 PDF 也能进入本地检索库。

## 2. 本 Phase 完成的主要任务

- 新增 `pypdf` 依赖。
- 扩展 parser，支持 `.pdf` 文字层抽取。
- PDF 解析时按页加入 `## Page N` 标记。
- `IngestionService` 支持传入 `source_type`。
- 新增 `data/fulltext_manifest.csv`。
- 新增 `docs/source_catalog.md`。
- 更新 `.gitignore`，忽略 `data/fulltext/`。
- 下载并导入 10 篇开放全文 PDF。
- 使用用户已登录 CNKI 的机构访问，导入《堆石混凝土及堆石混凝土大坝》PDF。

## 3. 新增/修改了哪些内容

- 修改 `app/services/ingestion/parser.py`。
- 修改 `app/services/ingestion/service.py`。
- 修改 `tests/test_ingestion_parser.py`。
- 修改 `tests/test_documents_api.py`。
- 修改 `tests/test_ingestion_service.py`。
- 新增 `data/fulltext_manifest.csv`。
- 新增 `docs/source_catalog.md`。
- 修改 `.gitignore`。

## 4. 关键代码或模块说明

- PDF parser 抽取文字层，并保留页码标记。
- `source_type` 区分 `open_access_pdf`、`institutional_access_pdf`、`local_file` 等来源类型。
- manifest 记录全文来源、许可备注、PDF URL 和本地文件名。

## 5. 遇到的问题与解决方式

问题：CNKI PDF 来自机构账号授权，不能提交或公开分发。

解决方式：只复制到本地 `data/fulltext/cnki_pending/`，并通过 `.gitignore` 避免全文进入 GitHub。

## 6. 新词解释

- PDF 文字层：PDF 中可直接复制/抽取的文字，不是扫描图片。
- manifest：清单文件，用来记录每个 PDF 的来源、路径、许可和备注。
- institutional access：机构授权访问，例如学校或单位购买的数据库权限。

## 7. 验证结果

- 开放 PDF 导入后：20 documents、800 chunks。
- CNKI PDF 导入后：21 documents、811 chunks。
- `python -m pytest tests\test_ingestion_parser.py tests\test_documents_api.py -q`：8 个测试通过。
- `python -m pytest`：27 个测试通过。

## 8. 当前遗留问题

- PDF 解析只支持文字层，不支持扫描版 OCR。
- CNKI PDF 中存在少量编码符号，后续 cleaner 可继续增强。
- 机构授权全文只用于本地私有学习和检索。

## 9. 下一 Phase 要做什么

进入 Phase 8，建设自动化语料扩容管道和题录优先语料库。

## 10. 面试表达

“我把资料来源从手工 Markdown 卡片扩展到 PDF 原文，并用 source_type 和 manifest 记录开放获取与机构访问的边界。这样既能提升检索资料量，又不把版权受限全文提交到远程仓库。”
