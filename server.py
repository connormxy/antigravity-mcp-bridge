import os
import subprocess
import threading
import uuid
import logging
import json
import shutil
from typing import Dict, Any, Optional, List
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
WORKSPACE_DIR = os.path.abspath(os.getenv("WORKSPACE_DIR", "/workspace"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3.7-flash")
DEFAULT_EFFORT = os.getenv("DEFAULT_EFFORT", "high")
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "300"))
AUTO_APPROVE = os.getenv("AUTO_APPROVE_PERMISSIONS", "true").lower() in ("true", "1", "yes")
EXTRA_AGY_FLAGS = [f.strip() for f in os.getenv("EXTRA_AGY_FLAGS", "").split() if f.strip()]


def sanitize_workspace_path(sub_path: str = "") -> str:
    """Ensures paths are confined strictly within the WORKSPACE_DIR sandbox."""
    if not sub_path:
        return WORKSPACE_DIR
    target = os.path.abspath(os.path.join(WORKSPACE_DIR, sub_path.lstrip("/\\")))
    if not target.startswith(WORKSPACE_DIR):
        logger.warning(f"Path escape attempt blocked: {sub_path}")
        return WORKSPACE_DIR
    return target


def run_local_shell(cmd_str: str, cwd: str, timeout_seconds: int = 120) -> str:
    """Executes a shell command inside the container workspace."""
    try:
        res = subprocess.run(
            cmd_str,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy()
        )
        output = res.stdout if res.returncode == 0 else f"{res.stdout}\nSTDERR:\n{res.stderr}"
        return output.strip() or f"Command finished with returncode {res.returncode}"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout_seconds}s"
    except Exception as e:
        return f"Shell execution error: {str(e)}"


def run_gemini_agent_loop(prompt: str, cwd: str, model_name: str = DEFAULT_MODEL, max_steps: int = 10) -> str:
    """Autonomous Gemini Sub-Agent execution loop (YOLO mode)."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("ANTIGRAVITY_API_KEY")
    
    # Check if google-genai is available
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("google-genai SDK not installed. Falling back to direct shell execution.")
        return run_local_shell(prompt, cwd)

    if not api_key:
        # Check ~/.gemini or ADC credentials
        logger.info("No explicit GEMINI_API_KEY; attempting default client credentials.")

    try:
        client = genai.Client(api_key=api_key) if api_key else genai.Client()
        logger.info(f"Initialized Gemini Client for model '{model_name}' in '{cwd}'")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini Client: {e}")
        return f"Agent initialization failed: {e}. Falling back to shell: {run_local_shell(prompt, cwd)}"

    # Define tools available to the autonomous sub-agent
    def read_file(file_path: str) -> str:
        """Reads the text content of a file in the workspace."""
        full_p = sanitize_workspace_path(os.path.join(cwd, file_path) if not os.path.isabs(file_path) else file_path)
        if not os.path.exists(full_p):
            return f"Error: File '{file_path}' does not exist."
        try:
            with open(full_p, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as err:
            return f"Error reading file: {err}"

    def write_file(file_path: str, content: str) -> str:
        """Writes or updates content to a file in the workspace."""
        full_p = sanitize_workspace_path(os.path.join(cwd, file_path) if not os.path.isabs(file_path) else file_path)
        try:
            os.makedirs(os.path.dirname(full_p), exist_ok=True)
            with open(full_p, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to '{file_path}'"
        except Exception as err:
            return f"Error writing file: {err}"

    def list_files(directory_path: str = ".") -> str:
        """Lists files and directories in the target workspace directory."""
        full_p = sanitize_workspace_path(os.path.join(cwd, directory_path) if not os.path.isabs(directory_path) else directory_path)
        if not os.path.exists(full_p):
            return f"Error: Directory '{directory_path}' does not exist."
        try:
            entries = os.listdir(full_p)
            return "\n".join(entries) if entries else "(Empty directory)"
        except Exception as err:
            return f"Error listing directory: {err}"

    def execute_shell(command: str) -> str:
        """Runs a bash/shell command inside the workspace directory."""
        return run_local_shell(command, cwd=cwd, timeout_seconds=180)

    tools = [read_file, write_file, list_files, execute_shell]
    system_instruction = (
        "You are an autonomous expert software engineering sub-agent operating in YOLO mode. "
        "Your task is to analyze, implement, debug, test, and complete the user's instructions directly "
        "in the workspace filesystem using your available tools. Execute required tools proactively without "
        "asking for confirmation. Provide a concise, clear summary of changes and results when finished."
    )

    try:
        # Check model name fallback
        target_model = model_name
        for candidate in [model_name, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
            try:
                chat = client.chats.create(
                    model=candidate,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=tools,
                        temperature=0.2,
                    )
                )
                target_model = candidate
                break
            except Exception:
                continue

        logger.info(f"Dispatching task to {target_model}: {prompt[:100]}...")
        response = chat.send_message(prompt)
        return response.text or "Sub-agent task completed successfully."
    except Exception as e:
        logger.error(f"Gemini Sub-Agent loop encountered error: {e}")
        return f"Gemini Sub-Agent error: {str(e)}\n\nFallback shell run:\n{run_local_shell(prompt, cwd)}"


@mcp.tool()
def execute_antigravity_sync(
    prompt: str,
    sub_path: str = "",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT
) -> str:
    """Executes a coding, debugging, or automation task synchronously via Antigravity / Gemini Sub-Agent.
    
    Args:
        prompt: The task instruction or coding goal.
        sub_path: Optional sub-directory path inside /workspace (e.g. 'connormxy/antigravity-mcp-bridge').
        timeout_seconds: Maximum execution time before timeout (default from env: 300s).
        model: The Gemini model to use for the sub-agent (default from env: 'gemini-3.7-flash').
        effort: Reasoning effort for the session ('low', 'medium', 'high').
    
    Returns:
        The text output/log and summary of the completed task.
    """
    cwd = sanitize_workspace_path(sub_path)
    os.makedirs(cwd, exist_ok=True)
    logger.info(f"Executing sync Antigravity task in '{cwd}': {prompt[:100]}...")

    # If 'agy' CLI binary is installed, invoke agy with non-interactive and auto-approval flags
    agy_path = shutil.which("agy") or ("/root/.local/bin/agy" if os.path.exists("/root/.local/bin/agy") else None)
    if agy_path:
        cmd = [agy_path, "-p", prompt]
        if AUTO_APPROVE:
            cmd.append("--dangerously-skip-permissions")
        if model:
            cmd.extend(["--model", model])
        if effort and not any(model.endswith(s) for s in ["-low", "-medium", "-high"]):
            cmd.extend(["--effort", effort])
        if EXTRA_AGY_FLAGS:
            cmd.extend(EXTRA_AGY_FLAGS)
            
        try:
            logger.info(f"Invoking agy CLI: {' '.join(cmd)}")
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=os.environ.copy()
            )
            if res.returncode == 0:
                return res.stdout or "Task completed via Antigravity CLI with no output."
            return f"Antigravity CLI output (code {res.returncode}):\n{res.stdout}\n{res.stderr}"
        except Exception as e:
            logger.warning(f"agy CLI invocation failed: {e}. Running Gemini sub-agent engine.")

    # Native Gemini Autonomous Sub-Agent loop
    return run_gemini_agent_loop(prompt=prompt, cwd=cwd, model_name=model)


@mcp.tool()
def start_antigravity_async(
    prompt: str,
    sub_path: str = "",
    model: str = DEFAULT_MODEL
) -> str:
    """Dispatches a long-running Antigravity / Gemini Sub-Agent task in the background.
    
    Args:
        prompt: The task instruction or coding goal.
        sub_path: Optional sub-directory path inside /workspace to execute within.
        model: The Gemini model to use (default: 'gemini-3.7-flash').
        
    Returns:
        An 8-character task_id to inspect with get_antigravity_task_status.
    """
    task_id = str(uuid.uuid4())[:8]
    cwd = sanitize_workspace_path(sub_path)
    os.makedirs(cwd, exist_ok=True)
    logger.info(f"Launching async sub-agent task '{task_id}' in '{cwd}': {prompt[:100]}...")

    TASKS[task_id] = {
        "status": "running",
        "prompt": prompt,
        "output": "",
        "cwd": cwd,
        "model": model
    }

    def _worker():
        try:
            output = execute_antigravity_sync(prompt=prompt, sub_path=sub_path, model=model)
            TASKS[task_id]["status"] = "completed"
            TASKS[task_id]["output"] = output
            logger.info(f"Async task '{task_id}' completed successfully")
        except Exception as e:
            TASKS[task_id]["status"] = "error"
            TASKS[task_id]["output"] = str(e)
            logger.error(f"Async task '{task_id}' failed: {e}")

    threading.Thread(target=_worker, daemon=True).start()
    return (
        f"Task launched in background. Task ID: {task_id}. "
        "Check status using get_antigravity_task_status."
    )


@mcp.tool()
def get_antigravity_task_status(task_id: str) -> str:
    """Polls the status and output log of a background sub-agent task."""
    task = TASKS.get(task_id)
    if not task:
        return f"Task ID '{task_id}' was not found."

    if task["status"] == "running":
        return f"Task '{task_id}' is still in progress.\nPrompt: {task.get('prompt', '')}"

    return f"Status: {task['status']}\nModel: {task.get('model', DEFAULT_MODEL)}\nPrompt: {task.get('prompt', '')}\n\nOutput Log:\n{task['output']}"


@mcp.tool()
def list_antigravity_tasks() -> str:
    """Lists all background Antigravity sub-agent tasks and their current status."""
    if not TASKS:
        return "No background tasks have been launched."
    
    lines = ["Active & Completed Tasks:"]
    for tid, tinfo in TASKS.items():
        lines.append(f"- [{tid}] Status: {tinfo['status']} | Model: {tinfo.get('model', 'default')} | Prompt: {tinfo.get('prompt', '')[:60]}...")
    return "\n".join(lines)


@mcp.tool()
def run_sandboxed_shell(command: str, sub_path: str = "", timeout_seconds: int = 120) -> str:
    """Directly runs a shell command inside the sandboxed workspace.
    
    Args:
        command: The bash/shell command to execute (e.g. 'git status', 'npm test', 'pytest').
        sub_path: Optional sub-directory path inside /workspace.
        timeout_seconds: Maximum execution time (default: 120s).
    """
    cwd = sanitize_workspace_path(sub_path)
    os.makedirs(cwd, exist_ok=True)
    logger.info(f"Executing sandboxed shell in '{cwd}': {command}")
    return run_local_shell(command, cwd=cwd, timeout_seconds=timeout_seconds)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting Antigravity MCP Bridge on {host}:{port} via SSE transport...")
    mcp.run(transport="sse", host=host, port=port)
