# Antigravity Sub-Agent Bridge (FastMCP)

A containerized **FastMCP** server that exposes the **Google Antigravity CLI (`agy --headless`)** as remote Model Context Protocol (MCP) tools over **SSE**.

This bridge allows conversational AI clients (such as **Google Spark**, Claude, Cursor, or ChatGPT) to dispatch full coding and automation sub-agents in a sandboxed, containerized workspace.

---

## 🚀 Key Features

* **Synchronous Sub-Agent Execution (`execute_antigravity_sync`)**:
  Dispatches a coding/automation task directly to `agy --headless` and returns the output log once the agent finishes (ideal for short 1–3 minute tasks).
* **Asynchronous Background Execution (`start_antigravity_async`)**:
  Spawns a long-running Antigravity agent in the background, returning a `task_id` for decoupled execution.
* **Task Polling & Management (`get_antigravity_task_status`, `list_antigravity_tasks`)**:
  Polls progress, inspects logs, and lists all background sub-agents.
* **Workspace Isolation & Sandboxing**:
  Runs within a Docker container mounting only `./workspaces`, protecting host system files while giving the agent full build, test, and execution autonomy inside its sandbox.
* **Seamless Integration with `mcp-server-oauth-proxy`**:
  Exposes standard SSE endpoints on port `8080/sse`, pluggable directly into Home Assistant's OAuth proxy for secure access from Google Spark.

---

## 🛠️ Repository Layout

```
antigravity-mcp-bridge/
├── Dockerfile              # Container image with Python 3.12, Node.js, git, & agy CLI
├── docker-compose.yml      # Service definitions with volume mounts & port bindings
├── requirements.txt        # fastmcp, mcp[cli], pydantic
├── server.py               # FastMCP Server exposing Antigravity agent tools
├── .env.example            # Environment variable template
├── .gitignore              # Ignored artifacts & workspace directories
└── README.md               # Documentation
```

## ⚙️ Environment Configuration

You can customize the sub-agent behavior by editing `.env`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DEFAULT_MODEL` | `gemini-3.7-flash` | The model used for sub-agent execution (`gemini-3.7-flash`, `gemini-2.5-flash`, `gemini-2.0-flash`). |
| `DEFAULT_EFFORT` | `high` | Reasoning effort for `agy` CLI sessions (`low`, `medium`, `high`). |
| `AUTO_APPROVE_PERMISSIONS` | `true` | When `true`, passes `--dangerously-skip-permissions` (YOLO mode) to avoid interactive prompts. |
| `DEFAULT_TIMEOUT_SECONDS` | `300` | Execution timeout in seconds. |
| `EXTRA_AGY_FLAGS` | `""` | Any extra flags to pass directly to `agy` CLI (e.g. `"--sandbox"`). |
| `WORKSPACE_DIR` | `/workspace` | Sandbox workspace directory inside container. |
| `GEMINI_API_KEY` | `""` | Optional API key for Google GenAI / Gemini models. |

---

## 📦 Quickstart & Deployment

### 1. Configure Environment
Copy the `.env.example` template:
```bash
cp .env.example .env
```
*(Optional: Add your `GEMINI_API_KEY` or `ANTIGRAVITY_API_KEY` if required by your `agy` environment).*

### 2. Start with Docker Compose
```bash
docker compose up -d --build
```

The FastMCP server will start listening on:
👉 **`http://localhost:8085/sse`** (or your host LAN IP).

### 3. Verify Container Health
```bash
docker compose logs -f
```

---

## 🔗 Connecting to `mcp-server-oauth-proxy`

To expose this Antigravity sub-agent bridge securely to **Google Spark** via your Home Assistant OAuth proxy:

1. In Home Assistant, open **Settings > Add-ons > MCP Server OAuth Proxy > Configuration**.
2. Add a new server entry under `servers`:

```yaml
    - client_name: "Google Spark"
      server_name: "Antigravity Bridge"
      server_url: "http://<YOUR_DOCKER_HOST_IP>:8085/sse"
      bearer_token: ""
      client_id: "spark-antigravity"
      client_secret: "secret-antigravity"
      allowed_redirect_uris: "https://oauth-redirect.googleusercontent.com"
      host: "antigravity-oauth.yourdomain.com"
      path_prefix: ""
```

3. Save and restart the add-on.
4. In **Google Spark**, add the custom tool pointing to `https://antigravity-oauth.yourdomain.com/sse` with Client ID `spark-antigravity`.

---

## 🧰 Available MCP Tools

### 1. `execute_antigravity_sync`
* **Description**: Executes a task synchronously via `agy --headless` and waits for output.
* **Parameters**:
  * `prompt` *(string, required)*: The goal or coding instruction.
  * `sub_path` *(string, optional)*: Subdirectory in `/workspace` to execute within.
  * `timeout_seconds` *(int, default: 300)*: Max seconds to wait before aborting.

### 2. `start_antigravity_async`
* **Description**: Starts an Antigravity task in the background and returns a `task_id`.
* **Parameters**:
  * `prompt` *(string, required)*: The goal or coding instruction.
  * `sub_path` *(string, optional)*: Subdirectory in `/workspace` to execute within.

### 3. `get_antigravity_task_status`
* **Description**: Inspects progress and full logs of a background task.
* **Parameters**:
  * `task_id` *(string, required)*: The 8-character ID returned by `start_antigravity_async`.

### 4. `list_antigravity_tasks`
* **Description**: Lists all active and completed background tasks.
