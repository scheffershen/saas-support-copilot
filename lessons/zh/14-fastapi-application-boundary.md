# 第14集 — FastAPI 应用边界

**画面：** 对一个真实运行中的服务器执行 `curl -X POST /ask`——一个真实的、带引用的答案返回,请求 ID 同时出现在响应头和响应体里。接着,把完全相同的请求发给一个未配置、未预先设脚本的客户端——得到的是一个干净的 `502 malformed_output`,而不是一段 Python 堆栈回溯。

## 学习目标

到目前为止构建的一切,都是被测试和彼此在进程内直接调用的。本集为它赋予了一个 HTTP 边界——同一套 `ask()`/`run_agent()` 流水线,早前每一集的测试都已经在使用它,现在可以通过网络访问了。这道边界带来了它自己的一系列关切:来自陌生人的请求体需要一个经过校验的形状;那些昂贵的共享资源(文档索引、调用图)需要在许多请求之间存活下来,而不是每次请求都重新构建一遍;同步工作不能阻塞其他请求共用的那个事件循环;而这门课程自己定义的每一种异常类型,都需要变成一个客户端真正能解析的响应——而不是一段堆栈回溯。

## 讲解要点

1. **请求/响应模型,理由与第3集的 `Answer` 相同。** `api/schemas.py` 的 `AskRequest`/`AskResponse` 是 Pydantic 模型——一个 HTTP 请求体,和一次 LLM 的输出一样,都是不受信任的输入,FastAPI 会在路由处理函数看到它之前就先校验它。
2. **依赖注入还清了一笔旧账。** `tools/__init__.py::build_default_registry` 从第10集起就一直带着一条注释:对于一个只构建一次注册表、用完即止的测试来说,每次调用都重建文档索引和调用图没问题;但对于一个要处理许多不同角色请求的服务器来说,这就不对了。把它拆分成 `build_shared_resources()`(开销大,只构建一次)和 `build_registry_for_role()`(开销小,只重新绑定角色)——`api/main.py` 的 `lifespan` 在启动时构建一次共享部分,并把它存放在 `app.state` 上;`api/dependencies.py` 的 `Depends()` 提供者在每次请求时把它读回来。`build_default_registry()` 现在只是这两步之上的一层薄封装,之所以保留它,是为了让早前每一集的测试都能一字不差地照旧调用它——这一点被直接证明了(`test_build_default_registry_matches_the_split_two_step_build`)。
3. **诚实的异步端点。** `run_agent()`/`ask()` 是同步的,这是故意的,遵循第5集自己的更正说明(一个线程池超时,而不是真正的异步)。路由处理函数照样是 `async def`,并且显式地用 `asyncio.to_thread()` 把真正的智能体工作挪到一个工作线程上——这样一次缓慢的智能体运行就不会阻塞其他所有并发请求共用的那个事件循环。FastAPI 本来也会自动把一个普通的 `def` 处理函数丢进线程池运行(Loopline 自己的 `routers/tickets.py` 自第0集以来就一直原封不动地依赖这一点)——这里的显式写法只是把同样的机制明明白白地写出来,而不是让它保持隐式。
4. **请求 ID,以中间件的形式实现。** `add_request_id` 包裹每一个请求——如果调用方自己发来了 `X-Request-ID` 就用它,否则就生成一个新的——在路由运行之前被设置到 `request.state` 上,并且无论成功响应*还是*错误响应,都会被回显为一个响应头,因为中间件包裹的是整个调用过程,包括异常处理在内。
5. **一个既便宜又真实的健康检查。** `/health` 会报告一个真实的数字(`docs_indexed`,从 `app.state` 上读出来),而不需要重建任何东西——这证明的是该服务真正依赖的东西(文档索引)还活着,而不仅仅是进程本身还在运行,而且快到可以被持续轮询。
6. **错误响应:本课程已经定义的每一种异常类型各配一个处理器,绝不使用裸的 `except Exception`。** `UnknownRoleError` → 400(客户端自己的错误);`AgentError` 及其每一个子类 → 422(一个格式良好的请求,但被智能体自身的安全约束拦下、无法作答);`LLMTimeoutError` → 504,注册顺序排在更笼统的 `LLMError` → 502 之前(Starlette 是沿着异常的 MRO 向上走来解析处理器的,所以更具体的那个注册会胜出);`MalformedOutputError` → 502(供应方确实响应了,但即便经过 `complete_structured()` 的重试,依然从未产生过有效输出)。任何没有在这里被点名的异常,依然会以 FastAPI 原本的 500 呈现出来——吞掉未知异常不是在处理 bug,只是在掩盖它。
7. **角色以请求头的形式传递,绝不作为请求体字段。** `AskRequest` 没有 `role` 字段——`X-User-Role` 是一个依赖项(`get_role`),独立于问题本身之外,与自第5/10集以来每一个白名单根目录、每一个绑定角色遵循同样的纪律。这一点被一路证明到底,而不只是被断言:`test_get_registry_binds_the_role_all_the_way_to_the_tools_own_filtering` 直接调用 `get_registry()`(一个 FastAPI 依赖项本质上就是一个普通函数),并确认由此得到的注册表中,`search_docs` 依然无法为 `support_agent` 呈现出那份受限的管理员运维手册。
8. **`/ingest` 和 `/evaluations`,诚实地面对它们今天实际做了什么。** `/ingest` 是真实的,不是一个占位符:它会从磁盘重新读取 Loopline 的文档/源代码,并在不重启进程的情况下重建共享资源,只有在重建完成之后才会把它们替换到 `app.state` 上,这样一次正在进行中的请求就不会被打断。`/evaluations` 返回 `{"suites": []}`——这是真实的空,因为目前还没有注册任何评估套件;那是第15集的任务,眼下这只是它将来要填充的形状,而不是一个假装在运行些什么、实际什么都没有的占位符。

## 实现

- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — `SharedResources`、`build_shared_resources`、`build_registry_for_role`。
- [`src/saas_copilot/api/schemas.py`](../../src/saas_copilot/api/schemas.py) — 请求/响应模型。
- [`src/saas_copilot/api/dependencies.py`](../../src/saas_copilot/api/dependencies.py) — `Depends()` 提供者。
- [`src/saas_copilot/api/routes.py`](../../src/saas_copilot/api/routes.py) — `/health`、`/ask`、`/ingest`、`/evaluations`。
- [`src/saas_copilot/api/main.py`](../../src/saas_copilot/api/main.py) — `lifespan`、请求 ID 中间件、异常处理器。

## 运行

```bash
pytest tests/unit/test_api.py tests/unit/test_tools_default_registry.py -v
```

## 现场演示(已验证输出)

```bash
curl http://localhost:8000/health
# {"status":"ok","docs_indexed":13}

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"session_id": "demo", "question": "how do I create a ticket?"}'
# {"request_id":"b65f7813-...","domain":"usage",
#  "answer":"To create a ticket in Loopline, follow these steps:\n\n1. Click New
#  ticket.\n2. Enter a title and description.\n3. Submit the ticket. The ticket will
#  start in the open status with no assignee.",
#  "citations":["docs/creating-a-ticket.md#chunk-0"],"confidence":1.0,
#  "refused":false,"refusal_reason":null,"steps_taken":2,"tools_called":["search_docs"]}
# (captured with a real OpenAI-compatible provider configured; the committed default,
# LLM_PROVIDER=fake, is covered in the failure case below instead - it was never
# meant to produce a coherent answer unscripted, only this course's tests script it)

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -H "X-User-Role: superadmin" -d '{"session_id": "demo", "question": "hi"}'
# 400 {"error":"unknown_role",
#      "detail":"unknown role: 'superadmin'. Known roles: billing_admin,
#      support_agent, support_lead","request_id":"c7eb6274-..."}

curl -D - -o /dev/null http://localhost:8000/health -H "X-Request-ID: my-own-trace-id"
# x-request-id: my-own-trace-id   <- echoed back exactly, not replaced
```

## 失败案例(现场演示 — 实际提交的默认配置,零配置)

`LLM_PROVIDER=fake`(仓库自己的 `.env.example` 默认值)给你的是一个*未预先设脚本*的 `FakeLLMClient`——它那唯一固定的回复 `"This is a fake response."`,本来就从未打算单独作为合法 JSON 使用;本课程里每一次真正的演示,都会先为它编写脚本。除了 README 自己的快速上手步骤之外什么都不配置,直接命中 `/ask`:

```pycon
>>> response = client.post("/ask", json={"session_id": "demo", "question": "how do I create a ticket?"})
>>> response.status_code
502
>>> response.json()
{'error': 'malformed_output',
 'detail': "no valid RouteDecision after 3 attempts: not valid JSON: Expecting value: line 1 column 1 (char 0)",
 'request_id': '859ae080-...'}
```

这正是第4集里 `complete_structured()` 自身「重试后抛出」行为的体现,只不过现在它以一个干净的、结构化的 502 呈现出来,而不是一个未被处理的异常——即便在「背后的一切都还没配置好」这唯一的情形下,这道边界依然完成了自己的职责。

## 练习

`AgentCancelledError` 从本集起就已经拥有一套完整的「异常到状态码」映射(422),但 API 里目前没有任何东西会真正触发它——`memory/orchestration.py::ask()` 眼下根本不接受 `cancel_token` 参数。把它贯穿进去:给 `ask()` 的签名加上 `cancel_token`(直接传给已经接受这个参数的 `run_agent()`),在 `/ask` 处理函数里为每个请求创建一个全新的 `threading.Event`,并在客户端于智能体运行结束之前断开连接时设置它(用 FastAPI 的 `Request.is_disconnected()`,由一个与 `asyncio.to_thread()` 调用赛跑的小型后台任务来检查)。写一个测试,证明一次原本会成功的运行,会在这个令牌被触发时,在循环执行到一半时被切断。

## 下一步

第15集覆盖评估与可观测性:黄金数据集、答案/引用/拒绝/访问控制测试,专门针对 `bug`/`feature` 类问题的「回答前必须先有证据」检查,追踪、延迟、token 用量、检索诊断,以及隐私安全的日志。`/evaluations` 终于有了真正可以汇报的内容。
