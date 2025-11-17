# Qdrant 进阶指南：从表格数据到向量搜索

你好！这份进阶指南将专注于解决一个核心问题：如何将你的结构化数据（例如表格、数据库记录）转换成向量，并存储到 Qdrant 中以实现语义搜索。这补充了我们之前创建的 `Qdrant_usage_guide.md` 的内容。

## 核心流程：三步走

正如我们之前讨论的，Qdrant 本身不负责生成向量，它是一个专业的“向量保管员和检索员”。要让 Qdrant 理解你的数据，我们需要一个“翻译官”——也就是**嵌入模型（Embedding Model）**——来将文本信息转换成数学向量。整个流程可以分为三步：

1.  **文本化**：从你的表格数据中，挑选出需要被搜索的关键信息列（比如“产品名称”、“描述”、“用户评论”等），并将它们组合成有意义的文本段落。
2.  **向量化**：使用一个强大的嵌入模型，将这些文本段落转换成高维向量。
3.  **存储与索引**：将生成的向量，连同原始数据中的其他信息（如 `product_id`）作为 `payload`，一起存储到 Qdrant 的集合（Collection）中。

---

## 1. 选择合适的中文嵌入模型（“翻译官”）

对于处理中文文本，选择一个高质量的嵌入模型至关重要。一个好的模型能更准确地理解中文的语义和细微差别。

**推荐模型：BAAI/bge-large-zh-v1.5**

-   **为什么推荐它？** 这是由北京智源人工智能研究院（BAAI）开发的模型，在 C-MTEB（一个权威的中文文本嵌入评测基准）上表现顶尖，是目前开源社区公认的、效果最好的中文嵌入模型之一。
-   **备选模型：** `jinaai/jina-embeddings-v2-base-zh` 也是一个非常不错的选择，它支持中英双语，并且能处理更长的文本输入。

在接下来的示例中，我们将使用 `bge-large-zh-v1.5`。

---

## 2. Python 代码实战：从 Pandas 到 Qdrant

下面的 Python 脚本为你提供了一个完整的端到端示例。它演示了如何加载一个 Pandas DataFrame，使用 `bge-large-zh-v1.5` 模型生成向量，并将它们存入 Qdrant，最后进行一次相似度搜索。

你可以在本地创建一个名为 `qdrant_embedding_example.py` 的文件，并将以下代码复制进去。我们之前已经创建过这个文件了，这里再次列出以保持文档的完整性。

```python
# 1. 安装必要的库
# 首先，请确保你已经安装了这些库。如果尚未安装，请在终端中运行以下命令：
# pip install sentence-transformers qdrant-client pandas torch

import torch
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models
import pandas as pd

# 2. 准备数据
# 假设我们有这样一个包含产品信息的DataFrame。
data = {
    'product_id': ['P001', 'P002', 'P003', 'P004'],
    'product_name': ['智能降噪耳机', '便携式咖啡机', '无线机械键盘', '高清运动相机'],
    'description': [
        '提供卓越的音质和主动降噪功能，让您沉浸在纯净的音乐世界。',
        '随时随地享受一杯香醇的现磨咖啡，小巧轻便，是旅行和办公室的理想选择。',
        '采用高品质机械轴体，提供出色的打字手感和响应速度，支持蓝牙和有线双模连接。',
        '记录您每一次的冒险瞬间，支持4K视频录制和超广角拍摄，防水防抖。'
    ]
}
df = pd.DataFrame(data)

print("原始数据:")
print(df)
print("-" * 30)

# 3. 初始化嵌入模型
print("正在加载嵌入模型 (bge-large-zh-v1.5)...")
device = 'cuda' if torch.cuda.is_available() else 'cpu'
embedding_model = SentenceTransformer('BAAI/bge-large-zh-v1.5', device=device)
print("模型加载完毕！")
print("-" * 30)

# 4. 将文本数据转换为向量
texts_to_embed = (df['product_name'] + "：" + df['description']).tolist()

print("正在生成文本向量...")
embeddings = embedding_model.encode(texts_to_embed, normalize_embeddings=True)
print(f"向量生成完毕！生成了 {len(embeddings)} 个向量。")
print("-" * 30)

# 5. 初始化 Qdrant 客户端并存储数据
qdrant_client = QdrantClient("http://localhost:6333")
collection_name = "my_products"
vector_size = embeddings.shape[1]

try:
    qdrant_client.get_collection(collection_name=collection_name)
    print(f"集合 '{collection_name}' 已存在。")
except Exception:
    print(f"集合 '{collection_name}' 不存在，正在创建...")
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
    )
    print("集合创建成功！")

# 准备并上传数据点
points_to_upsert = [
    models.PointStruct(
        id=i,
        vector=embeddings[i].tolist(),
        payload={
            "product_id": row['product_id'],
            "product_name": row['product_name']
        }
    )
    for i, row in df.iterrows()
]

qdrant_client.upsert(
    collection_name=collection_name,
    points=points_to_upsert,
    wait=True
)

print(f"成功将 {len(points_to_upsert)} 个数据点存入集合 '{collection_name}'！")
print("-" * 30)

# 6. 进行相似度搜索
print("正在进行相似度搜索...")
query_text = "适合户外运动的相机"
query_vector = embedding_model.encode(query_text, normalize_embeddings=True).tolist()

search_results = qdrant_client.search(
    collection_name=collection_name,
    query_vector=query_vector,
    limit=3
)

print(f"对于查询 '{query_text}'，找到以下最相关的产品：")
for result in search_results:
    print(f"  - 产品ID: {result.payload['product_id']}, "
          f"产品名称: {result.payload['product_name']}, "
          f"相似度得分: {result.score:.4f}")
```

### 如何运行代码

1.  **打开终端**。
2.  **进入项目目录**：`cd /Users/macmima1234/code/components/components/atol`
3.  **安装依赖**：`pip install sentence-transformers qdrant-client pandas torch`
4.  **运行脚本**：`python qdrant_embedding_example.py`

当你运行脚本后，你将会在终端看到整个流程的输出，从加载数据到最后的搜索结果。最后的搜索结果应该会告诉你，“高清运动相机”是与“适合户外运动的相机”最相关的产品，这证明了我们整个流程的有效性。

---

## 总结

通过这份指南，你应该已经掌握了将你自己的数据导入 Qdrant 的核心技术。关键在于**选择一个好的嵌入模型**，并**构建一个清晰的数据处理管道**。现在，你可以尝试用你自己的表格数据来替换示例中的数据，开始构建你自己的语义搜索应用了！

如果你有任何问题，随时都可以再问我。祝你探索愉快！