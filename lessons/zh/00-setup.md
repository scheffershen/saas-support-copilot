# 第0集 — 我们要构建什么

**画面：** 一个空的终端窗口，然后是 `git clone` 之后的这个仓库。

## 讲解要点

1. **模型 vs 应用 vs 智能体(agent)。** 模型负责预测文本。应用把模型包装在固定的
   逻辑中。智能体则会借助工具自行决定下一步做什么。本课程始终稳稳地停留在
   "读取信息、给出答案、引用来源"这一端，而不是"自主采取行动"的那一端。
2. **工作流(workflow) vs 智能体(agent)。** 我们构建的绝大部分内容都是一个确定性
   的工作流(分类 → 检索 → 回答)，其中只有一个针对功能可行性问题的、范围受限的
   规划步骤。我们会明确区分哪部分是哪种，因为"智能体"并不天然就比"工作流"更好。
3. **原型 vs 生产环境。** 这里的一切都在本地运行，没有身份验证，使用的是示例
   数据。第17集会完整列出一次真实部署还缺少什么——包括这样一条规则：在没有明确
   授权之前，这里的任何东西都不会触碰真实公司的代码或数据。
4. **本地优先的开发方式。** 跟着学习不需要付费的 API key——第2集会引入一个假的
   `LLMClient`，与一个真实的 provider adapter 并存。
5. **到底是谁在敲代码。** 这个仓库里的每一行代码，都是通过向 AI 编程智能体下达
   提示词(prompt)产生的，而不是手写实现出来的——从这里开始的每一课，教的正是
   让这件事成立所需要的那种知识：不是语法，而是为什么一个设计是正确的，以及
   如何验证它确实正确。等你对几集内容有了感觉之后，可以看看
   [`lessons/prompting-the-build.md`](prompting-the-build.md)——它讲的是整门
   课程，而不是课程中的某一步。

## 导览

- `sample_app/loopline/` ——这个虚构的工单类 SaaS，正是 copilot 将要回答相关
  问题的对象。走一遍 `docs/`、`app/models.py`、`schema.sql` 和 `logs/app.log`。
- `src/saas_copilot/` ——copilot 本体。今天它还只有 `config.py` 和一个
  `/health` 端点；其余的一切都会随着课程一集一集地构建起来。
- 到目前为止的提交历史*本身就是*第一课：脚手架 → Loopline 的应用 →
  日志 → 文档 → 一次 bug 修复(`git log --oneline`) → 这一课。

## 动手实践

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env

python -m sample_app.loopline.app.seed
python -m uvicorn sample_app.loopline.app.main:app --reload --port 8001 &
curl http://localhost:8001/health

python -m uvicorn saas_copilot.api.main:app --reload --port 8000 &
curl http://localhost:8000/health

pytest
```

你应该会看到 3 个测试通过，以及 1 个 `xfail`——那是预先埋好的通知(notification)
bug，不是结账流程坏了。

## 练习

手动复现这个预先埋好的 bug：发送 `POST /tickets/4/comments`，请求体类似
`{"author_id": 2, "body": "test"}`。然后，不借助任何工具，找出抛出 `KeyError`
的确切源码行，以及缺失的那一条确切的种子数据(seed row)。这正是 copilot 之后
需要产出的每一个答案的基本形态：一个论断，加上一条引用。第6集会构建出能自动
完成这件事的工具。

## 下一步

第1集会为 copilot 自身的代码引入带类型的模型(models)，并配上一套真正的测试
套件。
