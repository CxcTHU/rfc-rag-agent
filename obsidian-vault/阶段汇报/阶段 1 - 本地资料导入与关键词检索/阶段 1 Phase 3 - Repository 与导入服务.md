---
stage: "阶段 1"
phase: "Phase 3"
status: "已完成"
---

# 阶段 1 Phase 3 - Repository 与导入服务

所属阶段：[[阶段 1 - 本地资料导入与关键词检索]]
所属汇报索引：[[阶段 1 Phase 汇报索引]]

## 1. 本 Phase 目标

把文件读取、清洗、切分和数据库保存串成完整导入链路。

## 2. 本 Phase 完成的主要任务

- 新增 `app/db/repositories.py`。
- 新增 `app/services/ingestion/loader.py`。
- 新增 `app/services/ingestion/service.py`。
- 支持计算文件 hash 和保存原始文件。
- 支持重复文件识别，避免重复入库。
- 支持拒绝空文件。
- 新增 repository 和 ingestion service 测试。

## 3. 新增/修改了哪些内容

- 新增 `tests/test_repositories.py`。
- 新增 `tests/test_ingestion_service.py`。
- 新增配置项 `RAW_DATA_DIR`。
- 修改 `.env.example` 和配置读取。

## 4. 关键代码或模块说明

- repository 封装 `documents/chunks` 的数据库读写。
- loader 负责原始文件保存和 hash 计算。
- ingestion service 负责编排 parser、cleaner、splitter、loader 和 repository。

## 5. 遇到的问题与解决方式

问题：如果 API 层直接调用 parser、splitter 和数据库，代码会很快混在一起。

解决方式：用 ingestion service 做业务编排，API 层只负责接收请求和返回响应。

## 6. 新词解释

- repository：数据库仓储层，封装增删改查，让业务代码不用直接写数据库细节。
- service：业务服务层，负责把多个底层模块串成一个完整业务流程。
- hash：文件内容指纹，用来判断两个文件内容是否相同。

## 7. 验证结果

- repository 测试通过。
- ingestion service 测试通过。
- Markdown 文件可以完成导入、切分、保存。
- 重复文件不会重复入库，空文件会被拒绝。

## 8. 当前遗留问题

- 导入链路还没有接到 FastAPI。
- 还没有实现对外的文档列表和搜索接口。

## 9. 下一 Phase 要做什么

进入 Phase 4，实现 documents API、search API 和 chunk 查看接口。

## 10. 面试表达

“我用 repository 隔离数据库读写，用 ingestion service 编排导入流程。这样 API 层很薄，业务规则集中在 service，数据库细节集中在 repository，后续测试和扩展都更清楚。”
