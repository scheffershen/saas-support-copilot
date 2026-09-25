# 第6集 — 智能体循环

**画面：** 白板上的一张循环图——问题 → 路由 → (调用工具 ⟲) → 答案——在写
任何代码之前先画出来，然后据此构建。

## 学习目标

从第3集开始，到目前为止一直都是一次一次的单个 LLM 调用。本集要把它们
连接成一个真正由模型驱动的循环：`router.classify()` 选定一个领域，
`specialists.get_specialist()` 说明该领域需要哪些证据，而模型则一步一步
地自行决定，是调用工具，还是给出答案。

## 讲解要点

1. **观察 → 决策 → 行动 → 观察。** 每一轮迭代：模型*决策*(`AgentStep`)，
   如果它选择了工具，循环就负责*行动*(`registry.call()`)，而结果会成为
   模型在下一轮*观察*到的下一条观察信息
   (`Message(role="user", content="Tool result: ...")`)。`run_agent()`
   就是围绕这个循环写的一个普通 `for` 循环——没有用任何框架，因为这里没有
   什么是一个 `for` 循环表达不清楚的。
2. **状态转换。** 只有两种状态：`call_tool` 和 `final_answer`。
   `AgentStep` 的 `model_validator` 让无效的组合(例如
   `action="call_tool"` 却没有 `tool_call`)根本无法被表示出来，这与第3集
   中 `Answer` 的 refused/citations 规则遵循的是同一套原则。
3. **最大步数。** 用的是 `for step_number in range(1, max_steps + 1)`，
   而不是 `while True`。一个理论上可以永远运行下去的循环，需要的是一个
   "*被允许*继续运行"的理由，而不是一个"它最终会停下来"的理由。
4. **重复调用防护。** `seen_calls` 会追踪 `(tool, sorted-json-arguments)`
   这样的键值对。同一个调用被执行两次，说明模型并没有利用新信息取得
   进展——`RepeatedToolCallError` 会明确指出这一点，而不是白白再烧掉五个
   一模一样的步骤。
5. **工具错误。** `registry.call()` 抛出的 `ToolError` 不会让循环崩
   溃——它会变成下一条观察信息 `"Tool error: ..."`，模型可以借此尝试别的
   做法。`test_loop_continues_after_a_tool_error_instead_of_crashing`
   证明了即便第一次尝试失败，最终依然能得到一个真正的答案。
6. **证据规则是有牙齿的。** `bug`/`feature` 专家(对应第5集中的
   `required_evidence_tools`)如果没有先**成功**调用过所需工具之一，就
   不能 `final_answer`——而且*失败*的调用不算数
   (`test_a_failed_tool_call_does_not_count_as_evidence`)。"我试着查了，
   但报错了"同样不算证据。
7. **取消机制。** `cancel_token: threading.Event` 会在路由调用之前、以及
   每一步之前被检查——一次预先取消的运行不会做任何工作，而不是"先浪费
   一次调用才发现"。第14集会把一个真实请求的断开连接接入这里。
8. **`complete_structured()` 的第三种用法。** `Answer`(第3集)、
   `RouteDecision`(第4集)，现在又加上 `AgentStep`。同一套通用的"解析、
   校验、重试"机制被用在了三个真实的调用点上，没有重复的重试逻辑。
9. **提示词是生成出来的，不是手写的。** `_initial_messages()` 会根据
   `registry.specs()` 构建工具菜单——以后再加入第七个工具，模型的提示词
   也会自动知晓；不存在第二个需要记得同步更新的地方。

## 实现

- [`src/saas_copilot/agent.py`](../../src/saas_copilot/agent.py) — `AgentStep`、`ToolCall`、四个 `AgentError` 子类、`run_agent()`、`AgentRunResult`。

## 运行

```bash
pytest tests/unit/test_agent.py -v
```

每个测试都是在这个仓库中*真实*的 `sample_app/loopline/` 上运行*真实*的
工具注册表(`build_default_registry`)——唯一被预先编排好的只是 LLM 的
响应内容。当 "bug" 场景测试通过时，`search_code` 是真的针对
`notifications.py` 运行过的。

## 失败案例(现场演示)

```pycon
>>> # bug specialist tries to answer immediately, no tool call first
>>> run_agent(client, registry, "why does commenting on ticket 4 crash?")
MissingEvidenceError: bug specialist tried to answer without calling one of ['git_log', 'git_show', 'read_source', 'search_code'] first
```

模型给出的回答文本——"大概是因为缺少空值检查而崩溃"——听起来甚至相当有
道理。这正是为什么这一点不能只是一条建议：一个自信的猜测和一个有据可查的
事实，在文字上读起来几乎别无二致。

## 练习

目前没有任何机制阻止 `final_answer` 里的 `answer.domain` 与产生它的
专家自相矛盾——一个 `bug` 专家完全可以返回 `answer.domain="feature"`，
而 `run_agent()` 根本不会察觉。请在 `final_answer` 分支中添加一个检查，
当两者不一致时抛出一个新的 `AgentError` 子类(`DomainMismatchError`)，
并编写一个测试证明不匹配的领域会被拒绝。

## 下一步

第7集将加入记忆机制：目前每一次 `run_agent()` 调用都是从零开始的。
