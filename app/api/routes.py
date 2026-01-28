"""API 路由"""

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any
import json
import uuid
import asyncio

from app.services import claude_service, executor_service
from app.platforms import feishu_platform

router = APIRouter()


# ==================== 飞书 Webhook ====================

# 消息去重缓存（防止重复处理）
_processed_messages: Dict[str, float] = {}


def _is_duplicate_message(message_id: str) -> bool:
    """检查是否重复消息"""
    import time
    now = time.time()

    # 清理过期记录（5分钟前的）
    expired = [k for k, v in _processed_messages.items() if now - v > 300]
    for k in expired:
        del _processed_messages[k]

    if message_id in _processed_messages:
        return True

    _processed_messages[message_id] = now
    return False


async def process_feishu_message(event: Dict[str, Any]):
    """后台处理飞书消息（支持流式回复）"""
    text = event["text"]
    message_id = event["message_id"]
    chat_id = event["chat_id"]
    images = event.get("images", [])
    files = event.get("files", [])

    # 构建完整提示
    full_prompt = text
    if images:
        full_prompt += f"\n\n请查看以下图片并回答: {', '.join(images)}"
    if files:
        full_prompt += f"\n\n请查看以下文件: {', '.join(files)}"

    session_id = f"feishu_{chat_id}"

    # 使用伪流式回复
    await feishu_platform.reply_stream(
        message_id=message_id,
        content_generator=claude_service.chat_stream(full_prompt, session_id),
        update_interval=0.8  # 0.8秒更新一次，避免限流
    )


@router.post("/webhook/feishu")
async def feishu_webhook(request: Request, background_tasks: BackgroundTasks):
    """飞书事件回调"""
    data = await request.json()

    # 解析事件（现在是 async）
    event = await feishu_platform.parse_event(data)
    if not event:
        return JSONResponse({"code": 0})

    # URL 验证
    if event["type"] == "verification":
        return JSONResponse({"challenge": event["challenge"]})

    # 处理消息
    if event["type"] == "message":
        message_id = event["message_id"]

        # 去重检查
        if _is_duplicate_message(message_id):
            return JSONResponse({"code": 0})

        # 后台处理消息（立即返回响应给飞书）
        background_tasks.add_task(process_feishu_message, event)

    return JSONResponse({"code": 0})


# ==================== REST API ====================

@router.post("/api/chat")
async def chat(request: Request):
    """聊天 API"""
    data = await request.json()
    message = data.get("message", "")
    session_id = data.get("session_id", str(uuid.uuid4()))
    auto_execute = data.get("auto_execute", False)

    if not message:
        return JSONResponse({"error": "消息不能为空"}, status_code=400)

    # 调用 Claude
    response = await claude_service.chat(message, session_id)

    result = {
        "response": response,
        "session_id": session_id,
        "action": None,
        "action_result": None
    }

    # 检查是否有需要执行的操作
    action = executor_service.parse_action(response)
    if action:
        result["action"] = action
        if auto_execute:
            action_result = await executor_service.process_action(action)
            result["action_result"] = action_result

    return JSONResponse(result)


@router.post("/api/execute")
async def execute_action(request: Request):
    """执行操作 API"""
    data = await request.json()
    action = data.get("action")

    if not action:
        return JSONResponse({"error": "操作不能为空"}, status_code=400)

    result = await executor_service.process_action(action)
    return JSONResponse({"result": result})


@router.post("/api/clear")
async def clear_session(request: Request):
    """清除会话历史"""
    data = await request.json()
    session_id = data.get("session_id", "default")
    claude_service.clear_conversation(session_id)
    return JSONResponse({"message": "会话已清除"})


# ==================== WebSocket ====================

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 聊天"""
    await websocket.accept()
    session_id = str(uuid.uuid4())

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            message = message_data.get("message", "")
            auto_execute = message_data.get("auto_execute", False)

            if message == "/clear":
                claude_service.clear_conversation(session_id)
                await websocket.send_json({"type": "system", "message": "会话已清除"})
                continue

            # 流式响应
            full_response = ""
            async for chunk in claude_service.chat_stream(message, session_id):
                full_response += chunk
                await websocket.send_json({"type": "chunk", "content": chunk})

            # 发送完成信号
            await websocket.send_json({"type": "done", "content": full_response})

            # 检查并执行操作
            action = executor_service.parse_action(full_response)
            if action:
                await websocket.send_json({"type": "action", "action": action})
                if auto_execute:
                    result = await executor_service.process_action(action)
                    await websocket.send_json({"type": "action_result", "result": result})

    except WebSocketDisconnect:
        pass
