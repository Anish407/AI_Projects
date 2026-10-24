# GitLab Automation MCP

A Python Model Context Protocol (MCP) server that lets an AI client search GitLab projects, prepare release tags, and operate CI pipelines and jobs. Choose **Codex** for the client in section 1, or **Docker Agent with a local Ollama model** in section 2. Both use the same Docker image, GitLab credentials, and deployment skills.

These instructions use **Windows PowerShell**. Run project commands from the directory containing `DockerFile` and `requirements.txt`. Replace checkout paths with your own; do not copy another user's personal paths blindly.

## 1. Build and package the MCP server, then integrate it with Codex

### Step 1 — Understand the components

```text
Codex                               Docker Agent + Ollama
  |                                       |
  +----------- MCP over stdio ------------+
                      |
        Docker MCP Gateway --profile=gitlab
                      |
          gitlab-automation-mcp:local
                      |
              GitLab REST API
```

The MCP server is independent of the model. `src/server.py` registers Python functions as MCP tools and starts a stdio server. `src/gitlab_client.py` implements the GitLab API calls using HTTPX. The model selects tools; the server executes them against GitLab.

| File / configuration | What it does |
| --- | --- |
| `src/server.py` | Defines tool names, input schemas, and responses; runs MCP over stdin/stdout. |
| `src/gitlab_client.py` | Implements project discovery, tag numbering, tag creation, pipeline and job API requests. |
| `requirements.txt` | Installs the MCP SDK, HTTPX, and python-dotenv. |
| `DockerFile` | Packages Python dependencies and `src/` into an image; starts `python src/server.py`. Use `-f DockerFile` because of its capitalization. |
| `docker-mcp-server.yaml` | Describes the image, server metadata, allowed GitLab host, and secret-to-environment mappings to Docker MCP. |
| Docker MCP profile `gitlab` | Stores the registered server selection/configuration used by the gateway. A profile is not the Docker image itself. |
| `src/agent.yaml` | Docker Agent client configuration. Codex does not load this file. |
| `.agents/skills/*/SKILL.md` | Project-specific release workflows. Each has YAML name/description metadata followed by Markdown instructions. |
| `.codex/config.toml` or user `config.toml` | Codex MCP connection settings, separately from Docker Agent configuration. |
| `.env` | Credentials for direct Python execution only; excluded from Git and Docker build context. |
| `.mcp.json` | Existing direct-Python client example with checkout-specific paths. It does not configure Codex automatically or use the Docker profile. |
| `.dockerignore` / `.gitignore` | Exclude local credentials, virtual environments, and Python caches from builds / version control. |
| `tests/` | Mocked API tests; they do not create live tags or run GitLab jobs. |

The server exposes these **12 tools**:

| Tool | Purpose |
| --- | --- |
| `list_projects` | Search projects visible to the GitLab account. |
| `list_tags` | Read all pages of repository tags. |
| `get_next_tag` | Calculate the next `v<number>` or `proj<number>` tag without creating it. |
| `ensure_tag` | Resolve an exact namespace/project path and reuse or create an explicit tag. |
| `prepare_release` | Resolve the project, calculate an omitted tag name, and create/reuse it. Returns the real project ID and target SHA. |
| `create_tag` | Create an exact tag using a known project ID and ref. |
| `list_pipelines` | Read the 20 newest pipelines for an exact ref. |
| `trigger_pipeline` | Start a pipeline for a ref, optionally passing CI variables. |
| `list_pipeline_jobs` | Read job IDs, names, and statuses from a pipeline. |
| `play_job` | Start an existing manual job. |
| `get_pipeline_status` | Read pipeline status and details. |
| `get_job_log` | Read the final 20,000 characters of a job trace. |

Docker Agent deliberately does not expose `get_next_tag` in its current whitelist: `prepare_release` handles that operation without requiring the model to supply a numeric project ID. Codex can discover all server tools.

### Step 2 — Install the prerequisites

1. Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) and start it with Linux containers.
2. Enable **MCP Toolkit** in Docker Desktop if your installation requires it. Use a release supporting MCP profiles.
3. Install/sign in to [Codex](https://learn.chatgpt.com/docs/overview) for the Codex route.
4. Obtain a GitLab personal access token with `api` scope and sufficient project permissions to create tags, create pipelines, and play jobs. Protected tags may require additional role permissions. See [GitLab personal access tokens](https://docs.gitlab.com/user/profile/personal_access_tokens/).
5. Ensure the target repositories contain the intended branch (default `main`), CI configuration, and available runners if you plan to execute jobs.

Check that the CLI and engine are accessible:

```powershell
Set-Location 'D:\Projects\AI projects\MCPs\GitLab Automation\gitlab-mcp'
docker version
docker mcp version
docker mcp profile --help
```

`docker version` must show a **Server** section, not only the client version. This setup was checked with Docker Agent `v1.141.0` and Docker MCP `v0.43.3`; use your installed CLI help if options differ.

### Step 3 — Review the server definition

The included `docker-mcp-server.yaml` names the server `gitlab-automation`, references image `gitlab-automation-mcp:local`, and maps these secrets:

| Docker MCP secret | Container environment variable |
| --- | --- |
| `gitlab-automation.GITLAB_URL` | `GITLAB_URL` |
| `gitlab-automation.GITLAB_TOKEN` | `GITLAB_TOKEN` |

Its host allowlist is `gitlab.com:443`. For self-managed GitLab, change that entry to your actual hostname/port and use that instance's URL. After changing the definition, update its imported profile registration in step 6; the gateway does not automatically reread your checkout's YAML.

### Step 4 — Store the credentials in Docker MCP

Set the GitLab URL and enter the token without displaying it:

```powershell
'https://gitlab.com' | docker mcp secret set gitlab-automation.GITLAB_URL
$gitlabSecureToken = Read-Host 'GitLab personal access token' -AsSecureString
$gitlabPlainToken = [System.Net.NetworkCredential]::new('', $gitlabSecureToken).Password
$gitlabPlainToken | docker mcp secret set gitlab-automation.GITLAB_TOKEN
Remove-Variable gitlabSecureToken, gitlabPlainToken
docker mcp secret ls
```

The last command lists secret names. Keep tokens out of source files, image layers, and command-line arguments. An `.env` file is unnecessary for the Docker Gateway route.

### Step 5 — Build the image

```powershell
docker build -f DockerFile -t gitlab-automation-mcp:local .
docker image inspect gitlab-automation-mcp:local --format '{{.Id}}'
```

The build uses `python:3.12-slim`, installs `requirements.txt`, copies `src/`, and sets the server entrypoint. The image contains tool code; skills remain on the client's local filesystem. The gateway launches the container and discovers its tools through the MCP protocol. No published container port is needed for stdio.

### Step 6 — Register the server in the Docker MCP profile

Docker MCP restricts file server definitions to its catalog directory. Copy the file there:

```powershell
$gitlabCatalogDir = Join-Path $env:USERPROFILE '.docker\mcp\catalogs\servers'
New-Item -ItemType Directory -Path $gitlabCatalogDir -Force | Out-Null
Copy-Item -LiteralPath '.\docker-mcp-server.yaml' -Destination (Join-Path $gitlabCatalogDir 'gitlab.yaml') -Force
```

For a new profile:

```powershell
docker mcp profile create --name gitlab --id gitlab --server file://servers/gitlab.yaml
```

If `gitlab` already exists, **add/update the server instead of creating another profile**:

```powershell
docker mcp profile server add gitlab --server file://servers/gitlab.yaml
```

Verify the registration:

```powershell
docker mcp profile show gitlab
docker mcp profile server ls --filter profile=gitlab
```

You can also inspect **Docker Desktop → MCP Toolkit → Profiles → gitlab**. This local server is not necessarily listed in the public catalog.

### Step 7 — Verify discovery and a read-only GitLab call

```powershell
docker mcp tools list --verbose --gateway-arg=--profile=gitlab
docker mcp tools call list_projects search=myproj --gateway-arg=--profile=gitlab
```

Expect all 12 GitLab tools and actual project results from the second command. Discovery alone does not prove token authentication works. Do not use `prepare_release` as a connection test: it can create a tag.

You normally do **not** start a separate gateway terminal. Each client starts its gateway subprocess. To inspect startup without attaching a client:

```powershell
docker mcp gateway run --profile=gitlab --dry-run --verbose
```

### Step 8 — Connect Codex to the gateway

Merge this into `%USERPROFILE%\.codex\config.toml`, preserving existing configuration. Edit an existing `mcp_servers.gitlab` table rather than duplicating it. A trusted project-scoped `.codex/config.toml` is another option.

```toml
[mcp_servers.gitlab]
command = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
args = ["mcp", "gateway", "run", "--profile=gitlab"]
startup_timeout_sec = 60

[mcp_servers.gitlab.env]
PATH = 'C:\Program Files\Docker\Docker\resources\bin;C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem'
```

Adjust the executable path if Docker is installed elsewhere. The explicit `PATH` lets the gateway find both Docker and its credential helper when it launches child processes.

If you have the Codex CLI, check registration with:

```powershell
codex mcp list
```

Restart Codex after changing MCP configuration. Open the `gitlab-mcp` folder as the project; in the CLI, launch `codex` from that folder and use `/mcp` to inspect the connection. Ask it to list projects first. Codex reads this TOML connection configuration, not `src/agent.yaml`. See [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

### Step 9 — Use the deployment skills in Codex

The existing directories are already in a Codex discovery location:

```text
.agents/skills/
  deploy-myproj/SKILL.md
  deploy-myproj2/SKILL.md
```

Open/start Codex in this project directory so it can discover them. Merely having skills in a separate or remote GitLab repository does not make them available to this session. Codex initially sees names/descriptions, then reads the selected skill instructions. See [local skill discovery](https://learn.chatgpt.com/docs/build-skills).

Examples:

```text
Use $deploy-myproj to deploy proj.
Use $deploy-myproj2 to deploy proj2 and run the build_app job.
Use $deploy-myproj2 to create tag v2 in myproj2 and run build_app.
```

These are live operations: tag creation can trigger CI. `myproj` maps to `anish5416/myproj` and defaults to `v1`, `v2`, etc. `myproj2` maps to `anish5416/myproj2` and defaults to `proj1`, `proj2`, etc. Automatic numbering uses the highest matching integer, not creation date or alphabetical ordering. Explicit tag names override the default format.

Before using this checkout with other GitLab projects, edit the project paths, aliases, prefixes, and job defaults in both skill files and `src/agent.yaml`. The Python tool code does not hardcode these project IDs.

### Step 10 — Optional: run the Python MCP server directly

This alternative bypasses Docker Desktop, the image, the gateway profile, and Docker secrets. It requires Python 3.12+ on the host.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a local `.env` file in the project root:

```dotenv
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your_personal_access_token
```

Use this **instead of** the gateway's `[mcp_servers.gitlab]` block, with your actual absolute paths:

```toml
[mcp_servers.gitlab]
command = 'D:\Projects\AI projects\MCPs\GitLab Automation\gitlab-mcp\.venv\Scripts\python.exe'
args = ['D:\Projects\AI projects\MCPs\GitLab Automation\gitlab-mcp\src\server.py']
startup_timeout_sec = 60
```

Remove the gateway-specific `[mcp_servers.gitlab.env]` table for this alternative. Restart Codex. Running `src/server.py` alone starts a protocol process that waits for an MCP client; it is not an interactive chat application.

For local development, run the mocked tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## 2. Run locally with Docker Agent and Ollama, and use skills

### Step 1 — Complete the shared Docker/GitLab setup

Complete section 1, steps **2–7**, skipping the Codex installation if using only Docker Agent. You need the image, secrets, and `gitlab` profile. Codex configuration is not required for this route.

Verify Docker Agent is available:

```powershell
docker agent version
docker agent --help
```

If unavailable, follow the [Docker Agent installation guide](https://docs.docker.com/ai/docker-agent/) for your platform/version. The commands below use `docker agent`, the Docker CLI plugin.

### Step 2 — Install and start Ollama

Install [Ollama](https://ollama.com/download), then download the configured model:

```powershell
ollama pull llama3.2
ollama list
```

Ollama normally starts its local server automatically. If it is not running, use `ollama serve` in a separate terminal and leave it running. Do not start a second server if the default port is already in use.

Check its model endpoint:

```powershell
Invoke-RestMethod -Uri 'http://localhost:11434/v1/models'
```

Docker Agent's `ollama/llama3.2` configuration connects to the local OpenAI-compatible endpoint at `http://localhost:11434/v1`; no hosted model API key is needed. GitLab API requests still need network access and the GitLab token. See [Docker Agent local providers](https://docs.docker.com/ai/docker-agent/providers/local/).

### Step 3 — Understand the agent configuration

Use the supplied `src/agent.yaml`. Its structure is:

```yaml
agents:
  root:
    model: ollama/llama3.2
    skills: [deploy-myproj, deploy-myproj2]
    instruction: |
      Use the GitLab MCP tools and load the matching deployment skill.
    toolsets:
      - type: user_prompt
      - type: filesystem
      - type: mcp
        command: docker
        args: ["mcp", "gateway", "run", "--profile=gitlab"]
        env:
          PATH: 'C:\Program Files\Docker\Docker\resources\bin;C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem'
```

This excerpt explains the structure; the actual file contains more instructions and the complete tool whitelist. Keep that file rather than replacing it with this abbreviated example.

- `model` selects the local Ollama model.
- `instruction` supplies shared routing and result-reporting rules.
- `skills` selects the discovered deployment workflows by name.
- `filesystem` lets the agent read skill files.
- `user_prompt` lets it ask for a concrete alternative job choice and resume after approval.
- The `mcp` toolset starts the Docker Gateway subprocess using the `gitlab` profile.
- Its `tools` whitelist controls which discovered GitLab tools the model sees.
- Its `env.PATH` fixes Windows child-process lookup of Docker.

Ollama generates model responses; it does not connect to GitLab or run the MCP server itself. Docker Agent executes the model's tool calls through the gateway.

### Step 4 — Understand how skills are loaded

A skill is a folder containing `SKILL.md`, for example:

```markdown
---
name: deploy-myproj2
description: Create or reuse a release tag in anish5416/myproj2 and run a requested GitLab job.
---

Project-specific workflow instructions go here.
```

The agent discovers local skill metadata when starting, then loads a matching skill through `read_skill`. Its full instructions enter context when selected, rather than putting every project's full workflow in the main agent instructions. The skills are not registered inside the Docker profile. See [Docker Agent skills](https://docs.docker.com/ai/docker-agent/features/skills/).

The included workflows:

| Request | Project | Default behavior |
| --- | --- | --- |
| `deploy proj` | `anish5416/myproj` | Prepare the next `v<number>` tag on `main`; run a job only if requested. |
| `deploy proj2` | `anish5416/myproj2` | Prepare the next `proj<number>` tag on `main`, then run `build_app`. |
| Explicit tag/job request | The named project's exact path | Honor the supplied tag and job names instead of defaults. |

For new projects, create another `.agents/skills/<skill-name>/SKILL.md`, configure its exact project path and workflow, and add its name to `skills` in `src/agent.yaml`. Update shared routing only as needed. No image rebuild is needed for skill-only edits, because clients read skills locally.

### Step 5 — Verify tools and skills before running

From the project root:

```powershell
docker agent debug skills .\src\agent.yaml
docker agent debug toolsets .\src\agent.yaml
```

Expect both deployment skills, `read_skill`, `user_prompt`, filesystem tools, and the **11 GitLab tools whitelisted in the agent configuration**, including `prepare_release`, `list_pipeline_jobs`, and `play_job`. The server itself has 12 GitLab tools, but this agent hides `get_next_tag` to avoid placeholder project-ID calls.

### Step 6 — Start the agent and request a release

```powershell
docker agent run .\src\agent.yaml
```

Use `/tools` to inspect available tools. Start with a read-only request such as `list my GitLab projects`, then use a live workflow:

```text
deploy proj2
deploy proj2 and run the build_app job in the pipeline that is triggered
create a tag v2 in myproj2 and run the build_app GitLab job
```

If automatic skill selection fails, explicitly request:

```text
Use the deploy-myproj2 skill to deploy proj2 and run build_app.
```

The configured workflow:

1. Load the correct skill and exact namespace/project path.
2. Call `prepare_release`, which resolves the real project ID internally. For an omitted tag, calculate the next matching number. For an explicit tag, reuse it if present or create it if absent.
3. Use the confirmed project ID, tag, and target SHA from the tool response.
4. Find the newest pipeline matching both tag ref and SHA. Allow the tag-triggered pipeline to appear; if none exists, start one on that tag.
5. Read the actual pipeline job names and IDs.
6. Run the requested/default job if it is manual, or monitor it if already scheduled. If missing, show actual alternatives and ask before playing a different job.
7. After approval, continue on the same tag/pipeline with the approved job. Do not create another release.
8. Report the verified job state and links. Tag creation or job scheduling is not proof that an application has been deployed.

GitLab CI rules determine which other automatic jobs run. `play_job` starts manual jobs; it cannot make a job omitted by CI rules appear. Existing tags are reused without being moved, even if `main` has changed.

### Step 7 — Apply updates correctly

After changing server/tool code:

```powershell
docker build -f DockerFile -t gitlab-automation-mcp:local .
```

Then close the agent and start a fresh session. Restart the Codex MCP connection too if using Codex. Existing gateway processes/containers may still use the previous image.

After changing `docker-mcp-server.yaml`, copy it to the catalog directory again and run the profile server add/update command from section 1, step 6.

After changing skills or `src/agent.yaml`, restart Docker Agent in a fresh conversation; no image rebuild is needed unless Python code changed. Avoid resuming old conversations that contain invented IDs or outdated tool descriptions.

### Step 8 — Troubleshoot each layer

| Symptom | Check / resolution |
| --- | --- |
| `1 toolset, 0 tools` | Run the gateway's verbose tool listing first. Inspect startup errors rather than assuming a model problem. |
| `exec: "docker": executable file not found in %PATH%` | Ensure the MCP subprocess `PATH` includes Docker's installation directory. An absolute initial executable path alone does not fix the gateway's child-process lookup. |
| `Docker Desktop is not running` | Verify Desktop is open and `docker version` includes Server details. A restricted/sandboxed terminal may lack Docker named-pipe access even while Desktop is running. |
| Only unrelated tools appear | Verify `--profile=gitlab` is present; the default profile can contain different servers. |
| Tools list succeeds but GitLab calls fail | Check secret retrieval, token expiration/scope, project permissions, and the configured GitLab URL/host. |
| Ollama connection refused / model missing | Start Ollama, check `/v1/models`, run `ollama list`, and pull `llama3.2` if absent. |
| Agent invents an ID or uses `get_project_id` as a string | Start a fresh session with current configuration. Use `prepare_release` with the exact project path; a placeholder is a malformed model call, not missing information from the user. |
| Requested job does not appear | Inspect `list_pipeline_jobs`, check tag CI rules and actual job names. Approve a suggested alternative only if it is the job you want. |
| Agent claims success without tool evidence | Verify returned tag target and actual job status. Skills guide the model but do not guarantee compliance. |
| Profile tools tab is blank | Prefer CLI discovery as evidence; reopen the Desktop view and confirm the selected profile. |

Capture Docker Agent diagnostics:

```powershell
docker agent --debug debug toolsets .\src\agent.yaml
Get-Content -LiteralPath "$env:USERPROFILE\.cagent\cagent.debug.log" -Tail 60
```

Local `llama3.2` testing previously produced invented IDs, invalid arguments, and unsupported success claims. The current tool design reduces those failure modes, but a successful discovery test is not proof of reliable end-to-end model behavior. Review actual tool results and GitLab state when diagnosing a run.

The current mocked test suite verifies tag numbering/pagination, existing-tag reuse, lost-response recovery, project-path release preparation, pipeline filtering, job listing, and the play endpoint. It does not certify live CI deployment or model instruction-following.
