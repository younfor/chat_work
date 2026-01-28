"""配置管理"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    # Claude API
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")

    # 飞书配置
    feishu_app_id: str = Field(default="", env="FEISHU_APP_ID")
    feishu_app_secret: str = Field(default="", env="FEISHU_APP_SECRET")
    feishu_verification_token: str = Field(default="", env="FEISHU_VERIFICATION_TOKEN")
    feishu_encrypt_key: str = Field(default="", env="FEISHU_ENCRYPT_KEY")

    # 服务配置
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    debug: bool = Field(default=False, env="DEBUG")

    # 安全配置
    allowed_dirs: str = Field(default="/tmp", env="ALLOWED_DIRS")
    blocked_commands: str = Field(default="rm -rf /,sudo rm,mkfs,dd if=", env="BLOCKED_COMMANDS")

    @property
    def allowed_dirs_list(self) -> List[str]:
        return [d.strip() for d in self.allowed_dirs.split(",") if d.strip()]

    @property
    def blocked_commands_list(self) -> List[str]:
        return [c.strip() for c in self.blocked_commands.split(",") if c.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
