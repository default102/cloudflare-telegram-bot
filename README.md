# Cloudflare DNS Telegram 机器人

这是一个基于 Python 的 Telegram 机器人，用于方便地管理 Cloudflare DNS 记录。支持 Docker 部署和 GitHub Actions 自动构建。

## 功能特性

*   🔒 **安全认证**: 仅允许指定的 Telegram 用户 ID 操作。
*   🌐 **域名列表**: 列出账号下所有 Cloudflare 域名 (Zones)。
*   📝 **记录管理**:
    *   查看所有 DNS 记录 (A, CNAME, TXT, AAAA)。
    *   可视化图标显示代理状态 (☁️ Proxied / 🛡️ DNS Only)。
    *   **添加记录**: 向导式添加新记录。
    *   **编辑记录**: 修改记录内容 (IP/Hostname)。
    *   **切换代理**: 一键开启/关闭 Cloudflare 代理 (小黄云)。
    *   **删除记录**: 确认后删除。
*   🇨🇳 **全中文界面**: 友好的中文交互体验。

## 快速开始

### 1. 准备工作

你需要获取以下信息：
*   **Telegram Bot Token**: 从 [@BotFather](https://t.me/BotFather) 创建机器人获取。
*   **Allowed User ID**: 你自己的 Telegram 数字 ID (可以从 [@userinfobot](https://t.me/userinfobot) 获取)。
*   **Cloudflare API Token**: 在 Cloudflare Dashboard -> My Profile -> API Tokens 创建。
    *   **权限**: `Zone.Zone:Read`, `Zone.DNS:Edit`

### 2. 本地运行 (Python)

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量并运行
export TG_TOKEN="你的BotToken"
export ALLOWED_USER_ID="你的数字ID"
export CF_API_TOKEN="你的CFToken"

python bot/main.py
```

### 3. Docker 部署

```bash
docker run -d --restart=always \
  --name cf-dns-bot \
  -e TG_TOKEN="你的BotToken" \
  -e ALLOWED_USER_ID="你的数字ID" \
  -e CF_API_TOKEN="你的CFToken" \
  ghcr.io/default102/cloudflare-telegram-bot:latest
```

(注：你需要先构建镜像或使用 GitHub Actions 自动构建的镜像)

## 自动构建 (GitHub Actions)

本项目包含 GitHub Actions 配置。只需将代码推送到 GitHub 仓库 [default102/cloudflare-telegram-bot](https://github.com/default102/cloudflare-telegram-bot)，它会自动构建 Docker 镜像并发布到 GitHub Container Registry (ghcr.io)。

1.  Push 代码到 GitHub。
2.  默认情况下，镜像会发布到 `ghcr.io/default102/cloudflare-telegram-bot:latest`。
3.  确保在 GitHub 仓库设置中开启了 Actions 权限。

## 项目结构

```
.
├── bot/
│   ├── cf_api.py    # Cloudflare API 封装
│   ├── config.py    # 配置管理
│   ├── handlers.py  # 机器人交互逻辑 (核心)
│   └── main.py      # 入口文件
├── Dockerfile       # Docker 构建文件
└── requirements.txt # Python 依赖
```