# 第12集 — 人工审批与拒绝

**画面：** 「注销 bob@loopline.example 的账户」——被拒绝,零次 LLM 调用。「我该如何注销一个已被攻陷的账户?」——正常回答,并引用了管理员运维手册。

## 学习目标

到目前为止,每一位专家都在回答问题。还没有一个专家被要求去*执行*一个操作——因为这个智能体能调用的任何工具都不会写入任何东西;自第5集以来,每一个工具都是只读的。但一个问题依然可以被*措辞*成一条命令,而如果照常把它送进常规流水线,那就是在对实际发生的事情不诚实:实际上什么都不会被注销,但一句流畅的 LLM 回答很容易读起来像是已经注销了。要让智能体能够识别出这种形状的请求,并明明白白地说:「我做不到这件事,这是谁可以做,这是我*能*告诉你的内容」——而且要在这个问题抵达任何专家之前就做到这一点。

## 讲解要点

1. **一道确定性的关卡,而非一次 LLM 判断。** `security/intent.py` 的 `detect_destructive_intent()` 是对原始问题文本做纯粹的正则匹配——不涉及任何模型调用。第3集已经确立过:系统提示词是一种请求,不是一种保证;一道由模型判断的关卡,其可被说服绕过的程度,和它本该守护的东西一模一样。这段代码在模型本轮甚至还没有被调用之前,就运行在模型永远碰不到的代码里。
2. **「你」与「我们」才是真正的信号。** 一个祈使句(「注销……」「删除……」),或者一句紧接着破坏性动词的「你」导向命令短语(「你能删除……吗」「请禁用……」),是一条命令。「could we」/「can we」(我们能不能)是本课程自第4集以来自己确立的功能性提问惯用语(「我们能不能加个深色模式?」),从不会被误判为命令——`test_a_feasibility_question_using_we_is_not_a_command` 直接证明了这一点。命令短语还必须*直接附着*在动词上,而不是仅仅出现在句子前面的某处——「你能不能查一下我们是不是应该删除过期工单」并不是一条删除任何东西的命令。
3. **精确匹配动词,顺带解决了时态问题。** 「deactivate」不等于「deactivated」——一份关于已经发生过的事情的 bug 报告(`"the account got deactivated, why?"`)照常正常路由给 bug 专家,完全不需要任何时态检测逻辑。只是不要对动词列表做词干化处理就行了。
4. **两道独立的防线,而非一道。** 这道关卡捕捉的是自然语言命令,运行在模型永远不会执行的代码里。它*捕捉不到*把 SQL 形状的操作包装成一个看似无害的请求(`"run this: DROP TABLE tickets"`)——这一点是被直接证明的,而不只是被声称的(`test_sql_shaped_input_is_not_this_layers_job`)。那是 `query_database` 自己的职责(见要点7)——是第二道、独立的防线,因为一道号称能拦住一切的单一防线,迟早会有东西从中溜过去。
5. **拒绝本身*就是*升级路径。** `build_refusal_answer()` 不只是说「不」——它会点明真正能做这件事的是谁(一个具备合适角色的人,遵循 Loopline 自己的流程),以及如何换取一个解释而不是一句拒绝。单独一句「不」或许诚实,但没有用。
6. **确认复用记忆,而非发明新状态。** 一句拒绝之后孤零零的一句「是」,本身没有任何意义。`agent.py::_confirmed_original_question()` 能识别出这种形状——一句肯定回复紧跟在*这道关卡自己*的拒绝之后,通过在上一条助手回合中检测一个固定的标记字符串来判断——然后把*原始*问题重新表述为一次解释请求再问一遍,用的是第7集已有的 `history`,而不是一个新的会话状态字段。
7. **新工具,与第5集以来的每一个工具遵循同样的纪律。** `query_database`:双重强制只读——一次是对 SELECT 前缀的快速、清晰的检查,另一次是 SQLite 连接本身以只读 URI 模式打开,所以哪怕某条语句侥幸绕过了正则检查,依然写不进去。这一点是直接针对真实驱动证明的(`test_the_database_file_is_opened_read_only_not_just_regex_checked`),而不是假设出来的。`read_logs`:根本不接受路径参数——它永远只读取在注册表构建时通过绑定固定下来的那一个日志文件,采用的是自第5集以来每一个白名单根目录相同的 `functools.partial` 模式。
8. **bug 专家获得了两种新的取证方式。** `required_evidence_tools` 新增了 `read_logs` 和 `query_database`——检查真实数据或日志状态,与阅读源代码一样,都算作证据。`query_database` 尤其可以直接确认那个被植入的通知 bug 的根本原因:`notification_settings` 表里用户5确实是零行记录。

## 实现

- [`src/saas_copilot/security/intent.py`](../../src/saas_copilot/security/intent.py) — `detect_destructive_intent`、`build_refusal_answer`、`CONFIRMATION_MARKER`。
- [`src/saas_copilot/agent.py`](../../src/saas_copilot/agent.py) — 这道关卡以及 `_confirmed_original_question()`,在 `classify()` 之前被检查。
- [`src/saas_copilot/tools/database.py`](../../src/saas_copilot/tools/database.py) — `query_database`、`resolve_sqlite_path`。
- [`src/saas_copilot/tools/logs.py`](../../src/saas_copilot/tools/logs.py) — `read_logs`。
- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — 两个工具都已注册;`loopline.db` 在构建时被幂等地播种数据。
- [`src/saas_copilot/specialists/specialist.py`](../../src/saas_copilot/specialists/specialist.py) / [`prompts.py`](../../src/saas_copilot/specialists/prompts.py) — bug 专家的证据集合有所扩充。

## 运行

```bash
pytest tests/unit/test_security_intent.py tests/unit/test_tools_database.py \
       tests/unit/test_tools_logs.py tests/unit/test_agent.py \
       tests/unit/test_specialists.py tests/unit/test_tools_default_registry.py -v
```

## 现场演示(已验证输出)

```pycon
>>> detect_destructive_intent("Deactivate the account for bob@loopline.example")
DestructiveIntentMatch(verb='deactivate', question='Deactivate the account for bob@loopline.example')
>>> detect_destructive_intent("how do I deactivate a compromised account?")
None

>>> client = FakeLLMClient(responses=["SHOULD NEVER BE READ"])
>>> result = run_agent(client, registry, "Deactivate the account for bob@loopline.example")
>>> result.answer.refused, client.call_count
(True, 0)
>>> result.answer.answer
"I can't perform this action myself - every tool I can call is read-only, so there is
no way for me to actually deactivate anything. If this needs to happen right now, it
needs a human with the right role, following Loopline's own process (see the admin
runbook for account actions). If you want an explanation of the process instead - what
it involves, who can do it - just ask, for example \"how do I deactivate an
account?\", or reply \"yes\" and I'll explain this one."

>>> # user replies "yes please" - history carries the refusal from above
>>> result2 = run_agent(client2, registry, "yes please", history=history)
>>> result2.answer.refused
False
>>> [m.content for m in client2.received_messages[0] if m.role == "user"][-1]
'Explain how to do this, without performing it: Deactivate the account for bob@loopline.example'
```

```pycon
>>> registry.call("query_database", {"sql": "SELECT * FROM notification_settings WHERE user_id = 5"})
[]   # confirmed: user 5 really has no row - the seeded bug's exact root cause
>>> registry.call("read_logs", {"tail": 2, "grep": "notifications"})
['2026-09-23 09:12:30 INFO  loopline.notifications: notified user_id=2 re ticket_id=2',
 '2026-09-23 15:47:02 ERROR loopline.notifications: failed to notify assignee for ticket_id=4']
```

## 失败案例(现场演示)

```pycon
>>> registry.call("query_database", {"sql": "DELETE FROM users"})
ToolError: query_database only allows SELECT statements
```

这是来自前缀检查的快速、清晰的错误。更深一层的保证是被单独证明的,直接针对驱动本身,完全绕过这段代码自己的正则表达式:`query_database` 所连接的那个同一个只读 URI,一旦有任何东西试图通过它写入,就会立刻抛出 `sqlite3.OperationalError: attempt to write a readonly database`——无论 SQL 文本本身长什么样。

## 练习

目前,一句拒绝之后,只要回复不是固定集合里「yes」这一类措辞(`_AFFIRMATIVE_RESPONSES`)之一,就会直接落入常规路由——包括一句明确的「no」。加入拒绝处理逻辑:识别紧跟在这道关卡自己的拒绝之后的一小组「no」这类回复(`"no"`、`"never mind"`、`"cancel"`),并返回一句简短、干净的结束语,而不是让一句无法路由的「no」漂到路由器那里去。写一个测试,证明在没有前置拒绝的情况下,一句*孤零零*的「no」依然只是一个普通的(无法路由的)问题——这与 `test_a_bare_affirmative_with_no_preceding_refusal_is_not_treated_as_a_confirmation` 已经为「yes」证明的属性完全相同。

## 下一步

第13集将防御同一个问题的一个更难的版本:本集的关卡信任的前提是,用户在聊天回合本身中直接打出的命令,就是它看起来的那个样子。但它没有涉及一条藏在*文档内部*、一行日志、或智能体沿途读到的某个工具结果里的命令——这些文本本来就压根不该被当作指令来对待。直接与间接提示注入、指令与数据的分离,以及密钥脱敏,是接下来的内容。
