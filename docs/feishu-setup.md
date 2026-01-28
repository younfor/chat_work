# 飞书接入指南

本指南帮助你将 Chat Work 接入飞书，实现通过飞书对话调用本地 Claude。

## 架构说明

```
飞书用户发消息
       ↓
飞书服务器 (公网)
       ↓ Webhook 推送
内网穿透 (Tailscale Funnel / ngrok)
       ↓
你的本机 Chat Work 服务 (localhost:8000)
       ↓
调用本地 Claude CLI
       ↓
返回结果到飞书
```

---

## 第一步：创建飞书应用

### 1.1 登录飞书开放平台

访问 [飞书开放平台](https://open.feishu.cn/) 并登录。

### 1.2 创建应用

1. 点击「创建企业自建应用」
2. 填写应用信息：
   - 应用名称：`Chat Work` (或你喜欢的名字)
   - 应用描述：`AI 工作助手`
3. 点击「创建」

### 1.3 获取凭证

进入应用，在「凭证与基础信息」页面获取：

| 字段 | 说明 |
|------|------|
| **App ID** | 应用唯一标识 |
| **App Secret** | 应用密钥（点击查看） |

记下这两个值，后面要用。

---

## 第二步：配置应用能力

### 2.1 添加机器人能力

1. 左侧菜单：「应用能力」→「添加应用能力」
2. 选择「机器人」
3. 点击添加

### 2.2 配置权限

左侧菜单：「权限管理」，搜索并开启以下权限：

**必需权限：**
- `im:message` - 获取与发送单聊、群组消息
- `im:message:send_as_bot` - 以应用的身份发送消息
- `im:resource` - 获取消息中的资源文件（图片、文件等）

**可选权限（如需读取图片/文件）：**
- `im:message.content:readonly` - 读取消息内容

### 2.3 配置事件订阅

1. 左侧菜单：「事件订阅」
2. 添加事件：
   - `im.message.receive_v1` - 接收消息

**请求地址先留空**，第四步配置好内网穿透后再填。

---

## 第三步：配置本地服务

### 3.1 编辑 .env 文件

```bash
cd /Users/connie/kayee/chat_work
cp .env.example .env
```

编辑 `.env`，填入飞书凭证：

```env
# 飞书配置（从开放平台获取）
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=      # 可选，事件订阅页面获取
FEISHU_ENCRYPT_KEY=             # 可选，事件订阅页面获取

# 服务配置
HOST=0.0.0.0
PORT=8000

# 安全配置（允许 Claude 操作的目录）
ALLOWED_DIRS=/Users/connie/kayee,/tmp
```

### 3.2 启动服务

```bash
source .venv/bin/activate
chat_work serve -p 8000
```

服务启动后会监听 `http://0.0.0.0:8000`

---

## 第四步：配置内网穿透

飞书服务器需要能访问你的本机服务，选择一种方式：

### 方案 A：Tailscale Funnel（推荐）

如果你已经在用 Tailscale：

```bash
# 开启 Funnel
tailscale funnel 8000
```

会得到一个公网地址，如：
```
https://your-machine.tailnet-name.ts.net/
```

### 方案 B：ngrok

```bash
# 安装
brew install ngrok

# 启动
ngrok http 8000
```

会得到一个公网地址，如：
```
https://xxxx-xxx-xxx.ngrok.io
```

### 方案 C：cpolar（国内速度快）

```bash
# 安装
curl -L https://www.cpolar.com/static/downloads/install-release-cpolar.sh | sudo bash

# 启动
cpolar http 8000
```

---

## 第五步：配置 Webhook 地址

### 5.1 回到飞书开放平台

1. 进入你的应用
2. 左侧菜单：「事件订阅」
3. 填写请求地址：

```
https://你的穿透地址/webhook/feishu
```

例如：
- Tailscale: `https://your-machine.ts.net/webhook/feishu`
- ngrok: `https://xxxx.ngrok.io/webhook/feishu`

### 5.2 验证配置

点击「保存」，飞书会发送验证请求。如果你的服务正常运行，会显示「验证成功」。

---

## 第六步：发布应用

### 6.1 创建版本

1. 左侧菜单：「版本管理与发布」
2. 点击「创建版本」
3. 填写版本号和更新说明
4. 点击「保存」

### 6.2 申请发布

1. 点击「申请线上发布」
2. 如果你是企业管理员，会自动通过
3. 如果不是，需要管理员在飞书 App 中审批

---

## 第七步：开始使用

### 7.1 添加机器人到群聊

1. 在飞书中创建一个群聊（或使用现有群）
2. 点击群设置 → 「群机器人」→「添加机器人」
3. 选择你创建的应用

### 7.2 私聊机器人

1. 在飞书搜索框搜索你的应用名称
2. 点击进入私聊

### 7.3 发送消息测试

```
你：你好
机器人：🤔 思考中...
机器人：你好！有什么可以帮助你的吗？
```

---

## 功能说明

### 支持的消息类型

| 类型 | 支持 | 说明 |
|------|------|------|
| 文本 | ✅ | 直接对话 |
| 图片 | ✅ | 发送图片让 AI 识别 |
| 文件 | ✅ | 发送文件让 AI 读取 |
| 富文本 | ✅ | 图文混合消息 |
| 语音 | ⚠️ | 暂不支持 |

### 回复方式

- **伪流式**：先显示「🤔 思考中...」，然后逐步更新内容
- 更新间隔 0.8 秒，避免 API 限流

---

## 常见问题

### Q: Webhook 验证失败？

1. 检查服务是否正常运行：`curl http://localhost:8000/health`
2. 检查内网穿透是否正常
3. 检查 URL 是否正确（注意 https）

### Q: 消息收不到？

1. 检查权限是否开启
2. 检查应用是否已发布
3. 检查事件订阅是否配置 `im.message.receive_v1`

### Q: 机器人没有回复？

1. 检查终端日志是否有错误
2. 检查 Claude CLI 是否正常：`claude -p "你好" --output-format json`
3. 检查 .env 配置是否正确

### Q: 内网穿透地址变了？

- ngrok 免费版每次重启地址会变，需要重新配置
- 建议使用 Tailscale Funnel（地址固定）或 ngrok 付费版

---

## 快速检查清单

- [ ] 飞书应用已创建
- [ ] App ID 和 App Secret 已配置到 .env
- [ ] 机器人能力已添加
- [ ] 权限已开启
- [ ] 事件订阅已配置
- [ ] 内网穿透已启动
- [ ] Webhook 地址已填写并验证通过
- [ ] 应用已发布
- [ ] Chat Work 服务正在运行
