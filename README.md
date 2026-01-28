# Chat Work

通过聊天就能工作 - AI 对话 + 执行命令 + 代码生成

## 功能

- 🤖 **AI 对话**: 基于 Claude 的智能对话
- ⚡ **执行命令**: 通过对话执行 shell 命令
- 📝 **代码生成**: 通过对话生成和修改代码
- 📱 **多平台**: 支持 CLI、Web、飞书

## 快速开始

### 1. 安装依赖

```bash
cd chat_work
pip install -e .
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 3. 运行

**CLI 模式:**
```bash
chat_work chat
# 或
python -m app.cli chat
```

**Web 模式:**
```bash
chat_work serve
# 或
python -m app.cli serve

# 访问 http://localhost:8000
```

**单条消息:**
```bash
chat_work ask "帮我查看当前目录的文件"
```

## CLI 命令

```bash
chat_work chat          # 交互式聊天
chat_work chat --auto   # 自动执行命令模式
chat_work ask "消息"    # 发送单条消息
chat_work serve         # 启动 Web 服务器
chat_work serve -p 3000 # 指定端口
```

## 对话中的命令

- `/clear` - 清除对话历史
- `/auto` - 切换自动执行模式
- `/exit` - 退出程序
- `/help` - 显示帮助

## 飞书接入

1. 在[飞书开放平台](https://open.feishu.cn)创建应用
2. 添加机器人能力
3. 配置 `.env` 中的飞书参数
4. 启动服务: `chat_work serve`
5. 使用内网穿透暴露服务（如 Tailscale Funnel）
6. 在飞书配置事件订阅 URL: `https://your-domain/webhook/feishu`

## API

- `POST /api/chat` - 发送消息
- `POST /api/execute` - 执行操作
- `POST /api/clear` - 清除会话
- `WebSocket /ws/chat` - WebSocket 聊天
- `POST /webhook/feishu` - 飞书 Webhook

## 安全配置

在 `.env` 中配置:

```bash
# 允许执行命令的目录
ALLOWED_DIRS=/Users/xxx/projects,/tmp

# 禁止执行的命令
BLOCKED_COMMANDS=rm -rf /,sudo rm,mkfs
```

## 项目结构

```
chat_work/
├── app/
│   ├── api/          # API 路由
│   ├── platforms/    # 平台接入（飞书等）
│   ├── services/     # 核心服务
│   ├── cli.py        # CLI 入口
│   ├── config.py     # 配置
│   └── main.py       # FastAPI 应用
├── web/
│   └── static/       # Web 前端
├── tests/            # 测试
├── .env.example      # 环境变量示例
└── pyproject.toml    # 项目配置
```
