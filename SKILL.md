---
name: antigravity-subagent-bridge
description: Delegate heavy coding, multi-file refactoring, debugging, file system operations, and terminal execution to the local containerized Antigravity Sub-Agent Bridge to conserve context and avoid rate limits.
---

# Antigravity Sub-Agent Delegation Skill

Use this skill when you need to execute coding tasks, edit files, run tests, or perform multi-step automation inside the user's workspace without burning primary context or hitting rate limits.

---

## 🛠️ When to Delegate to the Sub-Agent Bridge

Delegate to the `antigravity-bridge` MCP tools whenever a task involves:
1. **Multi-File Edits & Refactoring**: Writing or modifying multiple files in a repository.
2. **Terminal & Test Execution**: Running test suites (`npm test`, `pytest`, `cargo test`), linters, or build commands.
3. **Log & Repository Inspection**: Reading large files or directories in the `/workspace` tree.
4. **Heavy Computation**: Offloading multi-turn reasoning to conserve your conversational message quota.

---

## ⚡ Best Practices for Dispatches

### 1. Concrete & Unambiguous Prompts
* Always provide exact relative paths from the workspace root (e.g. `connormxy/antigravity-mcp-bridge/server.py`).
* Clearly state what changes to make and what command to run to verify the work.
* Keep `effort="low"` for fast sub-agent execution when your instructions are already specific.

### 2. Synchronous vs. Asynchronous Modes

* **Quick Tasks (< 45s)**:
  Call `execute_antigravity_sync(prompt="...", sub_path="...", effort="low")`.
  *Use for*: Single-file edits, bug fixes, running a quick command or inspection.

* **Long-Running Tasks (> 45s)**:
  Call `start_antigravity_async(prompt="...", sub_path="...", effort="low")`.
  1. Capture the returned `task_id`.
  2. Wait a few moments.
  3. Call `get_antigravity_task_status(task_id)` to check progress and view the full output log.

### 3. Direct Sandboxed Shell Execution
* For simple command execution (e.g. `git status`, `docker ps`, `ls -la`), call `run_sandboxed_shell(command="...", sub_path="...")` directly.

---

## 📋 Example Tool Calls

### Synchronous Task:
```json
execute_antigravity_sync({
  "prompt": "Fix the syntax error in src/index.ts and run npm test to verify.",
  "sub_path": "my-project",
  "effort": "low",
  "dangerously_skip_permissions": true
})
```

### Asynchronous Long Task:
```json
start_antigravity_async({
  "prompt": "Implement comprehensive unit tests for all functions in utils.py and run pytest.",
  "sub_path": "my-backend",
  "effort": "low",
  "dangerously_skip_permissions": true
})
```
