---
stage: "阶段 3"
phase: "Phase 0"
status: "已完成"
---

# 阶段 3 Phase 0 - 启动与规划校准

所属阶段：[[阶段 3 - 引用式问答]]
所属汇报索引：[[阶段 3 Phase 汇报索引]]

## 1. 本 Phase 目标

确认阶段 3 的起点、开发边界和参考架构，把“引用式问答”拆成可执行的小步骤。

## 2. 本 Phase 完成的主要任务

- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md` 和 `docs/architecture.md`。
- 对比 Quivr 的 RAG pipeline、LLMEndpoint 和 response metadata 思路。
- 使用 Planning with Files 写入阶段 3 的 `task_plan.md`、`findings.md` 和 `progress.md`。
- 明确阶段 3 不做复杂 Agent workflow，优先打通最小稳定 RAG 问答链路。

## 3. 新增/修改了哪些内容

- 更新阶段 3 的规划文件。
- 明确阶段 3 的实现顺序：模型抽象、prompt 构造、回答服务、Chat API、评测测试、文档收尾。

## 4. 关键代码或模块说明

本 Phase 没有新增业务代码，重点是确定工作路线。规划文件负责让后续开发可以恢复上下文，不依赖单次聊天记忆。

## 5. 遇到的问题与解决方式

问题是 Quivr 架构比本项目当前阶段复杂很多，不能直接照搬。解决方式是只借鉴模块边界：模型调用单独封装，prompt 构造单独封装，回答服务负责串联链路。

## 6. 新词解释

- RAG pipeline：从用户问题到检索资料、组织上下文、生成回答、返回来源的完整流程。
- LLMEndpoint：Quivr 中封装模型调用的接口。本项目用 `ChatModelProvider` 承担类似职责。
- Planning with Files：用 `task_plan.md`、`findings.md`、`progress.md` 保存计划、发现和进度。

## 7. 验证结果

- 阶段 3 规划文件完成。
- 阶段 3 范围确认：实现 `POST /chat`、引用来源、拒答机制和 chat 评测。

## 8. 当前遗留问题

尚未实现真实问答链路，只有阶段规划和架构拆分。

## 9. 下一 Phase 要做什么

进入 Phase 1，先实现 `ChatModelProvider` 和 RAG prompt 构造能力。

## 10. 面试表达

“我没有直接把检索结果丢给大模型，而是先按成熟 RAG 项目的思路拆分模块：模型调用、prompt 构造、回答服务和 API 层各自负责一件事。这样后续换模型、改 prompt 或调整检索策略时不会互相牵连。”
