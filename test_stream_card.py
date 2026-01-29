import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.platforms.feishu import feishu_platform

async def mock_generator():
    """Generates rich text content in chunks"""
    chunks = [
        "👋 Hello! This is a **Rich Text Streaming** test.\n\n",
        "I can render **Bold**, *Italic*, and `Inline Code`.\n\n",
        "Here is a Python code block:\n",
        "```python\n",
        "def hello_world():\n",
        "    print('Hello Feishu!')\n",
        "    return True\n",
        "```\n\n",
        "And even a table:\n",
        "| Feature | Status |\n",
        "| :--- | :--- |\n",
        "| Streaming | ✅ Active |\n",
        "| Rich Text | ✅ Supported |\n",
        "\n",
        "Hope you like it! 🚀"
    ]
    
    for chunk in chunks:
        await asyncio.sleep(0.5)  # Simulate delay for typing effect
        yield chunk

async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_stream_card.py <message_id>")
        print("Please provide a message_id to reply to.")
        return

    message_id = sys.argv[1]
    print(f"Starting stream test for message_id: {message_id}...")
    
    try:
        await feishu_platform.reply_stream(
            message_id=message_id,
            content_generator=mock_generator(),
            update_interval=0.3
        )
        print("Test completed successfully!")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
