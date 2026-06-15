# 阶段 37 设计：Tool Calling Loop 并行迁移与 ReAct 对照评估

## 目标与基线

阶段 37 从阶段 36 已完成并合并后的主线出发：

```text
phase-36-complete -> 9516b22
main / origin/main -> d747169
Stage 30 = 91.52 / A / pass
```

本阶段新增并行 `mode="tool_calling_agent"`，不删除、不替换 `react_agent`，不自动切默认。目标不是只给 provider 加一次 `tools` 参数，而是实现一个轻量 tool-calling loop。

现有 ReAct 典型链路：

```text
planner LLM -> 检索工具 -> planner LLM -> answer LLM
planner LLM -> 妫€绱㈠伐鍏?-> planner LLM -> answer LLM
```

目标 tool-calling loop：

```text
LLM(messages, tools)
-> 如果返回 tool_calls：执行只读工具，脱敏/截断 tool result，以 role="tool" 回灌 messages，继续 loop
-> 如果返回 content：校验引用并结束
-> 如果重复 query、工具错误或达到 max_iterations：安全拒答或基于已有证据收敛
```

## Loop 语义

tool-calling 是模型用标准结构表达“我要调用工具”的协议；loop 是外层 Agent 控制结构。也保留测试锁定表述：tool-calling 鏄ā鍨嬬敤鏍囧噯缁撴瀯琛ㄨ揪鈥滄垜瑕佽皟鐢ㄥ伐鍏封€濈殑鍗忚；loop 鏄灞?Agent 鎺у埗缁撴瀯。

阶段 37 必须实现 tool-calling loop；蹇呴』瀹炵幇 tool-calling loop；不是只给 provider 加一次 `tools` 参数；涓嶆槸鍙粰 provider 鍔犱竴娆?`tools` 鍙傛暟。loop 必须支持多次 tool_calls、澶氭 tool_calls、max_iterations、重复 query 必须拦截、閲嶅 query 蹇呴』鎷︽埅、工具错误必须收敛、宸ュ叿閿欒蹇呴』鏀舵暃。

## Provider 协议

Chat provider 层新增 OpenAI-compatible `tools` 支持、`tool_calls` 结构化解析、`role="tool"` 消息回灌；测试锁定短语：`tool_calls` 缁撴瀯鍖栬В鏋?，`role="tool"` 娑堟伅鍥炵亴。

deterministic provider 离线模拟单轮 tool_call、多轮 tool_call 和最终 answer；deterministic provider 绂荤嚎妯℃嫙鍗曡疆 tool_call銆佸杞?tool_call 鍜屾渶缁?answer。旧 `generate()` 与 `stream_generate()` 行为保持兼容；鏃?`generate()` 涓?`stream_generate()` 琛屼负淇濇寔鍏煎。provider 只返回结构化安全字段，不保存 raw provider response；涓嶄繚瀛?raw provider response。

## Agent 边界

阶段 37 只新增并行 service，不改默认链路：

- 不引入 LangGraph；涓嶅紩鍏?LangGraph
- 不删除、不替换 `react_agent`；涓嶅垹闄ゃ€佷笉鏇挎崲 `react_agent`
- 不自动切默认；涓嶈嚜鍔ㄥ垏榛樿
- 不替换默认 chat provider；涓嶆浛鎹㈤粯璁?chat provider
- 不替换默认 embedding provider；涓嶆浛鎹㈤粯璁?embedding provider
- 不替换默认 rerank provider；涓嶆浛鎹㈤粯璁?rerank provider
- 不动 provider 拓扑；涓嶅姩 provider 鎷撴墤
- 不改 Stage 30 评分权重；涓嶆敼 Stage 30 璇勫垎鏉冮噸
- 不新增外部数据源；涓嶆柊澧炲閮ㄦ暟鎹簮
- 不接 `citation_validator`；涓嶆帴 `citation_validator`
- 不做多用户隔离；涓嶅仛澶氱敤鎴烽殧绂?
- 不做写入型 Agent 工具；涓嶅仛鍐欏叆鍨?Agent 宸ュ叿

## 工具与安全

第一版只暴露只读 `search_knowledge` / `hybrid_search_knowledge`；鍙毚闇插彧璇?`search_knowledge` / `hybrid_search_knowledge`。tool result 回灌给模型时必须只包含必要的脱敏结构化摘要；tool result 鍥炵亴缁欐ā鍨嬫椂蹇呴』鍙寘鍚繀瑕佺殑鑴辨晱缁撴瀯鍖栨憳瑕?

不暴露完整 chunk 全文；不得暴露完整 chunk 全文、内部规则、raw provider response、reasoning_content、hidden thought、API key、Bearer token、Authorization header 或受限全文。测试锁定短语：涓嶆毚闇插畬鏁?chunk 鍏ㄦ枃、鍐呴儴瑙勫垯、鍙楅檺鍏ㄦ枃。

最终答案引用必须来自 tool result / sources。若真实模型给出内容但缺少有效 `[N]` 引用，记录为 `missing_tool_backed_citations` 并安全收敛。

## 对照评估

新增 `scripts/evaluate_stage37_tool_calling_vs_react.py`，输出：

```text
stage37_tool_calling_vs_react_results.csv
stage37_tool_calling_vs_react_summary.csv
stage37_tool_calling_vs_react_real_results.csv
stage37_tool_calling_vs_react_real_summary.csv
```

脚本支持 `--execute` real-provider 对照。评估集覆盖单跳定义题、对比题、多维问题、中英术语题、追问题、evidence_insufficient、off-topic 拒答题、多跳检索题；同时保留测试锁定短语：鍗曡烦瀹氫箟棰?、瀵规瘮棰?、澶氱淮闂、涓嫳鏈棰?、杩介棶棰?、off-topic 鎷掔瓟棰?、澶氳烦妫€绱㈤。

对照指标包含 llm_call_count、tool_call_count、iteration_count、time_to_first_token_ms、time_to_final_ms、citation_count、source_count、refused、same_refusal_as_react、same_top_source_as_react、repeated_query_count、error_summary、decision_candidate，并补充 executed/skipped/near-duplicate/citation repair 指标。

## Tiered Provider 取舍

阶段 34 的 ReAct 可用 Flash planner + V4-Pro answer。tool_calling_agent 的 `LLM(messages, tools)` 同时承担规划和最终回答，因此第一版必须选择一个 tools-capable model。这个 tiered provider 取舍是阶段 37 的核心风险之一：Flash 可能更快但回答质量弱，V4-Pro 可能更稳但每次 tool_call 都更慢。

## 验证结果

```text
python -m pytest -q -> 758 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/evaluate_stage37_tool_calling_vs_react.py -> react_agent errors=0; tool_calling_agent errors=0
tool_calling_agent same_refusal_as_react=8/8; same_top_source_as_react=6/8
python scripts/evaluate_stage37_tool_calling_vs_react.py --execute --limit 8 -> react_agent errors=0, same_refusal=8/8, same_top_source=8/8; tool_calling_agent errors=0, same_refusal=8/8, same_top_source=7/8
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120 -> rows=9 execute=true failed=0
```

`scripts/run_production_smoke.py` 已覆盖 `tool_calling_agent` 普通与 SSE 路径。浏览器 smoke：桌面 + 390x844 移动端；娴忚鍣?smoke锛氭闈?+ 390x844 绉诲姩绔?。验收确认无横向溢出，console errors=0。

## 裁定草稿

阶段 37 建议保留 `tool_calling_agent` 为并行评审模式。它已经接近主流 tool runtime：校验 tool name/input、执行或跳过、每个 tool_call_id 都回灌 role="tool"、只把脱敏 transcript 交给下一轮模型。真实对照显示 latency 有明显收益，但仍有 1 条首源不一致，且 tiered provider 取舍未解决，因此不自动切默认。
