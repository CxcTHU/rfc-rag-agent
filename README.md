# RFC-RAG-Agent

面向水利工程堆石混凝土技术的文献检索与引用式问答 Agent。

本项目目标是从零搭建一个垂直领域 RAG 系统，逐步实现：

- 公开资料采集与来源管理
- 文档清洗、切分与元数据保存
- embedding 向量化与语义检索
- 基于检索资料的引用式问答
- 国产大模型接入
- 检索与回答质量评测
- 后续 Agent 工具调用与前端界面

## 当前阶段

阶段 0：项目初始化。

当前只建立项目骨架和项目指南，后续第一步实现 FastAPI `GET /health`。

## 新线程说明

任何新线程继续本项目时，先阅读：

1. `AGENT.MD`
2. `docs/progress.md`
3. `docs/architecture.md`
4. `docs/data_sources.md`

## 初始目录

```text
rfc-rag-agent/
  app/
  docs/
  tests/
  AGENT.MD
  README.md
  .env.example
  .gitignore
```

## 项目边界

第一阶段聚焦堆石混凝土，不做全水利知识库。

核心范围：

- 堆石混凝土基本概念
- 材料组成与自密实混凝土
- 施工工艺与质量控制
- 力学性能与耐久性
- 工程案例
- 公开文献和网页资料的引用式问答

## 安全说明

真实 API Key 只允许写入本地 `.env`，不得提交到 GitHub。

