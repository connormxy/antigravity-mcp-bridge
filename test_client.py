import asyncio
import httpx
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    print("[1] Connecting to Antigravity MCP Bridge over SSE at http://127.0.0.1:8080/sse...")
    try:
        async with sse_client("http://127.0.0.1:8080/sse") as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("[2] Connected and initialized! Listing tools...")
                tools = await session.list_tools()
                for t in tools.tools:
                    print(f"  - Tool: {t.name}")
                    print(f"    Description: {t.description}")
                    print(f"    Input Schema: {t.inputSchema}\n")
                
                print("[3] Testing tool call: list_antigravity_tasks...")
                res = await session.call_tool("list_antigravity_tasks", {})
                print(f"    Result: {res.content}\n")
                
                print("[4] Testing synchronous task execution (checking agy environment)...")
                res = await session.call_tool(
                    "execute_antigravity_sync",
                    {"prompt": "--version", "timeout_seconds": 15}
                )
                print(f"    Result:\n{res.content[0].text if res.content else 'No content'}")
    except Exception as e:
        print(f"Error testing MCP Bridge: {e}")

if __name__ == "__main__":
    asyncio.run(main())
