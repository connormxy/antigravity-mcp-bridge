import os
import subprocess
import threading
import uuid
import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("antigravity-mcp-bridge")

# Initialize FastMCP Server
mcp = FastMCP("Antigravity Sub-Agent Bridge")

# In-memory store for async background executions
TASKS: Dict[str, Dict[str, Any]] = {}
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "/workspace")


@mcp.tool()
def execute_antigravity_sync(
    prompt: str,
    sub_path: str = "",
    timeout_seconds: int = 300,
) -> str:
    """Executes a coding/automation task synchronously via Antigravity CLI.
    
    Args:
        prompt: The task instruction or goal for the Antigravity agent.
        sub_path: Optional sub-directory path inside the workspace to execute within.
        timeout_seconds: Maximum execution time before aborting (default: 300s).
    
    Returns:
        The text output/log of the Antigravity agent run.
    """
    cwd = (
        os.path.join(WORKSPACE_DIR, sub_path.strip("/"))
        if sub_path
        else WORKSPACE_DIR
    )
    os.makedirs(cwd, exist_ok=True)
    logger.info(f"Executing sync Antigravity task in '{cwd}': {prompt[:100]}...")

    cmd = ["agy", "--headless", prompt]
    try:
        res = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
        if res.returncode != 0:
            logger.warning(f"Task exited with error code {res.returncode}")
            return f"Agent exited with code {res.returncode}:\n{res.stderr or res.stdout}"
        
        logger.info("Sync task completed successfully")
        return res.stdout or "Task completed with no output."
    except subprocess.TimeoutExpired:
        logger.error(f"Task timed out after {timeout_seconds} seconds")
        return f"Task timed out after {timeout_seconds} seconds."
    except FileNotFoundError:
        logger.error("Antigravity CLI ('agy') binary not found in system PATH")
        return "Error: Antigravity CLI ('agy') is not installed or not in PATH."
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        return f"Execution failed: {str(e)}"


@mcp.tool()
def start_antigravity_async(prompt: str, sub_path: str = "") -> str:
    """Dispatches a long-running Antigravity task in the background.
    
    Args:
        prompt: The task instruction or goal for the Antigravity agent.
        sub_path: Optional sub-directory path inside the workspace to execute within.
        
    Returns:
        A task_id to inspect with get_antigravity_task_status.
    """
    task_id = str(uuid.uuid4())[:8]
    cwd = (
        os.path.join(WORKSPACE_DIR, sub_path.strip("/"))
        if sub_path
        else WORKSPACE_DIR
    )
    os.makedirs(cwd, exist_ok=True)
    logger.info(f"Launching async task '{task_id}' in '{cwd}': {prompt[:100]}...")

    TASKS[task_id] = {
        "status": "running",
        "prompt": prompt,
        "output": "",
        "cwd": cwd
    }

    def _worker():
        cmd = ["agy", "--headless", prompt]
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            TASKS[task_id]["status"] = (
                "completed" if res.returncode == 0 else "failed"
            )
            TASKS[task_id]["output"] = (
                res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
            )
            logger.info(f"Async task '{task_id}' finished with status: {TASKS[task_id]['status']}")
        except Exception as e:
            TASKS[task_id]["status"] = "error"
            TASKS[task_id]["output"] = str(e)
            logger.error(f"Async task '{task_id}' encountered error: {e}")

    threading.Thread(target=_worker, daemon=True).start()
    return (
        f"Task launched in background. Task ID: {task_id}. "
        "Check status using get_antigravity_task_status."
    )


@mcp.tool()
def get_antigravity_task_status(task_id: str) -> str:
    """Polls the status and output of a background task dispatched by start_antigravity_async.
    
    Args:
        task_id: The 8-character task ID returned by start_antigravity_async.
    """
    task = TASKS.get(task_id)
    if not task:
        return f"Task ID '{task_id}' was not found."

    if task["status"] == "running":
        return f"Task '{task_id}' is still in progress.\nPrompt: {task.get('prompt', '')}"

    return f"Status: {task['status']}\nPrompt: {task.get('prompt', '')}\n\nOutput Log:\n{task['output']}"


@mcp.tool()
def list_antigravity_tasks() -> str:
    """Lists all background Antigravity tasks and their current status."""
    if not TASKS:
        return "No background tasks have been launched."
    
    lines = ["Active & Completed Tasks:"]
    for tid, tinfo in TASKS.items():
        lines.append(f"- [{tid}] Status: {tinfo['status']} | Prompt: {tinfo.get('prompt', '')[:60]}...")
    return "\n".join(lines)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting Antigravity MCP Bridge on {host}:{port} via SSE transport...")
    mcp.run(transport="sse", host=host, port=port)
