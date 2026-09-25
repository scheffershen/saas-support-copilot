# 第16集——本地部署与可复现性

**画面：** `POST /ask`——「你能否根据真实数据确认一下，这个受理人在 notification_settings 表里是否有对应的一行？」——得到了正确答复，引用了 `query_database`，并针对**真实的 MySQL 数据**完成了根因定位，而这一切都是通过本集从零搭建的、**真实且独立的 MCP 服务器进程**实现的。

## 学习目标

迄今为止的每一集，`query_database` 面对的都是 SQLite——一个替身，而且始终被明确地称为替身。本集为它接通了一条真正通往 Loopline 实际目标数据库（MySQL）的路径，有两种可达方式——直接连接，以及通过一个独立的 MCP 服务器——再加上一个真实数据库依赖真正需要的部署脚手架：Docker Compose、绝不触碰源码控制的密钥、一次诚实限定范围的迁移，以及一个真正检查数据库是否在线、而不只是检查进程是否在跑的健康探针。

## 讲解要点

1. **Docker Compose 只管基础设施，不管整个应用。** `docker-compose.yml` 只运行 MySQL。copilot 依然原生运行（`uvicorn ...`，自第14集以来没变过）——这个项目依赖数据库，但不会被数据库反过来塑形。
2. **迁移，诚实地限定了范围。** `schema.sql` 和 `seed_data.sql` 通过 MySQL 自带的 `docker-entrypoint-initdb.d` 机制，针对一个全新的数据卷只运行一次——这就是本课程全部的"迁移故事"，而且被如实地称为这样：一个 schema 版本，应用一次，不是一个框架。以后如果要对 schema 做第二次*变更*，就需要一个真正的迁移框架（Alembic、Flyway）；目前只有一个版本，还配不上那个分量。
3. **只读边界，这次是 MySQL 原生实现的。** SQLite 的 `?mode=ro` 连接方式在 MySQL 里没有对应物——所以 `mysql-readonly-user.sh` 专门配置了一个 `loopline_reader` 用户，只授予 `GRANT SELECT`，别的什么都没有。现场验证过，而非凭空假设：以这个用户身份连接，执行一条真正的 `DELETE`——`ERROR 1142 (42000): DELETE command denied to user 'loopline_reader'@'localhost' for table 'users'`——MySQL 自身的权限系统直接拒绝了它，这和第12集靠一个连接标志得到的"无可辩驳"特性是同一种性质。
4. **三种后端，一个调度点。** `tools/__init__.py` 里的 `_query_database_handler()` 负责选择 SQLite（`tools/database.py`，未改动）、进程内 MySQL（`tools/database_mysql.py`），还是通过 MCP 的 MySQL（`tools/database_mcp.py`）——这个决定只在 `Settings` 那里做一次，绝不会是一个工具参数能选择的东西。`sql_safety.py` 的 `validate_select_only()` 被这三者共用（也被 MCP 服务器自己的工具函数共用）——是一处检查，而不是三份可能悄悄跑偏的副本。
5. **真正的 MCP 集成，不是挂个名字应付了事。** `mcp_server/server.py` 是一个货真价实、独立运行的 MCP 服务器（`mcp.server.fastmcp.FastMCP`），作为独立的操作系统进程启动，通过 stdio 通信——和 Claude Desktop 及其他真实 MCP 客户端用的是同一种传输方式。`tools/database_mcp.py` 里的客户端会真正完成握手（`ClientSession.initialize()`）、调用工具、再读回 `result.structuredContent["result"]`——这些行为都是先对照 SDK 的真实表现验证过，才写进本课程代码的，而不是从文档里想当然地假设出来的。
6. **每次调用都重新启动一个进程——这是一个明说出来的局限，不是藏起来的局限。** 没有连接池，没有持久化客户端。对一门课程来说简单且正确；一个真实系统会让会话在多次调用之间保持存活。这一点在 `database_mcp.py` 自己的 docstring 里，以及本集的练习里，都被明确点了出来。
7. **一个循环导入，在它上线之前就被抓住了。** `mcp_server/server.py` 需要 `tools.mysql_query`，这意味着导入它会初始化整个 `tools` 包——而这个包又需要 `database_mcp.py` 去注册 MCP 处理函数。如果 `database_mcp.py` 反过来从 `mcp_server` 导入了任何东西，那次导入就会卡在初始化过程中间失败。修复方式和第11集修复自己的循环导入时一样：把共享常量（`DATABASE_URL_ENV_VAR`）放到不会造成环路的那一侧，另一侧再从那里导入它。
8. **`env=` 是替换，不是合并——这是验证过的，不是假设出来的。** 要给启动的 MCP 服务器传一个自定义环境变量，得先从 SDK 自带的 `get_default_environment()`（PATH 以及其他几个变量）出发，再往上加——单独一个 `env={"MY_VAR": ...}` 会把子进程的整个环境替换掉，而一个没有 `PATH` 的 `python` 甚至可能启动不了。在写真正的客户端之前，先用一个一次性的探测服务器把这两个方向都验证了一遍。

## 实现

- [`docker-compose.yml`](../../docker-compose.yml) — 只运行 MySQL。
- [`sample_app/loopline/mysql-readonly-user.sh`](../../sample_app/loopline/mysql-readonly-user.sh) — 配置 `loopline_reader`。
- [`src/saas_copilot/tools/sql_safety.py`](../../src/saas_copilot/tools/sql_safety.py) — 抽取出来的、共享的"仅限 SELECT"检查。
- [`src/saas_copilot/tools/mysql_query.py`](../../src/saas_copilot/tools/mysql_query.py) — 共享的 MySQL 连接与查询逻辑，供两种 MySQL 后端共用。
- [`src/saas_copilot/tools/database_mysql.py`](../../src/saas_copilot/tools/database_mysql.py) — 进程内 MySQL 回退方案。
- [`src/saas_copilot/mcp_server/server.py`](../../src/saas_copilot/mcp_server/server.py) — 独立运行的 MCP 服务器。
- [`src/saas_copilot/tools/database_mcp.py`](../../src/saas_copilot/tools/database_mcp.py) — MCP 客户端。
- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — 三路调度逻辑。
- [`src/saas_copilot/api/routes.py`](../../src/saas_copilot/api/routes.py) — `/health` 现在会真正探测数据库。

## 运行

```bash
# SQLite (default, no Docker):
pytest tests/unit/test_tools_sql_safety.py -v

# MySQL + MCP (needs `docker compose up -d` and LOOPLINE_READONLY_DATABASE_URL set):
pytest tests/unit/test_tools_database_mysql.py tests/unit/test_tools_database_mcp.py \
       tests/unit/test_tools_default_registry.py -v
```

## 现场演示(经过验证的输出)

```bash
docker compose exec mysql mysql -uloopline_reader -p"$MYSQL_READER_PASSWORD" \
  -e "USE loopline; DELETE FROM users WHERE id=1;"
# ERROR 1142 (42000): DELETE command denied to user 'loopline_reader'@'localhost'
# for table 'users'
```

```bash
curl http://localhost:8000/health   # USE_DATABASE_MCP=true, real MySQL configured
# {"status":"ok","docs_indexed":13,"database":"ok"}

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d \
  '{"session_id": "demo16", "question": "a user reported that commenting on ticket 4
    crashes the server - can you confirm from the actual data whether the assignee
    has a notification_settings row?"}'
# {"domain":"bug","answer":"The assignee for ticket 4 does not have a corresponding
#  row in the notification_settings table, which may indicate that they are not set
#  up to receive notifications.","citations":["query_database"],"confidence":0.9,
#  "tools_called":["query_database"],"latency_ms":9657.0,"tokens_used":2820}
```

bug 专家模块自己主动调用了 `query_database`，而这次查询是通过一个真实、独立的 MCP 服务器进程，针对真实的 MySQL 执行的——不是 SQLite，也不是模拟。

## 失败案例(真实案例，在构建本集内容时现场发现)

完全相同的连接，只是 URL 里一个词不一样：

```pycon
>>> query_database_mysql("SELECT id FROM users LIMIT 1",
...     database_url="mysql+pymysql://loopline_reader:...@localhost:3306/loopline")
# took 5.094 s -> [{'id': 1}]

>>> query_database_mysql("SELECT id FROM users LIMIT 1",
...     database_url="mysql+pymysql://loopline_reader:...@127.0.0.1:3306/loopline")
# took 0.062 s -> [{'id': 1}]
```

在这套 Windows + Docker Desktop 环境下，`localhost` 首先解析到了一个没有任何服务监听的 IPv6 地址——pymysql 先耗时等待那次尝试超时，才回退到 IPv4。而 `127.0.0.1` 直接跳过了这个解析问题。两种连接方式最终都能到达同一个 MySQL 容器；只是其中一种要白白浪费真实的五秒钟才能找到它。修复方式是在 `.env.example` 里把 `127.0.0.1` 记录为推荐使用的主机地址，而不是让代码悄悄改写调用方传入的任何内容——一次让人意外、未经请求的改写，本身就是另一种 bug。

第二个、独立的发现，值得专门点出来，恰恰因为它太容易被悄悄掩盖：为了测试而在本机自己的本地 `.env` 里加上 `LOOPLINE_READONLY_DATABASE_URL`，结果弄坏了两个*早已交付*的第12集测试——`Settings()` 是全局读取 `.env` 的，而那些测试其实一直隐含地假定用的是 SQLite，只是从没有明说过。修复方式是把这个假设显式写出来（`Settings(loopline_readonly_database_url="")`），而不是靠"记得保持环境干净"——这和本集自己的 MySQL 测试所需要的"不依赖你控制不了的环境状态"是同一种特性（当那个变量未设置时，测试是被跳过，而不是失败）。

## 练习

`database_mcp.py` 在*每一次*调用时都会启动一个全新的服务器进程并完成一次完整的 MCP 握手——这被明确点明是本集"简单但并非最优"的选择。请添加一个持久化版本：写一个小类，只打开一次 `stdio_client`/`ClientSession`（例如作为一个在 `ToolRegistry` 整个生命周期内持有的上下文管理器），并在多次调用之间复用它。编写一个测试，证明通过持久化会话发起的第二次调用，要比今天这样两次调用 `query_database_via_mcp` 明显更快——并思考一下，如果服务器进程在两次调用之间挂掉了会发生什么，这是当前这个每次调用都重启的版本完全不用担心的问题。

## 下一步

第17集讲的是这个原型和一个生产系统之间的差距：SSO、RBAC/ABAC、租户隔离、网络边界、审计留存、队列、速率限制、备份、事件响应、成本，以及威胁建模——包括早在本课程第一次提交时就点明过的"把它指向某家真实公司代码库"这条边界。最终产出一份生产就绪检查清单。
