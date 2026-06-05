---
stage: "阶段 1"
phase: "Phase 0"
status: "已完成"
---

# 阶段 1 Phase 0 - 启动与总体框架

所属阶段：[[阶段 1 - 本地资料导入与关键词检索]]
所属汇报索引：[[阶段 1 Phase 汇报索引]]

## 1. 本 Phase 目标

明确阶段 1 的边界和总体设计：先打通本地资料导入与关键词检索，不接大模型、不接向量库。

## 2. 本 Phase 完成的主要任务

- 创建阶段分支 `codex/phase-1-document-ingestion`。
- 重新确认阶段 1 目标和不做范围。
- 参考 Quivr 的 storage、processor、splitter 模块边界。
- 在 `docs/architecture.md` 中补充阶段 1 总体框架。
- 确定阶段 1 的数据流、目录规划、数据库表、API 草案、关键词检索策略和测试顺序。

## 3. 新增/修改了哪些内容

- 修改 `docs/architecture.md`。
- 在 `docs/progress.md` 记录阶段 1 启动。
- 明确后续模块目录：`app/db/`、`app/services/ingestion/`、`app/services/retrieval/`、`app/api/`、`app/schemas/`。

## 4. 关键代码或模块说明

本 Phase 主要是设计，不直接写业务代码。关键设计是把阶段 1 拆成五层：API 层、schema 层、service 层、repository 层、database 层。

## 5. 遇到的问题与解决方式

问题：RAG 项目容易一开始就跳到大模型和向量库，导致资料链路不稳。

解决方式：阶段 1 先做确定性链路，即文件导入、文本处理、数据库保存和关键词检索。

## 6. 新词解释

- RAG：检索增强生成，先从资料库找依据，再让模型回答。
- Quivr：一个成熟 RAG 项目，本项目只参考它的工程拆分思路，不复制代码。
- 模块边界：每个模块负责什么、不负责什么，例如 parser 只读文本，repository 只管数据库。

## 7. 验证结果

- 阶段 1 总体框架已写入 `docs/architecture.md`。
- 后续 Phase 均按该框架落地。

## 8. 当前遗留问题

- 尚未实现数据库、导入链路、API 和关键词检索。
- 尚未导入真实堆石混凝土资料。

## 9. 下一 Phase 要做什么

进入 Phase 1，建立 SQLAlchemy 数据库层和 `documents/chunks` 最小模型。

## 10. 面试表达

“阶段 1 我没有直接接入大模型，而是先设计本地资料导入和关键词检索链路。这样可以先证明资料能被结构化保存、切分、检索和评测，再进入后续 embedding 和引用式问答。”
