"""命令执行服务"""

import subprocess
import os
import json
import re
from typing import Dict, Any, Optional, Tuple
from app.config import settings


class ExecutorService:
    """安全地执行命令和文件操作"""

    def __init__(self):
        self.allowed_dirs = settings.allowed_dirs_list
        self.blocked_commands = settings.blocked_commands_list

    def is_path_allowed(self, path: str) -> bool:
        """检查路径是否在允许的目录内"""
        abs_path = os.path.abspath(os.path.expanduser(path))
        return any(abs_path.startswith(d) for d in self.allowed_dirs)

    def is_command_blocked(self, command: str) -> bool:
        """检查命令是否被禁止"""
        return any(blocked in command for blocked in self.blocked_commands)

    def parse_action(self, response: str) -> Optional[Dict[str, Any]]:
        """从 AI 响应中解析操作指令"""
        # 查找 JSON 格式的操作指令
        json_pattern = r'```json\s*(\{[^`]+\})\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)

        for match in matches:
            try:
                action = json.loads(match)
                if "action" in action:
                    return action
            except json.JSONDecodeError:
                continue

        return None

    def execute_command(self, command: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
        """执行 shell 命令"""

        # 安全检查
        if self.is_command_blocked(command):
            return False, f"命令被禁止执行: {command}"

        if cwd and not self.is_path_allowed(cwd):
            return False, f"目录不在允许列表中: {cwd}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=cwd or os.getcwd()
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"

            if result.returncode != 0:
                return False, f"命令执行失败 (code={result.returncode}):\n{output}"

            return True, output or "命令执行成功（无输出）"

        except subprocess.TimeoutExpired:
            return False, "命令执行超时（60秒）"
        except Exception as e:
            return False, f"执行错误: {str(e)}"

    def read_file(self, path: str) -> Tuple[bool, str]:
        """读取文件内容"""

        abs_path = os.path.abspath(os.path.expanduser(path))

        if not self.is_path_allowed(abs_path):
            return False, f"文件路径不在允许列表中: {path}"

        if not os.path.exists(abs_path):
            return False, f"文件不存在: {path}"

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            return True, content
        except Exception as e:
            return False, f"读取文件失败: {str(e)}"

    def write_file(self, path: str, content: str) -> Tuple[bool, str]:
        """写入文件"""

        abs_path = os.path.abspath(os.path.expanduser(path))

        if not self.is_path_allowed(abs_path):
            return False, f"文件路径不在允许列表中: {path}"

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, f"文件已写入: {abs_path}"
        except Exception as e:
            return False, f"写入文件失败: {str(e)}"

    async def process_action(self, action: Dict[str, Any]) -> str:
        """处理 AI 返回的操作指令"""

        action_type = action.get("action")

        if action_type == "execute":
            command = action.get("command", "")
            description = action.get("description", "")
            success, output = self.execute_command(command)
            status = "✅" if success else "❌"
            return f"{status} 执行命令: {command}\n{description}\n\n结果:\n{output}"

        elif action_type == "read_file":
            path = action.get("path", "")
            success, content = self.read_file(path)
            status = "✅" if success else "❌"
            return f"{status} 读取文件: {path}\n\n{content}"

        elif action_type == "write_file":
            path = action.get("path", "")
            content = action.get("content", "")
            description = action.get("description", "")
            success, result = self.write_file(path, content)
            status = "✅" if success else "❌"
            return f"{status} {result}\n{description}"

        else:
            return f"未知操作类型: {action_type}"


# 全局实例
executor_service = ExecutorService()
