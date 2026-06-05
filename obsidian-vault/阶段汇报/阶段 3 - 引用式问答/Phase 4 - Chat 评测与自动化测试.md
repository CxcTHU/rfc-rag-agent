---
stage: "阶段 3"
phase: "Phase 4"
status: "已完成"
---

# 阶段 3 Phase 4 - Chat 评测与自动化测试

所属阶段：[[阶段 3 - 引用式问答]]
所属汇报索引：[[阶段 3 Phase 汇报索引]]

## 1. 本 Phase 目标

用自动化测试和评测脚本验证引用式问答链路，避免只靠人工提问判断效果。

## 2. 本 Phase 完成的主要任务

- 新增 `data/evaluation/chat_queries.csv`。
- 新增 `scripts/evaluate_chat.py`。
- 生成 `data/evaluation/chat_results.csv`。
- 补充 prompt、model provider、answer service、chat API、QA logging 和评测脚本测试。
- 运行全量测试和 chat 评测。

## 3. 新增/修改了哪些内容

- 新增 6 个阶段 3 相关测试文件。
- 新增 chat 评测问题集，覆盖概念、施工质量、温控、填充性能、工程案例和无依据问题。
- 新增评测结果文件，记录通过情况、引用数量、拒答状态和来源命中情况。

## 4. 关键代码或模块说明

`evaluate_chat.py` 通过统一问题集调用问答服务，检查回答是否返回、拒答是否符合预期、citations 是否有效、来源是否命中预期标题。它让阶段 3 的“能回答”变成可重复验证的指标。

## 5. 遇到的问题与解决方式

问题是生成式回答天然可能不稳定。解决方式是评测默认使用 deterministic provider，先验证链路、引用和拒答规则；真实模型接入后再扩展更细的忠实度评测。

## 6. 新词解释

- Evaluation：评测，用固定问题集检查系统表现。
- Citation failure：引用失败，指回答引用了不存在或无法对应的来源编号。
- Regression test：回归测试，确认新增功能没有破坏已有能力。
- Refusal quality：拒答质量，检查无依据问题是否能正确拒答。

## 7. 验证结果

```text
python -m pytest -q: 106 passed
scripts/evaluate_chat.py: 6/6 passed
citation_failures: 0
```

## 8. 当前遗留问题

Chat 评测集还比较小，后续阶段需要扩大问题数量，并加入更严格的忠实度、覆盖度和错误案例分析。

## 9. 下一 Phase 要做什么

进入 Phase 5，同步 README、docs、AGENT、Obsidian，并完成提交、tag 和 GitHub 上传。

## 10. 面试表达

“我没有只演示几条问答，而是为 chat 链路建了评测集。评测会检查回答、拒答、引用有效性和来源命中，这能把 RAG 问答从 demo 往可验证系统推进。”
