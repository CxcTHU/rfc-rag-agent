---
stage: "阶段 1"
phase: "Phase 1"
status: "已完成"
---

# 阶段 1 Phase 1 - 数据库模型与最小测试

所属阶段：[[阶段 1 - 本地资料导入与关键词检索]]
所属汇报索引：[[阶段 1 Phase 汇报索引]]

## 1. 本 Phase 目标

建立资料库的最小数据库结构，让一篇资料和它切出来的 chunk 可以被保存和查询。

## 2. 本 Phase 完成的主要任务

- 增加 `SQLAlchemy` 依赖。
- 新增 `app/db/session.py`，集中管理数据库连接和会话。
- 新增 `app/db/models.py`，定义 `documents` 和 `chunks` 两张表。
- 新增 `tests/test_db_models.py`，验证建表、保存 document 和保存 chunk。

## 3. 新增/修改了哪些内容

- 修改 `pyproject.toml`。
- 新增 `app/db/__init__.py`。
- 新增 `app/db/session.py`。
- 新增 `app/db/models.py`。
- 新增 `tests/test_db_models.py`。

## 4. 关键代码或模块说明

- `documents` 表保存资料级信息，例如标题、来源路径、文件名、hash 和来源类型。
- `chunks` 表保存资料片段，例如 chunk 编号、正文、标题路径、字符范围和字数。
- `session.py` 负责创建数据库 engine、session factory 和建表入口。

## 5. 遇到的问题与解决方式

问题：如果直接把资料存在内存或普通文本文件里，后续 API、检索和评测都难以统一读取。

解决方式：用 SQLite + SQLAlchemy 建立最小关系型表结构，先保证本地开发简单可跑。

## 6. 新词解释

- SQLAlchemy：Python 常用数据库工具，用对象方式操作数据库表。
- ORM：对象关系映射，把 Python 类和数据库表对应起来。
- session：一次数据库操作会话，可以理解为“打开数据库办一批事，再提交或回滚”。

## 7. 验证结果

- `tests/test_db_models.py` 通过。
- 数据库可以创建 `documents` 和 `chunks` 表。
- 一篇资料及其 chunk 可以被保存。

## 8. 当前遗留问题

- 只有表结构，还没有文件读取、清洗、切分和完整导入链路。
- 尚未通过 API 暴露给外部调用。

## 9. 下一 Phase 要做什么

进入 Phase 2，实现 parser、cleaner、splitter。

## 10. 面试表达

“我先用 SQLite 和 SQLAlchemy 建立 documents/chunks 两张核心表。documents 管资料级元数据，chunks 管可检索片段。这样后续检索、引用、评测都围绕 chunk 展开，而不是直接处理整篇文件。”
