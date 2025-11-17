# Qdrant 本地部署及使用攻略

你好！恭喜你成功在本地部署了 Qdrant！

这份攻略将指导你如何通过命令行（主要是 `curl`）与你的 Qdrant 实例进行交互，以及如何将你的本地服务分享给同事访问。

## 1. 通过 `curl` 进行基本操作

Qdrant 提供了丰富的 REST API，让我们可以通过 `curl` 这样的工具轻松地管理数据。你的 Qdrant 服务正在本地的 `6333` 端口上运行。

### 1.1 创建一个集合（Collection）

集合是 Qdrant 中存储向量和负载（payload）的基本单位。我们来创建一个名为 `my_first_collection` 的集合，用来存储4维向量。

```bash
curl -X PUT http://localhost:6333/collections/my_first_collection \
    -H 'Content-Type: application/json' \
    --data-raw '{
        "vectors": {
            "size": 4,
            "distance": "Cosine"
        }
    }'
```

**参数解释:**
*   `vectors.size`: 向量的维度。
*   `vectors.distance`: 计算向量相似度的距离函数，这里我们使用余弦相似度（Cosine）。

### 1.2 插入数据点（Points）

现在，我们向 `my_first_collection` 集合中插入一些数据点。每个数据点都包含一个唯一的 `id`、一个向量 `vector` 和一个可选的 `payload`。

```bash
curl -X PUT http://localhost:6333/collections/my_first_collection/points?wait=true \
    -H 'Content-Type: application/json' \
    --data-raw '{
        "points": [
            {"id": 1, "vector": [0.05, 0.61, 0.76, 0.74], "payload": {"color": "red"}},
            {"id": 2, "vector": [0.19, 0.81, 0.75, 0.11], "payload": {"color": "red"}},
            {"id": 3, "vector": [0.36, 0.55, 0.47, 0.94], "payload": {"color": "blue"}}
        ]
    }'
```

**参数解释:**
*   `wait=true`: 表示操作将等待所有更改被应用后再返回结果。

### 1.3 检索数据点

我们可以通过 ID 来检索刚刚插入的数据点。

```bash
curl -X POST http://localhost:6333/collections/my_first_collection/points \
    -H 'Content-Type: application/json' \
    --data-raw '{
        "ids": [1, 3]
    }'
```

### 1.4 相似性搜索

这是 Qdrant 最核心的功能。我们可以提供一个查询向量，Qdrant 会返回集合中最相似的数据点。

```bash
curl -X POST http://localhost:6333/collections/my_first_collection/points/search \
    -H 'Content-Type: application/json' \
    --data-raw '{
        "vector": [0.2, 0.1, 0.9, 0.7],
        "limit": 2
    }'
```

**参数解释:**
*   `vector`: 用于查询的向量。
*   `limit`: 返回最相似结果的数量。

### 1.5 使用过滤器（Filter）进行搜索

我们可以在搜索时加入过滤条件，只在满足条件的数据点中进行相似性搜索。例如，我们只搜索 `color` 为 `red` 的数据点。

```bash
curl -X POST http://localhost:6333/collections/my_first_collection/points/search \
    -H 'Content-Type: application/json' \
    --data-raw '{
        "vector": [0.2, 0.1, 0.9, 0.7],
        "limit": 2,
        "filter": {
            "must": [
                {
                    "key": "color",
                    "match": {
                        "value": "red"
                    }
                }
            ]
        }
    }'
```

## 2. 让同事访问你的本地 Qdrant 服务

要让你局域网之外的同事能够访问你本地运行的 Qdrant 服务，你需要一个叫做“隧道”的工具。这里我们推荐使用 `ngrok`。

### 2.1 安装 `ngrok`

你可以从 `ngrok` 的官网下载并安装它。对于 macOS，你可以使用 Homebrew 来安装：

```bash
brew install ngrok/ngrok/ngrok
```

### 2.2 获取你的 `ngrok` Authtoken

你需要注册一个 `ngrok` 账号来获取一个 Authtoken。登录后，你可以在你的 `ngrok` 仪表板上找到你的 Authtoken。

然后，在你的终端运行以下命令来配置你的 Authtoken：

```bash
ngrok config add-authtoken <YOUR_AUTHTOKEN>
```

### 2.3 启动 `ngrok` 隧道

现在，你可以使用 `ngrok` 来为你本地的 Qdrant 服务创建一个公共的 URL。因为 Qdrant 运行在 `6333` 端口，所以你需要运行以下命令：

```bash
ngrok http 6333
```

命令成功运行后，`ngrok` 会显示一个 `Forwarding` 地址，看起来像这样：

```
Forwarding                    https://<random-string>.ngrok-free.app -> http://localhost:6333
```

### 2.4 分享你的 Qdrant 服务

现在，你的同事就可以通过这个 `https://<random-string>.ngrok-free.app` 地址来访问你的 Qdrant 服务了！

例如，他们可以像这样向你的 Qdrant 发送请求：

```bash
curl -X GET https://<random-string>.ngrok-free.app/collections
```

---

希望这份攻略对你有帮助！现在你可以开始探索 Qdrant 的强大功能了。如果你有任何问题，随时都可以问我！