---
stage: "阶段 3"
phase: "Phase 3"
status: "已完成"
---

# 阶段 3 Phase 3 - Chat API 与 QA 日志

所属阶段：[[阶段 3 - 引用式问答]]
所属汇报索引：[[阶段 3 Phase 汇报索引]]

## 1. 本 Phase 目标

把引用式问答服务变成可调用的后端接口，并记录问答日志，方便之后排查和评测。

## 2. 本 Phase 完成的主要任务

- 新增 `app/schemas/chat.py`。
- 新增 `app/api/chat.py`。
- 在 `app/main.py` 注册 chat router。
- 在数据库模型中新增 `QuestionAnswerLog`。
- 在 repository 中新增 QA 日志写入能力。
- 让 `POST /chat` 返回结构化回答、引用、来源和模型信息。

## 3. 新增/修改了哪些内容

- 新增 Chat 请求与响应 schema。
- 新增 `qa_logs` 表。
- 新增 `QuestionAnswerLogRepository`。
- 修改数据库模型和 repository 序列化逻辑。

## 4. 关键代码或模块说明

API 层负责接收用户问题和参数，schema 负责校验输入输出结构，service 负责真正的问答链路，repository 负责把问答日志存进数据库。这样每层职责清楚，后续前端或评测脚本都可以复用同一个接口。

## 5. 遇到的问题与解决方式

问题是 citations、retrieved chunk ids 这类列表数据不适合直接塞进普通字符串字段。解决方式是在 repository 层集中做 int list 序列化和反序列化，避免业务代码到处手写转换。

## 6. 新词解释

- Schema：请求和响应的数据结构约定。本项目用 Pydantic schema 规定 `/chat` 接收什么、返回什么。
- Router：FastAPI 的路由模块，把某一组接口组织在一起。
- QA log：问答日志，记录问题、答案、召回内容、模型和拒答状态。
- Repository：数据库访问层，负责保存和读取数据。

## 7. 验证结果

- `tests/test_chat_api.py` 通过。
- `tests/test_chat_logging.py` 通过。
- `POST /chat` 可以返回结构化回答并写入 QA 日志。

## 8. 当前遗留问题

QA 日志目前主要用于本地排查，还没有管理界面、脱敏策略和长期统计报表。

## 9. 下一 Phase 要做什么

进入 Phase 4，建立 chat 评测集和自动化测试，证明问答链路不是只靠手工演示。

## 10. 面试表达

“我把 `/chat` 做成结构化 API，而不是只返回一段文本。响应里有 answer、citations、sources、refused 和模型信息，前端可以展示引用，评测脚本可以判断质量，日志也能追踪问题来源。”
