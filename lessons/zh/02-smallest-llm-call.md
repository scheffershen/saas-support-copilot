# 第2集 — 最小可用的 LLM 调用

**画面：** 空的 `src/saas_copilot/llm/`，然后逐个文件搭建起来。

## 学习目标

无论是托管的还是本地的，每一个 provider 说的都是大致相同的"语言"：传入一个
消息列表，返回一条消息和一个 token 数。在碰真正的 API key 之前，先把这个
形状用一个接口固定下来，只搭一次。

## 讲解要点

1. **消息(Messages)。** 一次 chat 调用就是一串 `{role, content}` 轮次
   (`system`、`user`、`assistant`)——对应 `llm/base.py` 里的 `Message`。
   系统消息是指令，用户消息是对话本身；这个列表里的任何内容都不天然可信，
   这一点到第13集把检索到的文档放进去之后会格外重要。
2. **提示词、token、上下文窗口。** 提示词(prompt)不过是把消息列表渲染成
   文本；token 则是 provider 用来衡量成本和上下文窗口预算的单位。
   `FakeLLMClient` 按大约每4个字符1个 token 来估算——用来推算预算够用，但
   作为真正的分词器(tokenizer)则是错的(第15集会为了真正的成本追踪重新
   讨论这一点)。
3. **温度(Temperature)。** `complete(..., temperature=0.2)`——对于一个应当
   始终依据证据一致作答、而不是随意发散的支持类 copilot 来说，低温度是合理
   的选择。
4. **Provider API。** `OpenAICompatibleClient` 直接说原始 HTTP
   (`POST /chat/completions`)，而不是包一层厂商 SDK，因为 Ollama、
   LM Studio 和 vLLM 在"OpenAI 兼容"模式下暴露的正是同一种形状——以后要换
   provider，改的只是一个 `base_url` 和一个 `model`，不需要重写。
5. **超时与重试。** 真实客户端在超时时会重试一次，再失败就抛出一个清晰的
   `LLMTimeoutError`；而 HTTP 错误状态(密钥错误、模型错误)*不会*被重试，
   因为把一个 401 重试五次，只会浪费五次超时的时间，去确认第一次尝试就已经
   告诉你的结论。
6. **Provider 抽象。** `LLMClient` 是一个只有一个方法的 ABC。这个代码库里
   其他任何地方都不允许导入 `httpx`，也不允许知道"OpenAI 兼容"是什么
   意思——这些知识只留在 `llm/` 内部。

## 实现

- [`src/saas_copilot/llm/base.py`](../../src/saas_copilot/llm/base.py) — `Message`、
  `Usage`、`LLMResponse`、`LLMError`、`LLMTimeoutError`、`LLMClient`。
- [`src/saas_copilot/llm/fake.py`](../../src/saas_copilot/llm/fake.py) — `FakeLLMClient`。
- [`src/saas_copilot/llm/openai_compatible.py`](../../src/saas_copilot/llm/openai_compatible.py) — `OpenAICompatibleClient`。
- [`src/saas_copilot/llm/__init__.py`](../../src/saas_copilot/llm/__init__.py) — `build_llm_client(settings)`。
- 配置：在 `.env.example` 和 `Settings` 中加入 `LLM_BASE_URL` / `LLM_MODEL`。

## 运行

```bash
pytest tests/unit/test_llm.py -v
```

指向一个真实的 provider(可选，需要一个 key)：

```bash
export LLM_PROVIDER=openai LLM_API_KEY=sk-...
python -c "
from saas_copilot.config import settings
from saas_copilot.llm import build_llm_client
from saas_copilot.llm.base import Message
client = build_llm_client(settings)
print(client.complete([Message(role='user', content='Say hi in five words.')]).content)
"
```

## 失败案例(现场演示)

`tests/unit/test_llm.py` 用 `httpx.MockTransport` 来代替真正的 provider，
*完全不接触网络*就证明了两条失败路径：

- `test_openai_compatible_client_retries_on_timeout_then_succeeds` ——第一次
  调用超时，第二次成功，调用方完全感知不到这次失败。
- `test_openai_compatible_client_raises_llm_timeout_error_after_exhausting_retries`
  ——每一次调用都超时 → 得到一个干净的 `LLMTimeoutError`，而不是一个原始的
  `httpx` 异常从抽象层里泄漏出来。
- `test_openai_compatible_client_raises_llm_error_on_http_status_error` ——401
  会立即抛出异常，不会重试。

## 练习

给 `LLMClient.complete()` 加一个 `max_tokens: int | None = None` 参数。把它
接入 `OpenAICompatibleClient` 的 payload 中(仅当它不是 `None` 时)；让
`FakeLLMClient` 接受这个参数但忽略它。为每个客户端各写一条测试，证明签名的
改动没有破坏任何一种实现。这就是扩展一个接口时反复出现的模式：每一种实现都
必须保持一致，并且要有一条测试来证明这一点。

## 下一步

第3集会把 `LLMClient` 的输出包装成一个经过校验的、带类型的 `Answer`——并且
会准确展示，为什么一个"客气地要求返回 JSON"的系统提示词，并不等同于一份
保证。
