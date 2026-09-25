# 第7集 — 对话状态与记忆

**画面：** 连续输入的两个问题——"一张工单可以有哪些状态？"，接着是"谁可以
修改这些状态？"——如果没有第一个问题，第二个问题毫无意义。

## 学习目标

第6集中的 `run_agent()` 每次调用都从零开始。现在要给它一个可以记住对话的
地方，同时不假装"记住这次聊天"和"记住这个用户"是同一个问题。

## 讲解要点

1. **上下文(context)、会话状态(session state)与长期记忆——三个不同的
   问题。** *上下文*是实际在一次调用中发送给 LLM 的内容
   (`Session.as_context()`——一个有边界的切片)。*会话状态*是某一次聊天
   目前为止的完整对话(`Session.turns`——它可能比能塞进上下文的内容更长；
   目前还没有任何机制在会话进行中做裁剪，这是一个合理的练习方向)。
   *长期记忆*是那些比对话本身活得更久的事实(`UserMemory`——按 `user_id`
   而不是 `session_id` 建立索引)。把这些都混成一个"记忆"大杂烩，最终会
   导致你无法回答"删除我的聊天记录，是否也会忘记我的角色偏好？"这样的
   问题。
2. **保留策略。** `Session.add_turn()` 在每次追加时都会裁剪到只保留最近
   的 `max_turns` 条记录，而不是作为一个单独的、容易被忘记调度的清理
   任务。无限增长的历史记录，既是一项持续膨胀的成本，也意味着某个人越来越
   多的对话内容毫无理由地滞留在内存中。
3. **删除。** `SessionStore.delete()` 和 `UserMemoryStore.forget_all()`
   是两个含义不同的用户控制项，二者相互独立这一点是通过测试证明的，而不
   仅仅是写在文档字符串里的断言：删除一次对话绝不能抹去用户是谁，而忘记
   长期事实也绝不能删除用户的聊天记录。
4. **现在是内存实现，以后是一个接口。** `SessionStore` 是一个 ABC(抽象
   基类)；`InMemorySessionStore` 是本课程提供的唯一实现，重启后数据就会
   丢失——这正是这里"本地优先的原型"的含义。一个真正的生产部署会在完全
   相同的接口背后换上基于 SQL 或 Redis 的存储；`ask()`、`run_agent()`
   以及它们之上的一切都不需要改变。
5. **路由器也需要历史记录。** 单独一句"谁可以修改这些状态？"是无法路由
   的。`classify()`(第4集)现在也接受 `history=` 参数，和专家步骤一样——
   循环的两个环节都能看到同一份对话，而不仅仅是负责作答的那一半。
6. **一层薄封装，而不是一条新路径。** `ask()` 没有重新实现或放宽
   `run_agent()` 已经强制执行的任何规则——
   `test_ask_does_not_bypass_the_agent_loops_evidence_rule` 证明，即便
   入口点变成了 `ask()` 而不是直接调用 `run_agent()`，`bug` 专家依然
   不能跳过证据要求。

## 实现

- [`src/saas_copilot/memory/session.py`](../../src/saas_copilot/memory/session.py) — `Turn`、`Session`。
- [`src/saas_copilot/memory/store.py`](../../src/saas_copilot/memory/store.py) — `SessionStore`、`InMemorySessionStore`。
- [`src/saas_copilot/memory/user_memory.py`](../../src/saas_copilot/memory/user_memory.py) — `UserMemory`、`UserMemoryStore`、`InMemoryUserMemoryStore`。
- [`src/saas_copilot/memory/orchestration.py`](../../src/saas_copilot/memory/orchestration.py) — `ask()`。
- [`src/saas_copilot/router/classify.py`](../../src/saas_copilot/router/classify.py) / [`src/saas_copilot/agent.py`](../../src/saas_copilot/agent.py) — 现在两者都接受 `history=` 参数。

## 运行

```bash
pytest tests/unit/test_memory_session.py tests/unit/test_memory_user_memory.py \
       tests/unit/test_memory_orchestration.py -v
```

## 现场演示(已验证的真实输出，而非示意性说明)

```pycon
>>> ask(client, registry, store, "demo-session", "what statuses can a ticket have?").answer.answer
'Statuses are open, in_progress, resolved, closed.'
>>> ask(client, registry, store, "demo-session", "who can change them?").answer.answer
'A support_agent or support_lead can change them.'
>>> len(store.get("demo-session").turns)
2
>>> store.delete("demo-session")
>>> store.get("demo-session")
None
```

第二个答案之所以说得通，只是因为路由器和专家都把第一个问题和答案当作
历史记录看到了——如果换一个全新的会话问同样的后续问题，它就没有任何
上下文可以用来解析"它们"指代的是什么。

## 练习

`Session.turns` 对总*大小*没有任何限制——即便在 `max_turns` 的约束下，
也只有第15集的评测(evals)才会注意到，少数几个特别长的回合是否已经超出
了上下文能容纳的范围。请添加一个
`Session.as_context(max_turns=..., max_chars=...)` 限制，优先丢弃最旧的
回合，直到渲染出的上下文能够放得下为止，并编写一个使用若干故意设置得很长
的假回合的测试，证明它确实会进行裁剪。

## 下一步

第8集会让 `search_docs` 和 `read_source` 真正具备优秀的检索能力——分块
(chunking)、嵌入(embeddings)、重排序(reranking)——取代第5集里那种朴素的
词频统计搜索。
