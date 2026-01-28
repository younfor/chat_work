"""飞书平台接入 - 支持文本、图片、文件、语音消息 + 伪流式回复"""

import hashlib
import json
import httpx
import os
import tempfile
import uuid
import asyncio
from typing import Optional, Dict, Any, List, AsyncGenerator
from pathlib import Path
from app.config import settings


class FeishuPlatform:
    """飞书机器人平台"""

    def __init__(self):
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self.verification_token = settings.feishu_verification_token
        self.encrypt_key = settings.feishu_encrypt_key
        self._tenant_access_token: Optional[str] = None
        self._token_expire_time: float = 0

        # 临时文件存储目录
        self.temp_dir = Path(tempfile.gettempdir()) / "chat_work_feishu"
        self.temp_dir.mkdir(exist_ok=True)

    async def get_tenant_access_token(self) -> str:
        """获取 tenant_access_token"""
        import time

        # 检查 token 是否过期
        if self._tenant_access_token and time.time() < self._token_expire_time:
            return self._tenant_access_token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret
                }
            )
            data = response.json()
            self._tenant_access_token = data.get("tenant_access_token")
            # token 有效期 2 小时，提前 5 分钟刷新
            self._token_expire_time = time.time() + data.get("expire", 7200) - 300
            return self._tenant_access_token

    def verify_signature(self, timestamp: str, nonce: str, body: str, signature: str) -> bool:
        """验证飞书请求签名"""
        if not self.encrypt_key:
            return True

        content = timestamp + nonce + self.encrypt_key + body
        calculated = hashlib.sha256(content.encode()).hexdigest()
        return calculated == signature

    async def download_resource(
        self,
        message_id: str,
        file_key: str,
        resource_type: str = "image",
        filename: str = ""
    ) -> Optional[str]:
        """下载飞书资源（图片、文件、语音等）"""
        token = await self.get_tenant_access_token()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"type": resource_type},
                    follow_redirects=True
                )

                if response.status_code == 200:
                    # 确定文件扩展名
                    content_type = response.headers.get("content-type", "")
                    ext = self._get_extension(content_type, resource_type, filename)

                    # 保存到临时文件
                    safe_filename = f"{uuid.uuid4().hex}{ext}"
                    filepath = self.temp_dir / safe_filename
                    filepath.write_bytes(response.content)

                    return str(filepath)
                else:
                    print(f"下载资源失败: {response.status_code}")
                    return None

        except Exception as e:
            print(f"下载资源异常: {e}")
            return None

    def _get_extension(self, content_type: str, resource_type: str, filename: str) -> str:
        """根据内容类型获取文件扩展名"""
        # 从原始文件名获取扩展名
        if filename and "." in filename:
            return "." + filename.rsplit(".", 1)[-1].lower()

        # 从 content-type 推断
        type_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "audio/ogg": ".ogg",
            "audio/mp3": ".mp3",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/amr": ".amr",
            "video/mp4": ".mp4",
            "application/pdf": ".pdf",
        }

        for mime, ext in type_map.items():
            if mime in content_type:
                return ext

        # 默认扩展名
        defaults = {
            "image": ".png",
            "file": ".bin",
            "audio": ".ogg",
        }
        return defaults.get(resource_type, ".bin")

    async def download_image(self, message_id: str, file_key: str) -> Optional[str]:
        """下载图片"""
        return await self.download_resource(message_id, file_key, "image")

    async def download_file(self, message_id: str, file_key: str, filename: str) -> Optional[str]:
        """下载文件"""
        return await self.download_resource(message_id, file_key, "file", filename)

    async def download_audio(self, message_id: str, file_key: str) -> Optional[str]:
        """下载语音"""
        return await self.download_resource(message_id, file_key, "file")  # 语音用 file 类型

    async def send_message(self, chat_id: str, content: str, msg_type: str = "text") -> Dict:
        """发送消息到飞书，返回消息信息"""
        token = await self.get_tenant_access_token()

        if msg_type == "text":
            content_body = {"text": content}
        else:
            content_body = content

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                params={"receive_id_type": "chat_id"},
                json={
                    "receive_id": chat_id,
                    "msg_type": msg_type,
                    "content": json.dumps(content_body)
                }
            )
            return response.json()

    async def reply_message(self, message_id: str, content: str, msg_type: str = "text") -> Dict:
        """回复消息"""
        token = await self.get_tenant_access_token()

        if msg_type == "text":
            content_body = {"text": content}
        else:
            content_body = content

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "msg_type": msg_type,
                    "content": json.dumps(content_body)
                }
            )
            return response.json()

    async def update_message(self, message_id: str, content: str) -> Dict:
        """更新消息内容（用于实现伪流式）"""
        token = await self.get_tenant_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "msg_type": "text",
                    "content": json.dumps({"text": content})
                }
            )
            return response.json()

    async def reply_stream(
        self,
        message_id: str,
        content_generator: AsyncGenerator[str, None],
        update_interval: float = 0.5
    ):
        """
        伪流式回复：先发送一条消息，然后持续更新

        Args:
            message_id: 要回复的消息 ID
            content_generator: 内容生成器
            update_interval: 更新间隔（秒）
        """
        # 先发送一条 "思考中..." 的消息
        result = await self.reply_message(message_id, "🤔 思考中...")
        reply_message_id = result.get("data", {}).get("message_id")

        if not reply_message_id:
            return

        full_content = ""
        last_update_time = 0
        import time

        try:
            async for chunk in content_generator:
                full_content += chunk
                current_time = time.time()

                # 按间隔更新消息
                if current_time - last_update_time >= update_interval:
                    await self.update_message(reply_message_id, full_content + " ▌")
                    last_update_time = current_time

            # 最终更新（移除光标）
            await self.update_message(reply_message_id, full_content)

        except Exception as e:
            await self.update_message(reply_message_id, f"{full_content}\n\n❌ 错误: {e}")

    async def parse_event(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析飞书事件，支持文本、图片、文件、语音消息"""

        # URL 验证
        if data.get("type") == "url_verification":
            return {"type": "verification", "challenge": data.get("challenge")}

        # 消息事件
        header = data.get("header", {})
        event = data.get("event", {})

        if header.get("event_type") == "im.message.receive_v1":
            message = event.get("message", {})
            sender = event.get("sender", {})
            msg_type = message.get("message_type", "text")
            message_id = message.get("message_id")

            # 解析消息内容
            content = message.get("content", "{}")
            try:
                content_json = json.loads(content)
            except:
                content_json = {}

            result = {
                "type": "message",
                "message_id": message_id,
                "chat_id": message.get("chat_id"),
                "chat_type": message.get("chat_type"),  # p2p / group
                "msg_type": msg_type,
                "sender_id": sender.get("sender_id", {}).get("user_id"),
                "text": "",
                "images": [],   # 图片本地路径列表
                "files": [],    # 文件本地路径列表
                "audios": [],   # 语音本地路径列表
            }

            # 处理不同消息类型
            if msg_type == "text":
                result["text"] = content_json.get("text", "")

            elif msg_type == "image":
                # 图片消息
                image_key = content_json.get("image_key")
                if image_key:
                    image_path = await self.download_image(message_id, image_key)
                    if image_path:
                        result["images"].append(image_path)
                        result["text"] = f"请查看并描述这张图片: {image_path}"

            elif msg_type == "file":
                # 文件消息
                file_key = content_json.get("file_key")
                file_name = content_json.get("file_name", "file")
                if file_key:
                    file_path = await self.download_file(message_id, file_key, file_name)
                    if file_path:
                        result["files"].append(file_path)
                        result["text"] = f"请查看这个文件 {file_name}: {file_path}"

            elif msg_type == "audio":
                # 语音消息
                file_key = content_json.get("file_key")
                if file_key:
                    audio_path = await self.download_audio(message_id, file_key)
                    if audio_path:
                        result["audios"].append(audio_path)
                        # 语音需要转文字后处理
                        result["text"] = f"[用户发送了语音消息，文件路径: {audio_path}]"
                        # 注意：Claude 目前不能直接处理音频，需要额外的语音转文字服务

            elif msg_type == "post":
                # 富文本消息，可能包含图片
                post_content = content_json.get("content", [])
                texts = []
                for line in post_content:
                    for item in line:
                        tag = item.get("tag")
                        if tag == "text":
                            texts.append(item.get("text", ""))
                        elif tag == "img":
                            image_key = item.get("image_key")
                            if image_key:
                                image_path = await self.download_image(message_id, image_key)
                                if image_path:
                                    result["images"].append(image_path)
                                    texts.append(f"\n[请查看图片: {image_path}]\n")
                result["text"] = "".join(texts)

            elif msg_type == "media":
                # 视频消息
                file_key = content_json.get("file_key")
                if file_key:
                    file_path = await self.download_file(message_id, file_key, "video.mp4")
                    if file_path:
                        result["files"].append(file_path)
                        result["text"] = f"[用户发送了视频: {file_path}]"

            elif msg_type == "sticker":
                # 表情包
                result["text"] = "[用户发送了表情包]"

            return result

        return None

    def cleanup_temp_files(self, max_age_hours: int = 24):
        """清理过期的临时文件"""
        import time

        now = time.time()
        max_age_seconds = max_age_hours * 3600

        for filepath in self.temp_dir.iterdir():
            if filepath.is_file():
                file_age = now - filepath.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        filepath.unlink()
                    except:
                        pass


# 全局实例
feishu_platform = FeishuPlatform()
