"""FastAPI 主应用"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.api import router
from app.config import settings

app = FastAPI(
    title="Chat Work",
    description="通过聊天就能工作",
    version="0.1.0"
)

# 注册路由
app.include_router(router)

# 静态文件
static_dir = os.path.join(os.path.dirname(__file__), "..", "web", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    from app.platforms.feishu import feishu_platform
    from app.api.routes import process_feishu_message
    
    # 后台启动飞书 WebSocket
    import asyncio
    asyncio.create_task(feishu_platform.start_feishu_ws(process_feishu_message))



@app.get("/")
async def index():
    """Web 首页"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Chat Work API", "docs": "/docs"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


def run():
    """运行服务器"""
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )


if __name__ == "__main__":
    run()
