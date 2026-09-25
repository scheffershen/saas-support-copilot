# 第17集——原型架构与生产架构

**画面：** 完全同一次调用——一个匿名调用方，没有 `X-User-Role` 请求头，搜索"强制停用一个被攻陷的账户"——运行了两次：一次针对本集的起始代码，一次是在那处一行修复之后。第一次，`docs/admin-runbook.md` 出现在结果里；第二次，它消失了。

## 学习目标

迄今为止的每一集都在增加一项能力。这一集则围绕它们全部划出一条边界：这个原型究竟已经具备了什么，一个真正的生产部署还需要什么，以及——这两个问题唯一交汇到足以在今天就动手修复的地方——本课程自己的代码，一直在悄悄依赖一个它自己早已明说过的缺口，是哪一个？把那一个真正地补上，再把剩下的写得足够精确，让它可以被实际执行，而不只是泛泛带过。

## 讲解要点

1. **一个此前两集已经点出、并被刻意推迟处理的缺口。** 自第10集起，`security/classification.py::is_visible_to` 里 `role=None` 这个分支就无条件返回 `True`——"未知身份"被当成了*比*任何真实角色都*更*可信，而不是更不可信。第10集自己的 docstring 就把这称为"一个原型阶段的权宜之计……不是一个生产环境下安全的默认值"。第14集的 `api/dependencies.py::get_role` 重申了同一句话："翻转这个默认值，明确是第17集要做的事。"一个被写进文档的缺口，在承诺去补上它的那一集真正动手之前，仍然是一个真实的缺口。
2. **这次修复的范围，比"未知调用方什么都看不到"要窄。** `RESTRICTED_DOCS` 是一份拒绝名单——绝大多数文档根本没有条目，对所有人都可见。正确的翻转方式不是"没有身份，就没有访问权限"（那会破坏每一个 usage 领域的回答，因为本课程里除非专门在测试角色限制，否则没有任何客户端会发送 `X-User-Role`）——而是"没有身份，绝不能被当成隐式获得了那些指名了特定允许角色的内容的授权"，这恰恰是任何其他未获授权角色本来就会得到的待遇。`is_visible_to` 现在会先检查 `path not in RESTRICTED_DOCS`，用的是 `roles_allowed()` 早就用过的同一种短路方式，然后才去比较 `role`。
3. **这次修复*没有*补上的地方。** `get_role()` 依然信任调用方发来的任何 `X-User-Role`——只验证它是不是一个真实存在的角色名（`validate_role`），从不验证它是否真的属于发送它的那个人。RBAC（限制一个角色能看到什么）和身份认证（确认调用方是否真的就是那个角色）是两个不同的关切点；本集补上的是第一个关切点里的第一个缺口，不是第二个关切点。下面的检查清单故意把它们保留为两个独立、未勾选的条目。
4. **生产就绪检查清单。** `docs/production-readiness-checklist.md`——身份/访问、租户隔离、网络边界、审计留存、速率限制与成本、队列、备份、事件响应、威胁建模、责任归属。清单上每一行点名的都是它所涉及的具体文件或行为，而不是泛泛而谈的建议——这正是本课程一直以来在每一集讲解要点上坚持的同一种纪律，只是这次一次性用在了整个系统上，而不是某一集的某项功能上。
5. **租户隔离是清单上最大的一个单项缺口。** 这个代码库里从来就没有过"租户"这个概念——一个 MySQL schema，任何地方都没有 `tenant_id`，而 `query_database` 是第12集和第16集搭建的一个通用 SELECT 工具，如果要信任一个由调用方提供的租户过滤条件，它的形状恰恰是错的。在此之前没有任何一集需要点出这一点，因为 Loopline 本身建模的从来就只是单一一家组织。
6. **知识产权与授权签字这条边界，完整呈现。** 自本仓库的第一次提交，以及 `youtube_course_plan.md` 自己的设计缘起说明起就被反复提及，在这里得到了完整的处理：在把这套模式指向任何真实雇主的代码库、数据库或日志之前，先就"智能体到底可以读什么、它的输出可以去哪里"取得明确的书面授权——把这当成一项凭证来对待，而不是一个可有可无的便利——并且绝不让任何真实的专有源码、数据或产品名称流入公开仓库或公开的课程内容。本仓库从第一次提交起就一直守着这条线。
7. **压轴演示不会补完这份清单——它只是把清单摆出来。** 第18集端到端地演示完成后的原型，并把这份检查清单一并呈现出来，如实标注为"目前仍然缺失的部分"。这正是第0集第一条讲解要点里"如实说明生产环境局限"那条规则，只是这次用在了整个系统收尾的时刻，而不是某一项功能上线的时刻。

## 实现

- [`src/saas_copilot/security/classification.py`](../../src/saas_copilot/security/classification.py) — `is_visible_to` 的"默认拒绝"翻转。
- [`src/saas_copilot/api/dependencies.py`](../../src/saas_copilot/api/dependencies.py) — `get_role` 的 docstring，在翻转真正落地后做了相应更正。
- [`docs/production-readiness-checklist.md`](../../docs/production-readiness-checklist.md) — 本集的第二项交付物。
- [`tests/unit/test_security_classification.py`](../../tests/unit/test_security_classification.py)、[`tests/unit/test_tools_docs.py`](../../tests/unit/test_tools_docs.py)、[`tests/unit/test_api.py`](../../tests/unit/test_api.py) — 翻转了原有测试并新增一个测试，分别在分类层、工具层、以及真实的 FastAPI 依赖链上证明这一特性。

## 运行

```bash
pytest tests/unit/test_security_classification.py tests/unit/test_tools_docs.py tests/unit/test_api.py -v
```

## 失败案例(真实案例，本集的起始状态)

针对第16集结束时留下的原样代码——`get_role(x_user_role=None)`，也就是 FastAPI 在处理一个完全没有 `X-User-Role` 请求头的请求时真正会调用的那个函数，直接送入 `get_registry()`，走的是真实的依赖链，没有任何 mock：

```pycon
>>> role = get_role(x_user_role=None)
>>> role
None
>>> registry = build_registry_for_role(resources, role=role)
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/admin-runbook.md', 'docs/assigning-tickets.md', 'docs/creating-a-ticket.md',
 'docs/getting-started.md', 'docs/integration-notes.md', 'docs/notifications.md',
 'docs/roles-and-permissions.md'}
```

一个身份验证为"谁都不是"的调用方，拿到了这整个语料库里唯一一份被限定为仅 `support_lead` 可见的文档。

## 现场演示(经过验证的输出)

完全相同的调用，在本集对 `is_visible_to` 做出那一处改动之后：

```pycon
>>> role = get_role(x_user_role=None)
>>> role
None
>>> registry = build_registry_for_role(resources, role=role)
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/assigning-tickets.md', 'docs/creating-a-ticket.md', 'docs/getting-started.md',
 'docs/integration-notes.md', 'docs/notifications.md', 'docs/roles-and-permissions.md'}
```

`docs/admin-runbook.md`——消失了。其余一切——完全相同，六份里的六份都在。这次修复精确地移除了它本应移除的那一份文档，别的什么都没动：一个匿名调用方依然能找到每一份普通文档，和之前一模一样。

## 练习

从 `production-readiness-checklist.md` 里挑一个尚未完成的条目，补上其中最小的一块真实内容。速率限制是最自成一体的一个：在 `POST /ask` 前面加一个基础的、按调用方区分的令牌桶（用 `X-User-Role` 作为键，如果没有这个头则用连接方的 IP——真实身份的确认仍然是身份认证要管的事，不是这里要管的），一旦调用方在一个时间窗口内超过限额，就返回 `429`。写一个测试证明：紧密循环中的第 N 个请求被限流了，而第 N-1 个没有——然后更新检查清单里速率限制那一项的勾选状态，让它精确反映你实际建成了什么、还缺什么（单进程的令牌桶在多个服务器实例下是撑不住的；诚实地说明这一点，而不要悄悄地声称你建成的东西比实际更多）。

## 下一步

第18集是压轴演示：内容摄取、具备权限意识的问答、附带引用证据的 bug 诊断、借助调用图完成的 feature 可行性初判、引用、拒答、工具调用追踪、评估结果、本地部署，以及本集的这份检查清单——全部端到端地一起展示出来。它会挑战学习者去新增一个 Loopline 模块，配上属于它自己的文档、自己的角色限制，以及十个属于自己的测试。
