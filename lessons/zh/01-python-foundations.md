# 第1集 — Python 项目基础

> **注(第8集补充):** `Document.citation` 最初在 `chunk_id` 为 0 时会省略
> `#chunk-N` 后缀，把 0 当作"这份文档没有被分块"的标记。等到第8集引入真正的
> 分块之后，chunk 0 就是一个真实存在的第一个分块，而不是哨兵值(sentinel)——
> 所以引用现在总是包含它。下面的 `Document`/`SourceFile` 概念本身没有变化；
> 变的只是那一个属性的具体输出。

**画面：** 编辑器中空空如也的 `src/saas_copilot/models.py`；分屏的另一侧终端里
运行着第0集的仓库。

## 学习目标

之后的每一集都会在函数、工具与 LLM 之间传递数据。现在就用类型和测试把这份
数据的形状定好，这样下游的一切就不用靠猜。

## 讲解要点

1. **包(Packages)。** `src/saas_copilot/` 是一个真正可安装的包——`pyproject.toml`
   声明了它(`packages = ["src/saas_copilot"]`)，第0集里的 `pip install -e ".[dev]"`
   正是让 `from saas_copilot.models import Document` 能在任何地方(包括
   `tests/`)都能正常导入的原因。
2. **类型标注(Type hints)。** 下面的每一个字段都带有类型标注。这不是装饰——
   它能让你的编辑器今天就抓到一个拼写错误，也能让结构化的 LLM 输出(第3集)
   针对一份 schema 做校验，而不是寄希望于模型刚好给出了正确的形状。
3. **数据类(Dataclasses)。** `@dataclass(frozen=True)` 免费为我们提供了相等性
   判断、`repr`，以及不可变性。不可变性在这里尤其重要：一旦 copilot 检索到一个
   `Document` 用来回答问题，流水线后面的任何环节都不应该能够悄悄改动它的内容，
   让你即将打印出来的引用变得对不上。
4. **异常(Exceptions)。** `SourceFile.line()` 会抛出一个带有具体、可读信息的
   `IndexError`，而不是任由一个裸的索引错误逃逸出去。第5集的工具正是捕获这种
   模式，把它转成一个干净的工具调用错误，而不是让一段堆栈跟踪(stack trace)
   直接甩给用户。
5. **异步基础(Async basics)。** Loopline 的各个端点，以及 copilot 的
   `/health`，现在仍然是普通的 `def`——目前还没有任何 I/O，所以 `async def`
   不会带来任何好处。第5集会把工具调用函数改成 `async def`，因为它们要做
   真正的文件、数据库和日志读取，我们不希望一次缓慢的工具调用挡住所有其他
   请求。
6. **venv / pyproject.toml / 依赖锁定。** 回顾第0集的内容：`pyproject.toml`
   里的 `>=` 版本范围，对于一门今天就能重跑的课程来说没问题，但一次真正的
   部署(第16集)需要一组精确锁定的版本，这样"在我机器上能跑"才不会在生产
   环境反咬你一口。
7. **pytest。** `tests/unit/test_models.py` 为课程接下来的部分定下了模式：
   每种行为一条正常路径测试、一条失败路径测试，而不是每个函数只写一条测试。

## 实现

- [`src/saas_copilot/models.py`](../../src/saas_copilot/models.py) — `Document`、`SourceFile`。
- [`tests/unit/test_models.py`](../../tests/unit/test_models.py) — 6 个测试。

## 运行

```bash
pytest tests/unit/test_models.py -v
```

## 失败案例(现场演示)

```pycon
>>> from saas_copilot.models import SourceFile
>>> f = SourceFile(path="app/notifications.py", language="python", content="a\nb\nc")
>>> f.line(10)
IndexError: app/notifications.py has no line 10 (file has 3 lines)
```

## 练习

新增第三个模型 `LogEntry`(`path`、`line_number`、`level`、`message`)，遵循
同样的原则：遇到非法输入时抛出清晰、具体的异常，而不是任由程序裸崩溃，也不是
悄悄返回一个 `None`。先写好它，再写好它的测试，然后再继续往下走。你会在第5集
的日志读取工具里真正把它接上。

## 下一步

第2集会发起一次尽可能小的、真实的 LLM 调用，背后用一个假/真 provider 开关来
切换，这样课程在没有 API key 的情况下依然能跑。
