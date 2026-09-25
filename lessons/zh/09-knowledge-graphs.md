# 第9集 — 面向代码关系的知识图谱

**画面：** "能不能让任何人自行认领工单？"这个问题——以及它所依赖的
`services.assign_ticket` 函数，却看不出还有什么地方在调用它。

## 学习目标

文本搜索能回答"这个词出现在哪里"。但它回答不了"修改这个函数会破坏
什么"——这是一个关于*结构*而非*内容*的问题。构建本课程所需的第二种检索
范式：实体及其之间的关系，而不是文档与分块。

## 讲解要点

1. **实体与关系，相对于文档与分块。** 第8集的 `DocumentIndex` 把一切都
   当作待排序的文本。`CallGraph` 则把 Loopline 的函数当作*节点*，把
   "调用"关系当作*边*——这是一种根本不同的问题形态：不是"什么内容与这个
   查询相关"，而是"什么东西与这个事物相连"。
2. **用 `ast` 做静态分析。** 不用正则表达式，也不对 import 语句做字符串
   匹配——`CallGraph` 解析的是真正的 Python 语法树，并按照 Python 自身
   的方式解析调用关系：同模块回退机制，以及针对相对导入使用
   `ast.ImportFrom` 真实的 `level`/`module` 字段(`from .models import X`
   和 `from ..services import Y` 会被正确地解析为不同的结果，因为
   Loopline 的 `routers/` 目录下的文件比顶层模块深一个包层级)。
3. **调用图。** 分两遍处理，而不是一遍：先收集所有节点，然后只有当被
   调用者能解析到一个*已知*节点时，才记录一条边。正是这一点让
   `session.add(...)`、`session.commit()` 和 `@router.post(...)` 装饰器
   调用被正确地排除在图之外，而无需针对 SQLAlchemy 或 FastAPI 做任何按
   名字的特殊处理——它们本来就永远不会匹配到任何一个 Loopline 自定义的
   函数。
4. **结构胜过文本搜索的场景。** `search_code("assign_ticket")` 会找到
   文本 "assign_ticket" 的每一处*出现*——包括出现在文档字符串或注释里
   的字符串。而 `query_graph("services.assign_ticket", "callers")` 则会
   找到每一个真正*调用*它的地方。对于"这次改动会影响到什么"这个问题，
   这个区别就是全部答案。
5. **一个真实存在、被明确说出来的局限性。** 不支持动态派发，不支持通过
   持有函数引用的变量进行调用，也不支持 `self.method()` 的解析。
   Loopline 自身的代码没有用到任何这些写法，因此由它构建出的图对这个
   代码库来说是完全准确的——一个更大、或者更动态的代码库将需要更重量级
   的工具。这一点被直白地说了出来，而不是被含糊带过。
6. **`feature` 专家变得更加敏锐。** `query_graph` 加入了
   `read_source`/`search_code`/`list_files` 的行列，成为它可以收集的
   证据之一，它的提示词现在也会要求在把某项改动称为"独立无关联"之前，
   先检查有哪些调用方。这不仅仅是宣称出来的，而是通过真实的智能体循环
   得到证明：`test_feature_specialist_can_satisfy_evidence_via_query_graph`
   会路由一个可行性问题，真正地调用 `query_graph`，然后给出答案。

## 实现

- [`src/saas_copilot/graph/call_graph.py`](../../src/saas_copilot/graph/call_graph.py) — `CallGraph`、`FunctionNode`。
- [`src/saas_copilot/tools/graph.py`](../../src/saas_copilot/tools/graph.py) — `query_graph` 工具。
- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — 图在注册表启动时构建一次，与第8集的文档索引做法相同。
- [`src/saas_copilot/specialists/`](../../src/saas_copilot/specialists/) — `feature` 的证据集合与提示词已更新。

## 运行

```bash
pytest tests/unit/test_graph_call_graph.py tests/unit/test_tools_graph.py \
       tests/unit/test_specialists.py tests/unit/test_agent.py -v
```

`test_graph_call_graph.py` 中每一条预期的边，都是先实际对 Loopline 的
真实源码运行图构建器、打印出它的输出之后才发现的——其中包括两条依赖
注入的边(`routers.tickets._session` / `routers.users._session` →
`database.get_session`)，这是人工追踪源码时都未曾预料到的。

## 失败案例(现场演示)

```pycon
>>> query_graph("assign_ticket", graph=graph)   # missing the "services." qualifier
ToolError: unknown symbol: 'assign_ticket'. Known symbols: database.get_session,
main._ensure_schema, main.health, notifications._settings_by_user,
notifications.notify_assignee_on_comment, routers.tickets._session,
routers.tickets.add_comment, routers.tickets.assign, routers.tickets.create_ticket,
routers.tickets.get_ticket, routers.tickets.list_tickets, routers.users._session,
routers.users.list_users, seed.seed, services.assign_ticket
```

一个瞎猜的、未加限定的名字会带着真实列表大声地失败，而不是悄悄地返回
一个空的(并具有误导性地暗示"没有调用者"的)结果。

## 练习

`CallGraph` 只追踪模块级别的函数调用——它并不知道
`sample_app/loopline/docs/assigning-tickets.md` 讲的*正是*
`services.assign_ticket`，尽管人类同时读到这两者会立刻把它们联系起来。
请添加一个 `doc_references()` 方法，在 `DocumentIndex` 的分块与
`CallGraph` 的节点之间做简单的关键词匹配(一篇文档归一化后的文本中，是否
包含某个函数的裸名？)，并编写一个测试证明 `assigning-tickets.md` 关联
到了 `services.assign_ticket`。这正是课程计划里提到的"文档↔代码交叉
引用"——特意留给你在两部分(第8集的索引、本集的图)都已经存在之后再去
构建。

## 下一步

第10集会让检索具备*权限感知*能力：`search_docs`、`search_code` 和
`query_graph` 能看到的一些内容，并不应该对每一个角色都可见。
