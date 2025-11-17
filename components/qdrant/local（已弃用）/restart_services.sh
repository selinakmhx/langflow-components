#!/bin/bash

# 这是一个一键重启 Qdrant 和 ngrok 服务的脚本（不带 API Key 版本）
# 目标：移除 Qdrant 的 API Key 要求，确保通过 ngrok 公网地址可以直接访问 Dashboard 和 API。

set -e

echo "🚀 开始执行一键重启脚本（无 API Key）..."

# --- 第0步：依赖检查（可选） ---
if ! command -v docker >/dev/null 2>&1; then
  echo "❌ 未检测到 Docker，请先安装 Docker 再运行本脚本。"
  exit 1
fi
if ! command -v ngrok >/dev/null 2>&1; then
  echo "❌ 未检测到 ngrok，请先安装并配置 authtoken（已在 ngrok.yml 中）再运行本脚本。"
  exit 1
fi

# --- 第1步：彻底终止旧进程 ---
echo "🛑 正在停止旧的 Qdrant (Docker) 容器 和 ngrok 进程..."
# 优先按容器名停止，避免误杀
if docker ps -a --format '{{.Names}}' | grep -q '^qdrant_local$'; then
  docker rm -f qdrant_local >/dev/null 2>&1 || true
fi
# 如果之前存在使用默认名称或任意名称的 qdrant/qdrant 容器，一并清理
OLD_QDRANT_CONTAINERS=$(docker ps -q --filter "ancestor=qdrant/qdrant")
if [ -n "${OLD_QDRANT_CONTAINERS}" ]; then
  docker rm -f ${OLD_QDRANT_CONTAINERS} >/dev/null 2>&1 || true
fi
# 同时尝试杀掉可能遗留的 ngrok 进程
pkill -f "ngrok" >/dev/null 2>&1 || true
killall ngrok >/dev/null 2>&1 || true

# 等待片刻确保进程已终止
sleep 2

echo "✅ 旧进程清理完毕。"
echo "---"

# --- 第2步：启动 Qdrant（不带 API Key） ---
echo "🐳 正在启动 Qdrant Docker 容器（无 API Key）..."
CONTAINER_ID=$(docker run -d --name qdrant_local -p 6333:6333 qdrant/qdrant)
if [ -z "$CONTAINER_ID" ]; then
  echo "❌ 启动 Qdrant 容器失败，请检查 Docker 环境。"
  exit 1
fi
# 将容器日志流式写入 qdrant.log，方便排查
(docker logs -f qdrant_local 2>&1 | sed -u 's/^/[QDRANT] /') > qdrant.log 2>&1 &

# 等待几秒钟让 Qdrant 服务有足够的时间启动
sleep 5

echo "✅ Qdrant 服务已启动。日志请查看 qdrant.log"
echo "---"

# --- 第3步：按配置文件启动 ngrok（更稳定） ---
echo "🔗 正在后台启动 ngrok（使用 ./ngrok.yml 配置）..."
# 使用配置文件中的 authtoken 与隧道定义，输出日志到 ngrok.log
nohup ngrok start --config ./ngrok.yml qdrant --log=stdout > ngrok.log 2>&1 &

# 等待几秒钟让 ngrok 建立连接
sleep 5

echo "✅ ngrok 服务已在后台启动。"
echo "---"

# --- 第4步：获取并显示新的 URL ---
echo "🌐 正在获取新的公共 URL..."

# 优先使用 jq 解析，如果没有 jq，尝试使用 sed 简单提取
if command -v jq >/dev/null 2>&1; then
  NEW_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | jq -r ".tunnels[0].public_url")
else
  NEW_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | sed -n 's/.*"public_url":"\([^"]\+\)".*/\1/p' | head -n 1)
fi

# 如果通过 ngrok.yml 启动未取到 URL，则回退到命令行方式
if [ -z "${NEW_URL:-}" ] || [ "$NEW_URL" = "null" ]; then
  echo "⚠️ 未从 ngrok 本地 API 获取到 URL，尝试回退启动方式..."
  pkill -f "ngrok" >/dev/null 2>&1 || true
  nohup ngrok http 6333 --host-header=rewrite --log=stdout > ngrok.log 2>&1 &
  sleep 5
  if command -v jq >/dev/null 2>&1; then
    NEW_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | jq -r ".tunnels[0].public_url")
  else
    NEW_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | sed -n 's/.*"public_url":"\([^"]\+\)".*/\1/p' | head -n 1)
  fi
fi

if [ -z "${NEW_URL:-}" ] || [ "$NEW_URL" = "null" ]; then
    echo "❌ 获取新 URL 失败。请手动运行 'curl -s http://127.0.0.1:4040/api/tunnels' 检查，并查看 ngrok.log。"
    exit 1
else
    echo "🎉 成功！你的新公共访问地址是: $NEW_URL"
    echo "你可以通过访问 $NEW_URL/dashboard 来查看 Qdrant 的 Web UI。"
fi

echo "---"

# --- 第5步：健康检查与提示 ---
echo "🩺 正在执行健康检查..."
HTTP_CODE_DASHBOARD=$(curl -s -o /dev/null -w "%{http_code}" "$NEW_URL/dashboard")
HTTP_CODE_COLLECTIONS=$(curl -s -o /dev/null -w "%{http_code}" "$NEW_URL/collections")
echo "Dashboard 响应码: $HTTP_CODE_DASHBOARD"
echo "Collections 响应码: $HTTP_CODE_COLLECTIONS"

if [ "$HTTP_CODE_DASHBOARD" != "200" ]; then
  echo "⚠️ Dashboard 非 200（$HTTP_CODE_DASHBOARD），请检查 ngrok.log 与浏览器控制台的网络错误。"
fi
if [ "$HTTP_CODE_COLLECTIONS" != "200" ]; then
  echo "⚠️ /collections 非 200（$HTTP_CODE_COLLECTIONS）。如果是 401/403，极有可能仍在使用旧容器（带 API Key）。建议再次执行本脚本或手动清理所有 qdrant/qdrant 容器后重试。"
fi

echo "✨ 脚本执行完毕！"