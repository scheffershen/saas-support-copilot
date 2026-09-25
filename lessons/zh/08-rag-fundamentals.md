# 第8集 — RAG 基础

**画面：** 第5集中 `search_docs` 用原始词频给查询打分的画面，紧挨着同一个
查询即将改用 BM25 + 嵌入(embeddings)的过程。

## 学习目标

检索增强生成(RAG)实际上是四个具体的步骤，而不是一次库的导入：把文本切分
成足够小、足够有用的片段；把每个片段转化为可以与查询进行比较的东西；根据
这种比较结果进行排序；当多种排序方法意见不一致时，把它们结合起来。把这四
步从零实现一遍，"RAG" 就不再是一个黑盒子。

## 讲解要点

1. **摄取与归一化。** `normalize_text()` 会在其他任何处理触碰文本之前，
   先修正换行符、去掉 Markdown 标题标记——处理的是版式，而不是内容。这一
   步很小，但它是糟糕的输入悄悄变成糟糕检索结果的第一个环节。
2. **分块(Chunking)。** 采用带重叠的固定大小分块(`chunk_text()`)。分块
   太大，真正的答案会被无关的周边文本稀释；分块太小，又会丢失上下文；
   重叠部分则可以防止跨越分块边界的句子被硬生生切成两半。
   `getting-started.md` 是 Loopline 文档中最长的一篇，在本课程 300 字符
   的切分大小下，真的会被拆成 2 个分块——这不是一个刻意编造的例子。
3. **BM25 全文搜索。** `BM25Index` 是一个真正从零实现的 Okapi BM25，而
   不是一次库调用：它考虑了词频饱和(一个词第10次出现的重要性远不如第1
   次)和长度归一化(一篇长文档并不会仅仅因为词更多就更相关)——这正是
   第5集里那种朴素词频打分方式做错的两件事。
4. **嵌入(Embeddings)。** `EmbeddingClient` 是第2集 `LLMClient` 模式在
   一个新问题上的再次应用——依赖的是"某个可以把文本变成嵌入向量的东西"，
   而不是某个具体的服务商。`HashingEmbeddingClient` 是本课程的默认实现：
   确定性、离线运行，和 `FakeLLMClient` 秉持同样的理念。它把向量搜索的
   *机制*做对了，但没有真正的语义理解能力——这是一个真实存在的缺陷，被
   明确写出来，而不是被藏起来。
5. **重排序(Reranking) / 混合搜索。** BM25 的分数和余弦相似度处在两个
   无法比较的量纲上，因此 `reciprocal_rank_fusion()` 结合的是*排名*，
   而不是原始分数——这与 Elasticsearch 混合搜索所使用的技术是同一套。
6. **引用(Citations)。** `Document.citation` 现在有了实际意义：
   `docs/getting-started.md#chunk-0` 和 `#chunk-1` 是同一份文件中真正
   不同的、可以被单独检索到的片段。

## 构建过程中发现的两个真实 bug

和第5集遵循同样的原则：两个 bug 都不是刻意设计的，都是在运行测试时暴露
出来的。

**一个停用词导致的假阳性。** 用查询 `"xyzzy-not-a-real-term"` 测试"无
匹配"场景时，却产生了一个匹配结果——而且还不是一个低置信度的匹配。它里
面的 "not" 和 "a" 与散落在每篇文档里的常见词发生了哈希碰撞，导致它与一篇
毫不相关的文章之间的语义相似度，反而*高于*一个真实查询与正确文档匹配时
的相似度。修复方式是在 `HashingEmbeddingClient` 的分词器里加入一个简短
的停用词列表。

**停用词过滤没能修复的更深层 bug。** 即便换成真正的乱码
(`"zzqvxlpfmnbwortkugh"`，与任何内容都不共享词汇)，`search_hybrid` 仍然
会返回结果。`_semantic_ranking` 根本没有设置任何相关性下限——它会按余弦
相似度给*每一个*分块排序，包括那些相似度恰好为 `0.0` 的分块。这样的语义
"搜索"永远只能对整个语料库重新排序，却从来无法真正地"什么都找不到"。
修复方式是在排序*之前*(而不是之后)设置一个 `min_similarity` 下限
(`DEFAULT_MIN_SIMILARITY = 0.05`)。

## 实现

- [`src/saas_copilot/retrieval/normalize.py`](../../src/saas_copilot/retrieval/normalize.py) — `normalize_text`。
- [`src/saas_copilot/retrieval/chunking.py`](../../src/saas_copilot/retrieval/chunking.py) — `chunk_text`。
- [`src/saas_copilot/retrieval/bm25.py`](../../src/saas_copilot/retrieval/bm25.py) — `BM25Index`。
- [`src/saas_copilot/retrieval/embeddings.py`](../../src/saas_copilot/retrieval/embeddings.py) — `EmbeddingClient`、`cosine_similarity`。
- [`src/saas_copilot/retrieval/hashing_embeddings.py`](../../src/saas_copilot/retrieval/hashing_embeddings.py) — `HashingEmbeddingClient`。
- [`src/saas_copilot/retrieval/rrf.py`](../../src/saas_copilot/retrieval/rrf.py) — `reciprocal_rank_fusion`。
- [`src/saas_copilot/retrieval/index.py`](../../src/saas_copilot/retrieval/index.py) — `DocumentIndex`。
- [`src/saas_copilot/tools/docs.py`](../../src/saas_copilot/tools/docs.py) / [`tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — `search_docs` 被改接到索引之上。
- [`src/saas_copilot/models.py`](../../src/saas_copilot/models.py) — `Document.citation` 现在总是包含分块后缀(参见第1集的说明)。

## 运行

```bash
pytest tests/unit/test_retrieval_normalize.py tests/unit/test_retrieval_chunking.py \
       tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_embeddings.py \
       tests/unit/test_retrieval_rrf.py tests/unit/test_retrieval_index.py \
       tests/unit/test_tools_docs.py -v
```

## 失败案例(真实案例，来自本集自身的开发过程)

```pycon
>>> len(index)   # 5 docs, 7 chunks - getting-started.md and roles-and-permissions.md each split in two
7
>>> index.search_semantic("zzqvxlpfmnbwortkugh", min_similarity=-1.0)   # the old, floor-less behavior
[<all 7 chunks, "ranked" at exactly 0.0 similarity>]
>>> index.search_semantic("zzqvxlpfmnbwortkugh")   # today's default floor
[]
```

一个没有下限的"排序"根本算不上搜索。它只是对那些一开始就从未成为候选项
的东西，给出的一种排列意见罢了。

## 练习

`DEFAULT_MIN_SIMILARITY = 0.05` 是通过观察这个特定语料库的具体数字选出
来的，并不是从某种原则推导而来——这正是那种真实系统会用数据来校准、而不
是靠肉眼估计的"魔法数字"。请构建一个小型的"是否匹配"评测集(覆盖
Loopline 文档、5-10 对查询/预期文档)，并针对它扫描若干个阈值，挑出最能
把真实匹配和噪声区分开的那一个。(这是第15集的完整预览——这里只是把同一
个想法放在尽可能小的规模上先做一遍。)

## 下一步

第9集会在此基础上加入第二种检索范式：一个针对 Loopline 自身源码的轻量级
调用图，用来回答那些文本搜索回答不好的问题(比如"修改这个函数会影响到
什么？")。
