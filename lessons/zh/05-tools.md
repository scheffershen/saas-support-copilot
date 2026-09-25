# 第5集 — 工具与安全的工具契约

> **注：** 第2集曾说这些工具将来会变成 `async def`，理由是"它们要做真正的
> 文件、数据库和日志读取"。但实际动手实现时，一个普通的同步函数加上
> `ToolRegistry` 的线程池超时包装器反而更简单——测试中不需要事件循环，而且
> 对于这个规模的 I/O，它解决的是同一个"不能让一次慢调用卡住一切"的问题。
> 真正的 `async def` 仍然会出现，但会出现在它真正值得使用的地方：第14集的
> FastAPI 服务器，需要同时处理大量并发请求——即便在那里，FastAPI 也会自动
> 把同步的路径函数放进线程池运行，这与 `ToolRegistry` 在这里手工采用的模式
> 如出一辙。计划遇到真实问题时会发生变化；这正是那种变化的体现，而不是需要
> 掩饰的前后矛盾。

**画面：** 文件树中的 `sample_app/loopline/`——docs/、app/，以及这个仓库
自身的 `git log`——这就是即将授予该副驾驶只读访问权限的四样东西。

## 学习目标

给副驾驶一些真正可以查看的东西。这里构建的每一个工具都是只读的、经过参数
校验的，并被限制在一个白名单根目录之内——契约本身比任何单个工具都更重要，
因为第6集的智能体循环将完全信任这一层。

## 讲解要点

1. **工具模式(Tool schemas)。** 每个工具都配有一个小型的 Pydantic `*Args`
   模型(`SearchDocsArgs`、`ReadSourceArgs`……)——与第3集中 `Answer` 所遵循
   的"先校验、后信任"原则如出一辙，只不过这次校验的是工具的*输入*，而不是
   LLM 的*输出*。
2. **参数校验。** `SearchCodeArgs` 在模式层面就会拒绝无效的正则表达式，
   早于 `search_code()` 真正运行之前——`field_validator` 把"在函数深处
   崩溃"变成了"在门口就被拒绝，并附带清晰的错误信息"。
3. **只读工具与可变更工具。** `ToolRegistry.register()` 会拒绝任何未标记
   `read_only=True` 的工具。目前这套代码库里根本没有办法注册一个会产生
   变更的工具——不是"提示词里写着不要这样做"，而是这条代码路径压根不存在。
4. **白名单。** `resolve_within_root()` 才是真正的边界：每个文件工具都
   通过 `functools.partial` 在*注册时*(`tools/__init__.py`)被绑定到唯一
   一个目录上，而不是作为调用者传入的参数。LLM 能选择的任何参数，都无法
   把工具重定向到开发者设定范围之外的地方。
5. **超时。** `ToolRegistry.call()` 让每个处理函数都通过线程池的
   `future.result(timeout=...)` 运行——这种方式可移植(基于信号的超时机制
   在 Windows 上并不存在)，而且统一(不需要每个工具自己记得去实现超时)。
6. **授权。** 两个不同的层级，不要混为一谈：本集的白名单根目录是*系统*级
   授权(进程本身被允许触碰什么，仅此而已)。*用户*级授权——某个具体用户的
   角色允许他看到什么——留到第10集。
7. **结果数量限制。** `search_docs`/`search_code` 会限制结果数量，
   `read_source` 在超过 20k 字符后会截断，`list_files` 拒绝返回超过 200
   条记录，而不是把整棵目录树悄悄地塞进模型的上下文里。

## 构建过程中发现的两个真实 bug

这两个 bug 都不是为了本课特意设计出来的——它们都是在实际运行测试时暴露
出来的，而这正是运行测试的意义所在。

**一个真实存在的安全隐患，在被防范之前就已经被证实。** 在纯 pathlib 中，
`Path("allowed/root") / "/etc/passwd"` 会被求值为 `Path("/etc/passwd")`——
当右侧是绝对路径时，`/` 运算符会*直接丢弃左侧*。一个只做前缀检查的路径
守卫(`candidate.resolve().is_relative_to(root)`，在一次朴素拼接*之后*才
检查)在运行时，根目录早就已经被丢掉了。正因如此，`resolve_within_root()`
会先检查 `Path(relative_path).is_absolute()`，然后才进行任何拼接。

```pycon
>>> from pathlib import Path
>>> from saas_copilot.tools.source import read_source
>>> read_source("C:/Windows/win.ini", root=Path("sample_app/loopline/app"))
ToolError: path must be relative, got an absolute path: 'C:/Windows/win.ini'
```

**`list_files` 中的一个真实 bug，被它自己的测试抓到。** 第一版代码解析了
`start`(通过 `resolve_within_root()`，返回的是绝对路径)，但在计算结果时
却用 `p.relative_to(root)` 使用了*原始的、未解析的* `root`。在
`relative_to()` 中把一个已解析的绝对路径和一个未解析的相对路径混用会
抛出 `ValueError`——pathlib 在这里并不认为一个路径和它自身的解析形式可以
互换。`test_list_files_scoped_to_a_subdirectory` 如实地失败了；修复方式
是提前把 `root` 解析一次，然后在函数中的所有地方都使用这个值。完整的
失败与修复过程参见 `feat(copilot): search_docs, read_source, search_code, list_files
tools` 这次提交。

## 实现

- [`src/saas_copilot/tools/base.py`](../../src/saas_copilot/tools/base.py) — `ToolError`、`resolve_within_root`。
- [`src/saas_copilot/tools/registry.py`](../../src/saas_copilot/tools/registry.py) — `ToolSpec`、`ToolRegistry`。
- [`src/saas_copilot/tools/docs.py`](../../src/saas_copilot/tools/docs.py) — `search_docs`。
- [`src/saas_copilot/tools/source.py`](../../src/saas_copilot/tools/source.py) — `read_source`、`search_code`。
- [`src/saas_copilot/tools/files.py`](../../src/saas_copilot/tools/files.py) — `list_files`。
- [`src/saas_copilot/tools/git_history.py`](../../src/saas_copilot/tools/git_history.py) — `git_log`、`git_show`(子进程调用，仅使用参数列表形式，并对
  `commit` 施加了严格的十六进制限制——因为 git 会把开头的 `-` 当作选项
  标志，如果直接透传，精心构造的 commit 值就可能被当作选项而不是引用来
  解析)。
- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — `build_default_registry()`。

## 运行

```bash
pytest tests/unit/test_tools_base.py tests/unit/test_tools_registry.py \
       tests/unit/test_tools_docs.py tests/unit/test_tools_source.py \
       tests/unit/test_tools_files.py tests/unit/test_tools_git_history.py \
       tests/unit/test_tools_default_registry.py -v
```

每个测试使用的夹具都是真实的，不是合成的：`search_code` 在
`notifications.py:26` 找到 `"KeyError"`，正是第0集在真实回溯(traceback)
中验证过的那一行；对 `services.py` 运行 `git_log`，返回的是这个仓库中
真实存在的"先 feat 后 fix"提交对。

## 练习

目前 `ToolRegistry.call()` 会让 Pydantic 静默忽略 `raw_args` 中意料之外
的键(参见 `test_call_rejects_extra_arguments_not_in_the_schema`——它其实
什么都没有拒绝，这个名字描述的是当前的行为，而不是一种保证)。请为每一个
`*Args` 模式添加 `model_config = ConfigDict(extra="forbid")`，并修改这个
测试的名称和断言，使其匹配新的、更严格的行为。然后自己论证一下：对于面向
LLM 的模式来说，静默丢弃模型凭空捏造出来的字段，和大声拒绝它们，哪一种
才是更正确的做法。(这个问题有一个真实的答案，第13集会给出提示。)

## 下一步

第6集将构建智能体循环：`classify()` 负责选定领域，循环从这个注册表中
挑选工具，而 `bug` 专家必须先收集到真实证据——一次 `read_source` 或
`search_code` 调用，而不是凭猜测——才被允许作答。
