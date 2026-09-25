# 第4集 — 决策、路由与工作流

**画面：** 在动手写代码之前，白板或幻灯片上先摆出四个示例问题——一个使用类
(usage)、一个 bug 类、一个功能类(feature)、一个模棱两可的。

## 学习目标

先判断"这是哪一类问题"，再决定"该怎么回答它"。正是这种分离，让本课程接下来
的部分变得可控：bug 专项处理器(第6集)永远不必反过来问"等等，这其实是个
功能请求吧？"。

## 讲解要点

1. **分类、路由、执行、综合(Classify, route, execute, synthesize)。** 这正
   是整个 capstone 项目遵循的四段式形状：给问题分类(本集)、路由到正确的
   专项处理器和工具(第5集的工具、第6集的循环)、执行那些工具、把证据综合
   成一个 `Answer`(复用第3集的成果)。今天只是孤立地做第一阶段。
2. **确定性工作流 vs. 自由形式的智能体。** `classify()` 并不会让模型自己
   决定回答之后发生什么——是*代码*去查看 `decision.domain`，然后挑选一条
   路径。这就是工作流：一个固定的形状，由 LLM 去填充，而不是一个自由决定
   自己下一步的智能体。这个状态会一直持续到第10集；第11集才是模型第一次
   获得真正的自主空间的地方，即便如此，那也是有边界的。
3. **第二个 schema，而不是一个更大的 schema。** `RouteDecision`
   (`domain`、`rationale`)本来也可以做成"直接用 `Answer`，把 citations
   留空"。这个方案被有意否决了——那样会让 `citations` 和 `confidence`
   谎报路由环节实际产出的内容。一个更窄、更诚实的 schema，胜过一个塞满
   无关字段的共享 schema。
4. **在第二个使用场景上做泛化。** 第3集的
   `parse_answer()`/`complete_structured()` 是写死给 `Answer` 用的。路由器
   需要针对 `RouteDecision` 用上完全相同的"解析-校验-重试"逻辑，所以本集
   一开始就是一次重构：`parse_structured(raw, schema)` /
   `complete_structured(client, messages, schema)`。看看这次的 diff——
   还是那些行，只是参数化了，而且完整的测试套件(全部31个既有测试)在改动
   之后依然原样通过，证明这次重构没有改变任何行为。

## 实现

- [`src/saas_copilot/structured.py`](../../src/saas_copilot/structured.py) ——
  重构：原本只服务于 `Answer` 的函数，变成了 schema 通用的函数。**把这次
  重构单独提交**，和下面的新功能分开，这样"重构"和"功能"才能各自独立地
  被review、被回退。
- [`src/saas_copilot/prompts.py`](../../src/saas_copilot/prompts.py) — `ROUTER_SYSTEM_PROMPT`。
- [`src/saas_copilot/router/`](../../src/saas_copilot/router/) — `RouteDecision`(位于 schema.py)、`classify()`(位于 classify.py)。

## 运行

```bash
pytest tests/unit/test_structured.py tests/unit/test_router.py -v
```

## 失败案例(现场演示)

```pycon
>>> from saas_copilot.llm.fake import FakeLLMClient
>>> from saas_copilot.router import classify
>>> client = FakeLLMClient(response='{"domain": "urgent", "rationale": "sounds important"}')
>>> classify(client, "the export button is broken")
Traceback (most recent call last):
    ...
saas_copilot.structured.MalformedOutputError: no valid RouteDecision after 3 attempts:
JSON did not match the RouteDecision schema: 1 validation error for RouteDecision
domain
  Input should be 'usage', 'bug', 'feature' or 'general' [type=literal_error, input_value='urgent', input_type=str]
    For further information visit https://errors.pydantic.dev/2.13/v/literal_error
```

`"urgent"` 读起来像是一个说得通的 domain——它只是恰好不属于系统其余部分知道
该如何处理的那四个之一。在这里就大声地拒绝它，好过悄悄地把它路由到
`general`，然后不动声色地给出一个更差的答案。

## 练习

`classify()` 每次都要花掉一整次 LLM 调用，哪怕它翻来覆去只会返回那四个
domain 名字之一。加一条快速路径：一个 `KEYWORD_HINTS: dict[str, Domain]`，
收录几个明显的触发词(例如 `"crash"`、`"error"`、`"traceback"` → `bug`)，
一旦精确匹配到子串，就直接返回一个 `rationale="keyword match"` 的
`RouteDecision`，*完全不*调用 LLM。写一条测试，证明这条快速路径会跳过
`client.call_count` 的增加。(这是一次真正的成本/延迟优化，不只是一道
练习题——第15集会测量它实际触发的频率。)

## 下一步

第5集会给 copilot 一些真正可以路由过去的东西：针对 Loopline 的文档、源码、
git 历史、数据库和日志的一组只读工具。
