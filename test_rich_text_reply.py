import asyncio
import os
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

from app.platforms.feishu import FeishuPlatform

async def mock_generator():
    content = """
# Hello World in Python

Here is a **code block** example:

```python
def hello_world():
    print("Hello, Feishu Cards!")
    return True
```

## Features List

- [x] Rich Text
- [x] Streaming
- [ ] Code Execution

## Data Table

| ID | Name | Role |
|----|------|------|
| 1  | Bot  | AI   |
| 2  | User | Human|

> End of test message.
"""
    # Simulate streaming chunks
    chunk_size = 10
    for i in range(0, len(content), chunk_size):
        yield content[i:i+chunk_size]
        await asyncio.sleep(0.1)

async def main():
    if len(sys.argv) < 2:
        print("Usage: python3.9 test_rich_text_reply.py <message_id>")
        return

    message_id = sys.argv[1]
    
    feishu = FeishuPlatform()
    print(f"Sending rich text reply to message: {message_id}")
    
    await feishu.reply_stream(message_id, mock_generator(), update_interval=0.1)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
