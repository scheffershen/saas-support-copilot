# 第10集 — 具备权限感知的检索

**画面：** 同一个问题——「如何强制注销一个已被攻陷的账户?」——被问了两次,一次以 `support_lead` 身份,一次以 `support_agent` 身份。

## 学习目标

一个能找到一切的检索系统,就是一个能泄露一切的检索系统。让角色成为搜索的一等公民输入,并在决定什么才算得上*候选项*的那一层强制执行,而不是寄希望于 LLM 会自觉遵守的一句建议。

## 讲解要点

1. **文档分类。** `security/classification.py` 中的 `RESTRICTED_DOCS` 将路径映射到允许查看该文档的角色——`docs/admin-runbook.md`(本集新增的种子文档:如何强制注销一个已被攻陷的账户)仅限 `support_lead` 查看,这与 `docs/roles-and-permissions.md` 中已经写明的、只有该角色才能执行的操作(注销用户)完全一致。
2. **角色。** `security/roles.py` 中的 `ROLES` 并不是临时编造的示例集合——它就是 Loopline 自身的三个角色,直接取自 `seed.py` 和 `roles-and-permissions.md`。
3. **检索时鉴权,作为一道硬性边界。** `DocumentIndex.eligible_indices()` 会在*任何*排序发生*之前*,先计算出允许的分块索引子集;随后 `eligible` 会将 `BM25Index.search()` 和语义排序都限制在这些索引范围内。一个不满足资格的分块永远不会被打分——不是先打分再隐藏,而是压根不会成为候选项。
4. **为什么「永远不是候选项」很重要:抗改写能力。** 一种事后过滤(先给所有结果排序,再剔除不允许的结果)的安全性,取决于那一步过滤是否会被人遗漏调用。`test_restricted_doc_stays_invisible_to_a_paraphrased_query_too` 用完全不同的措辞——与源文档几乎没有共同词汇——询问同一个受限流程,结果依然无法被找到,因为把该分块排除在 `eligible` 之外,使得「它匹配得有多好」这个问题根本不会被提出。
5. **角色是绑定的,绝不是被传递的。** 与第5集以来每一个白名单根目录相同的纪律:`role` 是 `build_default_registry()` 中的一个 `functools.partial` 绑定,绝不是 `SearchDocsArgs` 上的一个字段。如果它是一个可由 LLM 提供的参数,模型完全可以直接声称自己在以 `support_lead` 身份搜索——RBAC 的全部意义就在于,身份来自调用方本身,而不是来自调用方请求中声称的内容。
6. **一个被明确写出的原型缺口,而非隐藏的缺口。** `is_visible_to(path, role=None)` 默认对所有人可见——在尚无鉴权层的当下很方便,但文档中明确写明这在生产环境中是错误的默认值,生产环境必须拒绝未知身份,而不是放行。第17集会回来处理这个问题。

   **更新(第17集)：** 已解决——`role=None` 现在代表权限最低的调用方,而不是权限最高的。完整的前后对比见 [`lessons/17-prototype-vs-production-architecture.md`](17-prototype-vs-production-architecture.md)。上文的描述在第16集之前都是准确的;这里按原样保留而不是悄悄改掉,处理方式与第1集的引用说明一致。

## 实现

- [`src/saas_copilot/security/roles.py`](../../src/saas_copilot/security/roles.py) — `ROLES`、`validate_role`。
- [`src/saas_copilot/security/classification.py`](../../src/saas_copilot/security/classification.py) — `RESTRICTED_DOCS`、`is_visible_to`。
- [`sample_app/loopline/docs/admin-runbook.md`](../../sample_app/loopline/docs/admin-runbook.md) — 种子受限文档。
- [`src/saas_copilot/retrieval/bm25.py`](../../src/saas_copilot/retrieval/bm25.py) / [`retrieval/index.py`](../../src/saas_copilot/retrieval/index.py) — `eligible` 贯穿整个搜索流程。
- [`src/saas_copilot/tools/docs.py`](../../src/saas_copilot/tools/docs.py) / [`tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — `search_docs`/`build_default_registry` 新增 `role`。

## 运行

```bash
pytest tests/unit/test_security_roles.py tests/unit/test_security_classification.py \
       tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_index.py \
       tests/unit/test_tools_docs.py tests/unit/test_tools_default_registry.py -v
```

## 现场演示(已验证输出)

```pycon
>>> registry = build_default_registry(settings, repo_root=repo_root, role="support_lead")
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/admin-runbook.md', 'docs/roles-and-permissions.md', 'docs/notifications.md', ...}

>>> registry = build_default_registry(settings, repo_root=repo_root, role="support_agent")
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/roles-and-permissions.md', 'docs/notifications.md', ...}   # admin-runbook.md: gone
```

(在去重之前的原始 `support_lead` 结果列表中,`admin-runbook.md` 实际上出现了三次——它被拆分成了三个分块,这正是第8集的分块逻辑在一份长度刚好两次跨过300字符边界的文档上发挥作用。)

## 失败案例(构建过程中真正踩到的坑)

我最初为「未授权角色」这个用例写的测试断言查询会找到*空结果*。但它找到了另外五份文档。`roles-and-permissions.md` 在自己的权限表中确实合法地包含了「Deactivate users」这个短语,并且对每个角色来说都正确地匹配——它不是受限文档,只是*讨论了*一个受限操作。真正需要成立的属性并不是「未授权的搜索返回空结果」,而是更窄、更精确的一条:「那份受限文档具体地永远不会出现。」如果断言了那个更强、但错误的说法,测试会因为一个与它本该证明的安全属性毫无关系的原因而失败。

## 练习

`eligible_indices()` 接受一个谓词,因此它已经能够泛化到不止「哪些角色」这一种检查。再加入一个独立的分类维度——除了角色之外,再按*内容敏感度*(例如「财务」)限制某份文档——并证明一次查询需要同时满足「角色被允许」*和*「敏感度级别被允许」才能让它出现(`predicate = lambda doc: is_visible_to(doc.path, role) and is_sensitivity_allowed(doc.path, clearance)`)。这正是多租户系统需要的形态——「角色 AND 租户」,而不只是「角色」。

## 下一步

第11集将为 `feature` 专家赋予真正的规划结构:一个有边界的多步骤工作流,而不是「调用几个工具,然后回答」。
