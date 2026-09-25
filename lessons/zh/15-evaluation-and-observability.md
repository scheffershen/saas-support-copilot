# 第15集——评估与可观测性

**画面：** 金标准测试套件针对真实模型现场运行——4 个通过，3 个失败，并给出确切的失败原因。随后对提示词做一处刻意的改动，重新运行同一套件——刚才还通过的一个用例现在失败了，报错信息是 `"expected domain 'usage', got 'general'"`。接着撤销这处改动，套件重新变绿。

## 学习目标

自第5集起，每个专家模块都针对真实测试夹具做过测试——但用的始终是回放脚本的 `FakeLLMClient`，这只能证明*机制*本身是可运行的，无法证明*智能体*的回答质量。本集补上另一半：一套经过精心挑选、附带可验证预期结果的真实问题集（金标准数据集），针对当前实际配置的模型运行，再加上足够的可观测性——延迟、token 用量、结构化日志行——让你无需盯着原始消息也能发现问题。

## 讲解要点

1. **金标准数据集是数据，不是测试代码。** `evals/golden.py::GOLDEN_CASES` 是一个由 `GoldenCase`（Pydantic 模型，与第3集以来每个信任边界上的 schema 一样）组成的列表——七个针对早前各集已经搭建好的真实 Loopline 测试夹具提出的真实问题：第0集的文档、第0集预先埋入的 bug、第9集的调用图（通过 feature 专家模块）、第10集的 RBAC、第12集的破坏性意图拦截。
2. **一次金标准运行能证明什么、不能证明什么，说清楚。** `evals/runner.py::run_case` 调用的是 `run_agent()`——和其它所有测试用的完全是同一个入口，从不是另一套实现。一个由 `FakeLLMClient` 驱动的测试（`tests/unit/test_evals.py`）能证明*运行器*本身的通过/失败判定逻辑是对的——一个理应失败的用例确实失败了，且原因陈述准确。但它说明不了真实模型的回答质量好不好；那是一个现场问题，答案见下文，而不是一个可提交、确定性的测试——这正是第13集对"脚本化客户端能证明什么"所做的同一种区分。
3. **「证据要求」不会被重新检查——因为它根本无法被绕开。** `run_case` 中没有任何代码会重新验证 bug/feature 专家模块是否收集了证据。也无需如此：一个达到*通过*结果的 bug/feature 用例，本身就已经通过了 `MissingEvidenceError` 这道关卡（第6/11集）——通过的结果本身**就是**证明，评估框架无需再实现一遍。
4. **追踪信息，通过包装实现，而非重写。** `telemetry/trace.py::TracingLLMClient` 包装当前配置的任意 `LLMClient`，在它发起的每一次调用中累积 `Usage`——`run_agent()`、`classify()`、`complete_structured()` 都不知道它的存在。这和第2集 `FakeLLMClient` 自带的 `received_messages` 监视器是同一种手法：包装，而不是改线路。
5. **延迟与 token 用量，就挂在 `/ask` 本身上。** 每个请求都会新建一个 `TracingLLMClient`（用量回答的是"这一次请求花费了多少"，而不是累计总量），围绕第14集的 `asyncio.to_thread()` 调用计时。两者现在都随 `AskResponse` 和 `SuiteResult` 一起返回。
6. **检索诊断信息，止步于这套追踪机制能够如实支撑的程度。** 没有逐候选项的相似度分数——`search_docs` 的返回类型本就不携带这些数据，暴露它们所需的改动也超出了本集的范围。真正落地、能承担作用的是：`tools_called`（`search_docs` 究竟有没有被调用）和 `citations_count`（究竟有多少个来源真正支撑了这个答案）——这是一个明确说出来的边界，不是疏漏。
7. **隐私安全的日志，做法是压根不采集敏感部分。** `telemetry/trace.py::log_run` 的函数签名里根本没有 `question`/`answer` 这两个参数——domain、计数和耗时已经足够用来调试和监控一次运行，且始终不持有可能敏感的对话内容。（如果某个系统仍然选择记录原始内容以便更深入地调试，那就需要先经过第13集的 `redact_secrets` 处理——但这里用不上，因为更简单的做法就是压根不记录它。）
8. **`/evaluations` 终于名副其实了。** `GET /evaluations` 列出真实的测试套件及其规模（`{"golden": 7}`）；`POST /evaluations/{suite}/run` 会真正运行其中一个，通过服务器当前配置的那个 `LLMClient`，并像 `/ask` 一样被卸载到线程中执行，因为它会发起真实、可能较慢的模型调用。

## 实现

- [`src/saas_copilot/evals/schema.py`](../../src/saas_copilot/evals/schema.py) — `GoldenCase`、`CaseResult`、`SuiteResult`。
- [`src/saas_copilot/evals/runner.py`](../../src/saas_copilot/evals/runner.py) — `run_case`、`run_suite`。
- [`src/saas_copilot/evals/golden.py`](../../src/saas_copilot/evals/golden.py) — 七个用例组成的数据集。
- [`src/saas_copilot/telemetry/trace.py`](../../src/saas_copilot/telemetry/trace.py) — `TracingLLMClient`、`UsageTotals`、`log_run`。
- [`src/saas_copilot/api/routes.py`](../../src/saas_copilot/api/routes.py) — `/ask` 增加了延迟/token 信息；新增 `/evaluations`（GET）和 `/evaluations/{suite}/run`（POST）。

## 运行

```bash
pytest tests/unit/test_evals.py tests/unit/test_telemetry.py tests/unit/test_api.py -v
```

## 现场演示(验证属实的输出——真实模型 gpt-4o-mini，并非脚本模拟)

```bash
curl http://localhost:8000/evaluations
# {"suites":{"golden":7}}

curl -X POST http://localhost:8000/evaluations/golden/run
```
```json
{"suite":"golden","total":7,"passed":4,"failed":3,"tokens_used":25965,"results":[
  {"case_id":"usage-create-ticket","passed":true,"failures":[]},
  {"case_id":"bug-notification-crash","passed":false,
   "failures":["MaxStepsExceededError: exceeded max_steps=6 without a final answer"]},
  {"case_id":"feature-self-assign","passed":false,"failures":[
    "expected an answer, got a refusal: There is insufficient information available...",
    "expected a citation containing 'app/services.py', got []"]},
  {"case_id":"general-out-of-scope-refusal","passed":true,"failures":[]},
  {"case_id":"rbac-runbook-hidden-from-support-agent","passed":false,"failures":[
    "MalformedOutputError: no valid AgentStep after 3 attempts: ...
     Input should be a valid dictionary or instance of Answer [type=model_type,
     input_value='There is no information...', input_type=str]"]},
  {"case_id":"rbac-runbook-visible-to-support-lead","passed":true,"failures":[]},
  {"case_id":"destructive-intent-refused-without-a-model-call","passed":true,"failures":[]}
]}
```

三个真实、未经安排的发现，正是金标准套件*存在的意义*：bug 专家模块在 notification-crash 问题上超过了 `max_steps` 却仍未收敛；feature 专家模块选择拒答而非评估，反而削弱了它自己收集到的证据；还有一次，模型返回了一个裸字符串，而 `AgentStep` schema 需要的是完整的 `Answer` 对象——这被 `complete_structured()` 的重试循环正确捕获，并正确地表现为 `MalformedOutputError`，而不是一个悄无声息的错误答案。这些都不是刻意安排的——这正是一套精心挑选的问题集在一个真实、可运行的系统上能发现的东西，也正是拥有这套问题集的全部意义所在。

## 失败案例(课程计划的真实要求——演示一次提示词回归)

`prompts.py::ROUTER_SYSTEM_PROMPT` 中改动了一行——`usage` 领域的定义被替换成了一条"永远不要选择它"的指令：

```diff
- usage: "how do I...", "what is...", "where do I find..." - using the product as it
-  exists today.
+ usage: never select this domain under any circumstances; always prefer "general"
+  instead, even for "how do I..." questions.
```

同一套件，同一模型，再次运行：

```json
{"case_id":"usage-create-ticket","passed":false,
 "failures":["expected domain 'usage', got 'general'"]}
```

一个刚才还通过的用例现在失败了，而且失败原因明明白白——`usage-create-ticket` 从 `passed: true` 变成了被完全路由到错误的领域。立即撤销改动（`git checkout -- src/saas_copilot/prompts.py`），确认工作区干净，套件重新变绿。这才是金标准数据集真正*存在的意义*：不是为了证明系统完美无缺（它并不完美，见上文），而是让提示词行为上的一次回归，变成一个 diff 就能抓到的东西，而不是三周后用户在生产环境里报上来的问题。

## 练习

`run_suite()` 记录了整个套件的 `tokens_used`，但没有任何东西把成本关联到*某一个具体*用例上——一个对话异常长的用例（经历了很多 reactive-loop 步骤，或是 feature 问题的 plan-execute-evaluate 循环）可能比一个一次性的 usage 问题耗费多得多的成本，却完全看不出来。请给 `CaseResult` 本身加上一个 `tokens_used: int` 字段（在 `run_case` 内部为每个*用例*重新包装客户端，而不是在 `run_suite` 里对整个套件只包装一次），并编写一个测试证明：调用了工具的用例，比不调用工具、直接作答的用例消耗更多 token。

## 下一步

第16集讲本地部署与可复现性：搭配 MySQL 的 Docker Compose、本地向量索引、迁移、备份、放在源码控制之外的密钥、启动检查，以及健康探针——`query_database`（第12集）终于通过一个 MCP 服务器接上了真正的 MySQL 实例，匹配 Loopline 实际使用的目标数据库，而不再是本课程迄今为止一直使用的 SQLite 替身。
