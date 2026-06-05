---
stage: "阶段 1"
phase: "Phase 4"
status: "已完成"
---

# 阶段 1 Phase 4 - Documents API 与关键词检索 API

所属阶段：[[阶段 1 - 本地资料导入与关键词检索]]
所属汇报索引：[[阶段 1 Phase 汇报索引]]

## 1. 本 Phase 目标

让外部请求可以调用导入链路、查看文档、查看 chunks，并执行关键词检索。

## 2. 本 Phase 完成的主要任务

- 新增 `python-multipart` 依赖，支持上传文件。
- 新增 `app/schemas/document.py`。
- 新增 `app/api/documents.py`。
- 实现 `POST /documents/import` 和 `GET /documents`。
- 实现 `GET /documents/{document_id}/chunks`。
- 新增 `app/services/retrieval/keyword_search.py`。
- 新增 `app/schemas/search.py` 和 `app/api/search.py`。
- 实现 `POST /search`。
- 在 `app/main.py` 注册 documents 和 search 路由，并启动时建表。

## 3. 新增/修改了哪些内容

- 修改 `app/main.py`。
- 新增 `tests/test_documents_api.py`。
- 新增 `tests/test_keyword_search.py`。
- 新增 `tests/test_search_api.py`。
- 修改 `pyproject.toml`，显式声明只打包 `app` 包，避免 `data/` 被误识别为顶层包。

## 4. 关键代码或模块说明

- documents API 负责导入资料和列出资料。
- chunk 查看接口用于检查切分结果。
- keyword search service 根据 query 命中 chunk 正文、标题路径和文档标题计算分数。

## 5. 遇到的问题与解决方式

问题：上传文件需要 multipart 支持，默认依赖不一定包含。

解决方式：新增 `python-multipart`，并用 API 测试覆盖上传 Markdown、查询列表和不支持格式返回 400。

## 6. 新词解释

- API：给外部程序调用的接口，例如 `POST /search`。
- schema：请求或响应的数据结构约束。
- multipart：浏览器或客户端上传文件常用的数据格式。
- score：检索分数，用来表示某个 chunk 和问题的相关程度。

## 7. 验证结果

- `python -m pytest`：21 个测试通过。
- 上传 Markdown 后可以通过 `POST /search` 搜到相关 chunk。
- 文档不存在时 chunk 查看接口返回 404。

## 8. 当前遗留问题

- 关键词检索仍是最小实现，需要真实资料校准。
- 尚未导入堆石混凝土真实资料。

## 9. 下一 Phase 要做什么

进入 Phase 5，导入 5 到 10 篇真实堆石混凝土资料并检查检索效果。

## 10. 面试表达

“我把导入和检索通过 FastAPI 暴露出来：POST /documents/import 负责入库，GET /documents 和 GET /documents/{id}/chunks 负责观察数据，POST /search 负责检索。这样阶段 1 不只是内部脚本，而是形成了可被外部系统调用的最小 RAG 数据入口。”
