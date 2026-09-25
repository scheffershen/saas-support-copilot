# 第11集 — 规划与多步骤工作:功能可行性评估

**画面：** 「我们能不能让任何人自行认领工单?」这个问题——以及,正如第4集埋下的伏笔,本课程发展到这一步,模型终于获得了在决定下一步调用哪个工具之外的真正决策权。

## 学习目标

第6集的反应式循环是一步一步地决策,对刚刚看到的内容做出反应。这对于处理一份 bug 报告是正确的形态。但对于「评估这是否可行」这类问题来说,这个形态就不对了——这类问题受益于提前思考:在花费第一次工具调用之前,先想清楚需要哪些证据才能定论,以及先后顺序。为 `feature` 专家配备一个先规划、后执行的工作流。

## 讲解要点

1. **计划作为结构化数据。** `FeaturePlan`(`planning/plan.py`)是一个 Pydantic 模型,而不是模型自由撰写的字符串——它是一份 `PlanStep` 列表,每一项都带有 `tool`、`arguments`、`depends_on` 和 `rationale`。与 `Answer` 和 `AgentStep` 遵循同样的纪律:先校验形状,再信任内容。
2. **原子化动作,依赖顺序。** 每个 `PlanStep` 对应一次工具调用。计划自带的 `model_validator` 会拒绝一个悬空的 `depends_on` 引用、一个重复的 `step_id`,或一个环(包括最简单的自环)——做法是真正运行一遍 `topological_order()`(Kahn 算法),并让真实的 `ValueError` 传播进 `complete_structured()` 已经提供的重试循环中。一份格式有误的*计划*,会以处理一份格式有误的 *Answer* 完全相同的方式被修正。
3. **顺序执行的工作流。** 计划一旦通过校验,就会按依赖顺序执行——这是被证明的,而不是被假设的:`test_plan_executes_in_dependency_order_not_json_order` 故意在脚本化的 JSON 中把有依赖关系的那一步排在前面,并检查 `tools_called`(实际执行顺序),而不是相信 JSON 本身的排列顺序。
4. **一个被明确说出的权衡,而非被掩盖的权衡。** 这里没有任何机制允许后一步的 `arguments` 引用前一步的*结果*——整份计划是在任何证据返回之前就一次性写好的。`depends_on` 控制的是*顺序*,不是*数据流*。与第6集那种能根据刚刚观察到的内容调整每一步的反应式循环相比,这确实丢失了一部分真实的自由度。本集的练习就是要补上这个缺口。
5. **评估者-优化者工作流。** 一次独立的第二判断(`FeasibilityEvaluation`)会依据一份评分标准检查草稿 `Answer`——是否附有引用、「相互隔离」这类说法是否有真实的 `query_graph` 调用方检查作为支撑、语气是否不过度自信——并且可以把它打回去修改,但仅限一次。
6. **修改稿会被重新检查,而不是被直接信任。** 这个循环的第一版实现中,修改一次之后可以*不经过任何再评估*就直接发布——这让配备评估者这件事本身失去了意义。这是在写测试的过程中发现并修复的:每一次修改都会在发布前重新检查一遍;如果预算耗尽时答案仍未通过,它还是会照常发布(它已经通过了证据关卡,并且是一个合法的 `Answer`)——这是有边界的努力,不是必然获批的保证。
7. **同一道证据关卡,应用于计划而非循环。** `feature` 专家的 `required_evidence_tools`(第6/9集)没有变化——变化的是*如何*检查它:针对的是计划中成功执行的工具调用,而不是逐步循环中的工具调用。

## 实现

- [`src/saas_copilot/agent_types.py`](../../src/saas_copilot/agent_types.py) — `AgentRunResult`/错误类型,被抽取出来,这样 `agent.py` 和 `planning/` 就不必相互导入。
- [`src/saas_copilot/tools/formatting.py`](../../src/saas_copilot/tools/formatting.py) — `format_tool_result`,同样被共享。
- [`src/saas_copilot/tools/registry.py`](../../src/saas_copilot/tools/registry.py) — `ToolRegistry.describe()`。
- [`src/saas_copilot/planning/plan.py`](../../src/saas_copilot/planning/plan.py) — `PlanStep`、`FeaturePlan`、`topological_order`。
- [`src/saas_copilot/planning/schema.py`](../../src/saas_copilot/planning/schema.py) — `FeasibilityEvaluation`。
- [`src/saas_copilot/planning/feasibility.py`](../../src/saas_copilot/planning/feasibility.py) — `assess_feasibility`。
- [`src/saas_copilot/agent.py`](../../src/saas_copilot/agent.py) — `run_agent` 将「feature」分派到这里,而不是运行反应式循环。

## 运行

```bash
pytest tests/unit/test_planning_plan.py tests/unit/test_planning_feasibility.py \
       tests/unit/test_agent.py -v
```

## 现场演示(已验证输出)

```pycon
>>> # plan JSON lists "callers" (depends on "find") BEFORE "find" itself
>>> result = assess_feasibility(client, registry, "could we let anyone self-assign a ticket?", specialist=feature)
>>> result.tools_called
('search_code', 'query_graph')   # "find" ran first, despite JSON order - topological_order() resorted it
>>> result.answer.answer
'Only support_lead can currently assign tickets to others; letting anyone self-assign would touch assign_ticket and its one caller.'
```

## 失败案例(现场演示)

```pycon
>>> assess_feasibility(client, registry, "could we add dark mode?", specialist=feature)
# plan only calls search_docs - not in feature's required_evidence_tools
MissingEvidenceError: feature specialist's plan didn't include a successful call to one of ['list_files', 'query_graph', 'read_source', 'search_code']
```

提前规划并不会放松证据规则的要求——它只是把检查的*时机*从「每一步之后」挪到了「整个计划执行完之后」。

## 练习

补上讲解要点4中提到的那个缺口:让 `PlanStep` 的 `arguments` 能够通过一个占位符(例如 `"{{find.first_match_path}}"`)引用前一步的结果,并在该步骤即将执行、其依赖已经跑完之后再解析这个占位符。写一个测试,用一份计划证明步骤 B 的参数在字面上不可能在步骤 A 的真实结果返回之前就被知道——从而证明这种解析发生在执行时,而不是计划生成时。

## 下一步

第12集将为写操作形状的问题(例如「我该如何注销这个账户」)配备真正的审批关卡——解释一个操作,与被信任去执行一个操作,是两回事。
