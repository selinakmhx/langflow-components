from qdrant_client import QdrantClient, models

# 1. 初始化 Qdrant 客户端
# 我们将使用一个内存中的 Qdrant 实例，这样就不需要运行一个单独的服务。
# 这对于快速测试和原型设计非常方便。
print("正在初始化 Qdrant 客户端 (内存模式)...")
client = QdrantClient(host="localhost", port=6333, api_key="timisukmhx")
print("客户端初始化完毕！")
print("-" * 30)

# 2. 创建一个集合 (Collection)
# 集合是用来存储向量的地方，类似于数据库中的表。
collection_name = "my_minimal_collection"
vector_size = 4  # 我们将使用4维的向量作为示例

print(f"正在创建 Qdrant 集合 '{collection_name}'...")
try:
    # recreate_collection 会在每次运行时都重新创建集合，确保环境干净。
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.DOT) # 使用点积作为距离度量
    )
    print("集合创建成功！")
except Exception as e:
    print(f"创建集合时出错: {e}")
print("-" * 30)

# 3. 上传数据点 (Points)
# 我们将手动创建一些向量和它们的元数据 (payload)。
print("正在上传向量和元数据到 Qdrant...")
client.upload_points(
    collection_name=collection_name,
    points=[
        models.PointStruct(id=1, vector=[0.9, 0.1, 0.1, 0.2], payload={"color": "red"}),
        models.PointStruct(id=2, vector=[0.1, 0.9, 0.1, 0.1], payload={"color": "green"}),
        models.PointStruct(id=3, vector=[0.1, 0.1, 0.9, 0.1], payload={"color": "blue"}),
        models.PointStruct(id=4, vector=[0.8, 0.2, 0.3, 0.4], payload={"color": "red"}),
        models.PointStruct(id=5, vector=[0.2, 0.8, 0.2, 0.3], payload={"color": "green"}),
    ],
    wait=True # 等待操作完成
)
print("数据上传成功！")
print("-" * 30)

# 4. 执行相似度搜索
# 现在，让我们用一个查询向量来搜索最相似的数据点。
query_vector = [0.85, 0.15, 0.1, 0.1]
print(f"使用查询向量: {query_vector} 进行搜索...")

search_results = client.search(
    collection_name=collection_name,
    query_vector=query_vector,
    limit=3  # 返回最相似的3个结果
)

print("\n搜索结果:")
if not search_results:
    print("没有找到相似的结果。")
else:
    for result in search_results:
        print(f"  - ID: {result.id}")
        print(f"    Payload: {result.payload}")
        print(f"    相似度得分: {result.score:.4f}")

print("\nQdrant 最小示例执行完毕！")