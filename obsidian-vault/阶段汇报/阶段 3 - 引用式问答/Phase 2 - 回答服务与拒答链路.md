---
stage: "阶段 3"
phase: "Phase 2"
status: "已完成"
---

# 阶段 3 Phase 2 - 回答服务与拒答链路

所属阶段：[[阶段 3 - 引用式问答]]
所属汇报索引：[[阶段 3 Phase 汇报索引]]

## 1. 本 Phase 目标

实现引用式问答的核心服务，把检索结果、prompt、模型回答、引用来源和拒答机制串成一条链路。

## 2. 本 Phase 完成的主要任务

- 新增 `app/services/generation/answer_service.py`。
- 支持 keyword、vector 和 hybrid 检索模式选择。
- 将召回 chunk 转成 prompt context。
- 调用 `ChatModelProvider` 生成回答。
- 从回答中提取 citations，并校验 citations 是否来自本次 sources。
- 在资料不足或低置信度时返回拒答。

## 3. 新增/修改了哪些内容

- 新增 `CitationAnswerService`。
- 新增回答结果中的 `answer`、`sources`、`citations`、`refused`、`refusal_reason`、`retrieval_mode`、`model_provider` 和 `model_name`。
- 复用已有关键词检索与向量检索能力。

## 4. 关键代码或模块说明

`CitationAnswerService` 是阶段 3 的核心编排层。它不自己解析文档、不自己生成 embedding，而是调用既有检索服务，拿到 sources 后构造 prompt，再调用模型 provider，最后整理成 API 可以返回的结构。

## 5. 遇到的问题与解决方式

问题是模型可能编造不存在的引用编号。解决方式是后端只接受本次 sources 中存在的编号，无法对应到 sources 的引用不会进入最终 citations。另一个问题是资料不足时不能硬答，因此加入拒答判断。

## 6. 新词解释

- Citation：引用。回答里类似 `[1]` 的编号，必须能对应到真实来源。
- Refusal：拒答。当资料库没有足够依据时，系统主动说明不能回答。
- Hybrid retrieval：混合检索，把关键词检索和向量检索结合起来使用。
- Source：回答依据，包含标题、URL 或文件路径、chunk 内容和分数。

## 7. 验证结果

- `tests/test_answer_service.py` 通过。
- 能返回可追踪 citations。
- 无依据问题能触发拒答。

## 8. 当前遗留问题

回答质量仍依赖召回片段质量和真实模型能力；阶段 3 只完成最小稳定链路，还没有 rerank 和更细的回答忠实度评测。

## 9. 下一 Phase 要做什么

进入 Phase 3，把回答服务暴露成 `POST /chat`，并把问答过程记录到 `qa_logs`。

## 10. 面试表达

“回答服务的核心不是让模型自由发挥，而是先召回资料，再把资料组织成可引用上下文，最后校验引用是否来自本次召回。资料不足时拒答，这能降低幻觉风险，也让回答更适合工程资料检索场景。”
