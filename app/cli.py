"""命令行界面"""

import typer
import asyncio
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from app.services import claude_service, executor_service

app = typer.Typer(help="Chat Work - 通过聊天就能工作")
console = Console()


def print_response(response: str):
    """打印 AI 响应"""
    console.print(Panel(Markdown(response), title="🤖 AI", border_style="blue"))


def print_action_result(result: str):
    """打印操作结果"""
    console.print(Panel(result, title="⚡ 执行结果", border_style="green"))


def print_error(message: str):
    """打印错误"""
    console.print(Panel(message, title="❌ 错误", border_style="red"))


async def chat_loop(session_id: str, auto_execute: bool):
    """聊天循环"""
    console.print(Panel(
        "输入消息与 AI 对话，输入 /help 查看帮助，输入 /exit 退出",
        title="💬 Chat Work",
        border_style="cyan"
    ))

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]你[/bold cyan]")

            if not user_input.strip():
                continue

            # 处理命令
            if user_input.startswith("/"):
                cmd = user_input.lower().strip()

                if cmd == "/exit" or cmd == "/quit":
                    console.print("[yellow]再见！[/yellow]")
                    break

                elif cmd == "/clear":
                    claude_service.clear_conversation(session_id)
                    console.print("[yellow]会话已清除[/yellow]")
                    continue

                elif cmd == "/auto":
                    auto_execute = not auto_execute
                    status = "开启" if auto_execute else "关闭"
                    console.print(f"[yellow]自动执行已{status}[/yellow]")
                    continue

                elif cmd == "/help":
                    help_text = """
**可用命令:**
- `/clear` - 清除对话历史
- `/auto` - 切换自动执行模式
- `/exit` 或 `/quit` - 退出程序
- `/help` - 显示帮助

**使用示例:**
- "帮我查看当前目录的文件"
- "创建一个 Python 脚本，打印 Hello World"
- "帮我执行 git status"
                    """
                    console.print(Markdown(help_text))
                    continue

            # 调用 AI
            with console.status("[bold green]思考中...[/bold green]"):
                response = await claude_service.chat(user_input, session_id)

            print_response(response)

            # 检查是否有操作需要执行
            action = executor_service.parse_action(response)
            if action:
                if auto_execute:
                    console.print("[yellow]正在执行操作...[/yellow]")
                    result = await executor_service.process_action(action)
                    print_action_result(result)
                else:
                    console.print(f"\n[yellow]检测到操作: {action.get('action')}[/yellow]")
                    confirm = Prompt.ask("是否执行？", choices=["y", "n"], default="y")
                    if confirm == "y":
                        result = await executor_service.process_action(action)
                        print_action_result(result)

        except KeyboardInterrupt:
            console.print("\n[yellow]按 Ctrl+C 退出，或输入 /exit[/yellow]")
        except Exception as e:
            print_error(str(e))


@app.command()
def chat(
    session: str = typer.Option("cli_default", "--session", "-s", help="会话 ID"),
    auto: bool = typer.Option(False, "--auto", "-a", help="自动执行命令")
):
    """启动交互式聊天"""
    asyncio.run(chat_loop(session, auto))


@app.command()
def ask(
    message: str = typer.Argument(..., help="要发送的消息"),
    session: str = typer.Option("cli_default", "--session", "-s", help="会话 ID"),
    execute: bool = typer.Option(False, "--execute", "-e", help="自动执行命令")
):
    """发送单条消息"""
    async def run():
        response = await claude_service.chat(message, session)
        print_response(response)

        action = executor_service.parse_action(response)
        if action and execute:
            result = await executor_service.process_action(action)
            print_action_result(result)

    asyncio.run(run())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="监听地址"),
    port: int = typer.Option(8000, "--port", "-p", help="监听端口"),
    reload: bool = typer.Option(False, "--reload", "-r", help="热重载")
):
    """启动 Web 服务器"""
    import uvicorn
    console.print(f"[bold green]启动服务器: http://{host}:{port}[/bold green]")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


def main():
    app()


if __name__ == "__main__":
    main()
