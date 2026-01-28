"""Claude CLI 服务 - 通过跨进程调用本地 claude，支持流式输出"""

import subprocess
import json
import asyncio
import os
from typing import AsyncGenerator, Optional, List, Dict, Any


class ClaudeService:
    """通过调用本地 claude CLI 来实现 AI 对话"""

    def __init__(self):
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
        # 获取 claude 命令的完整路径
        self.claude_path = self._find_claude_path()

    def _find_claude_path(self) -> str:
        """查找 claude 命令路径"""
        # 尝试常见路径
        possible_paths = [
            "/usr/local/bin/claude",
            "/opt/homebrew/bin/claude",
            os.path.expanduser("~/.npm-global/bin/claude"),
            os.path.expanduser("~/.local/bin/claude"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # 默认使用 PATH 中的 claude
        return "claude"

    def get_conversation(self, session_id: str) -> List[Dict[str, str]]:
        """获取会话历史"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        return self.conversations[session_id]

    def add_message(self, session_id: str, role: str, content: str):
        """添加消息到会话"""
        conversation = self.get_conversation(session_id)
        conversation.append({"role": role, "content": content})
        # 保留最近 20 条消息
        if len(conversation) > 20:
            self.conversations[session_id] = conversation[-20:]

    def clear_conversation(self, session_id: str):
        """清除会话历史"""
        self.conversations[session_id] = []

    async def chat(
        self,
        message: str,
        session_id: str = "default",
        context: Optional[str] = None
    ) -> str:
        """发送消息并获取回复 - 调用本地 claude CLI"""

        self.add_message(session_id, "user", message)

        full_message = message
        if context:
            full_message = f"[上下文: {context}]\n\n{message}"

        try:
            # 调用 claude CLI，使用 JSON 输出
            process = await asyncio.create_subprocess_exec(
                self.claude_path,
                "-p", full_message,
                "--output-format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1"}
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300  # 5分钟超时
            )

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "未知错误"
                return f"Claude CLI 错误: {error_msg}"

            # 解析 JSON 响应
            try:
                result = json.loads(stdout.decode())
                response = result.get("result", stdout.decode().strip())
            except json.JSONDecodeError:
                response = stdout.decode().strip()

            self.add_message(session_id, "assistant", response)
            return response

        except asyncio.TimeoutError:
            return "请求超时（超过5分钟）"
        except FileNotFoundError:
            return "错误: 找不到 claude 命令，请确保 Claude Code CLI 已安装"
        except Exception as e:
            return f"调用 Claude 失败: {str(e)}"

    async def chat_stream(
        self,
        message: str,
        session_id: str = "default",
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """流式发送消息 - 调用本地 claude CLI 的流式输出"""

        self.add_message(session_id, "user", message)

        full_message = message
        if context:
            full_message = f"[上下文: {context}]\n\n{message}"

        try:
            # 使用 stream-json 格式获取流式输出
            process = await asyncio.create_subprocess_exec(
                self.claude_path,
                "-p", full_message,
                "--output-format", "stream-json",
                "--include-partial-messages",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1"}
            )

            full_response = ""
            buffer = ""

            # 逐行读取 JSON 流
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode().strip())

                    # 处理不同类型的消息
                    msg_type = data.get("type")

                    if msg_type == "assistant":
                        # 完整的助手消息
                        content = data.get("message", {}).get("content", [])
                        for block in content:
                            if block.get("type") == "text":
                                text = block.get("text", "")
                                # 只输出新增的部分
                                if text.startswith(full_response):
                                    new_text = text[len(full_response):]
                                    if new_text:
                                        yield new_text
                                        full_response = text
                                else:
                                    # 全新的文本
                                    yield text
                                    full_response = text

                    elif msg_type == "content_block_delta":
                        # 增量文本
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            yield text
                            full_response += text

                    elif msg_type == "result":
                        # 最终结果
                        result_text = data.get("result", "")
                        if result_text and not full_response:
                            yield result_text
                            full_response = result_text

                except json.JSONDecodeError:
                    # 非 JSON 行，直接输出
                    text = line.decode().strip()
                    if text:
                        yield text
                        full_response += text

            await process.wait()

            if full_response:
                self.add_message(session_id, "assistant", full_response)
            else:
                # 如果没有收到流式数据，读取 stderr
                stderr = await process.stderr.read()
                if stderr:
                    yield f"错误: {stderr.decode()}"

        except FileNotFoundError:
            yield "错误: 找不到 claude 命令"
        except Exception as e:
            yield f"错误: {str(e)}"

    async def chat_with_session(
        self,
        message: str,
        session_id: str,
        resume: bool = True
    ) -> AsyncGenerator[str, None]:
        """使用 claude 的会话管理功能"""

        try:
            args = [self.claude_path, "-p", message, "--output-format", "stream-json"]

            if resume and session_id:
                # 尝试恢复会话
                args.extend(["--session-id", session_id])

            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1"}
            )

            full_response = ""

            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode().strip())
                    if data.get("type") == "content_block_delta":
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            yield text
                            full_response += text
                    elif data.get("type") == "result":
                        result = data.get("result", "")
                        if result and not full_response:
                            yield result
                except:
                    pass

            await process.wait()

        except Exception as e:
            yield f"错误: {str(e)}"


# 全局实例
claude_service = ClaudeService()
