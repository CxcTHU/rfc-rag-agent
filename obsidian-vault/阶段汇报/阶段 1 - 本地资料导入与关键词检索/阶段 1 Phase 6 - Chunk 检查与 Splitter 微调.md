---
stage: "阶段 1"
phase: "Phase 6"
status: "已完成"
---

# 阶段 1 Phase 6 - Chunk 检查与 Splitter 微调

所属阶段：[[阶段 1 - 本地资料导入与关键词检索]]
所属汇报索引：[[阶段 1 Phase 汇报索引]]

## 1. 本 Phase 目标

直接检查真实资料生成的 chunk，修正可读性差、元信息混入正文和标题路径不准确的问题。

## 2. 本 Phase 完成的主要任务

- 实现 `GET /documents/{document_id}/chunks`。
- 增加按 `document_id` 查询 document 和 chunks 的 repository 方法。
- 增加 chunk 查看响应 schema。
- 检查 10 条真实资料卡生成的 chunk。
- 更新 splitter，跳过 Markdown 资料卡开头的元信息块。
- 优化 chunk 起点，优先从段落、换行或句号等自然边界开始。
- 修正 `heading_path`，改为按 chunk 开始位置计算。
- 重新切分 `data/imports/rfc_seed/` 下的 10 条资料卡。

## 3. 新增/修改了哪些内容

- 修改 `app/db/repositories.py`。
- 修改 `app/schemas/document.py`。
- 修改 `app/api/documents.py`。
- 修改 `app/services/ingestion/splitter.py`。
- 更新 `tests/test_documents_api.py`。
- 更新 `tests/test_ingestion_splitter.py`。

## 4. 关键代码或模块说明

- chunk 查看接口让用户可以直接看到某篇资料被切成了哪些片段。
- splitter 的 metadata skip 逻辑避免把 `source_id`、URL、copyright note 当成知识正文。
- 自然边界切分让 chunk 展示更像人能读懂的一段话。

## 5. 遇到的问题与解决方式

问题：旧 overlap 会让新 chunk 从 URL、英文单词或元信息字段中间开始。

解决方式：调整起点选择逻辑，让 chunk 尽量从自然文本边界开始。

## 6. 新词解释

- 可观测性：系统内部状态能被检查，例如直接查看某篇资料切出的 chunks。
- overlap：相邻 chunk 之间保留的重叠内容，用来减少上下文断裂。
- heading_path：chunk 所属标题路径，例如“施工质量 / 填充密实性”。

## 7. 验证结果

- `python -m pytest tests\test_documents_api.py`：4 个测试通过。
- `python -m pytest tests\test_ingestion_splitter.py -q`：6 个测试通过。
- `python -m pytest`：25 个测试通过。
- 重切后数据库为 10 documents、10 chunks。

## 8. 当前遗留问题

- splitter 对长论文仍需要结合 PDF 实际效果继续观察。
- PDF 特有编码符号尚未专门清洗。

## 9. 下一 Phase 要做什么

进入 Phase 7，支持 PDF 原文解析，并导入开放全文和 CNKI 机构访问全文。

## 10. 面试表达

“我没有把 chunk 切分当成一次性参数问题，而是通过检查真实 chunk 反向调 splitter。修正后，资料卡元信息不再污染正文，chunk 起点更接近自然段落，检索结果也更适合展示和引用。”
