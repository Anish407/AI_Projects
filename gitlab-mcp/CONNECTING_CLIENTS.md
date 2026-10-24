# Connect GitLab MCP to clients

This guide connects clients to the `gitlab` Docker MCP profile. The profile contains the `gitlab-automation` server definition; Docker MCP Gateway launches the container and exposes its MCP tools to clients over stdio.

Before connecting, make sure this works from PowerShell:

```powershell
docker mcp tools list --verbose --gateway-arg=--profile=gitlab
```

It should list `list_projects`, `create_tag`, `trigger_pipeline`, `get_pipeline_status`, and `get_job_log`.

## Codex

Codex reads MCP server settings from `%USERPROFILE%\.codex\config.toml`. Add this block:

```toml
[mcp_servers.gitlab]
command = "docker"
args = ["mcp", "gateway", "run", "--profile", "gitlab"]
```

Alternatively, use the Codex CLI to register a stdio server if supported by your installed version:

```powershell
codex mcp add gitlab -- docker mcp gateway run --profile gitlab
codex mcp list
```

Restart or start a new Codex session so it loads the configuration. This connects Codex to the Gateway; Codex does not read `docker-mcp-server.yaml` directly.

## Visual Studio Code

For workspace-only setup, create `.vscode/mcp.json` in the project where you use Copilot Chat:

```json
{
  "servers": {
    "MCP_DOCKER": {
      "type": "stdio",
      "command": "docker",
      "args": ["mcp", "gateway", "run", "--profile", "gitlab"]
    }
  }
}
```

Then open Copilot Chat in **Agent** mode, open the tools picker, and enable the GitLab tools. If the project is under source control, add `.vscode/mcp.json` to `.gitignore` if you do not want to share your local client configuration.

VS Code may also discover the root `.mcp.json` already in this project. That file launches the local Python server directly using `.venv`; it does **not** route through Docker MCP Gateway or use Docker MCP secrets. Use the `.vscode/mcp.json` configuration above when you want this client to use the Docker image and `gitlab` profile.

## Docker Agent (`agent.yaml`)

Docker Agent uses its own agent configuration file, commonly named `agent.yaml`. It does not use `docker-mcp-server.yaml` as its agent definition. Add the MCP toolset under the agent's `toolsets` list:

```yaml
agents:
  root:
    # Keep your existing model, instructions, and other settings.
    toolsets:
      - type: mcp
        command: docker
        args: ["mcp", "gateway", "run", "--profile", "gitlab"]
```

Run that agent configuration with Docker Agent. The agent starts `docker mcp gateway run --profile gitlab` as an MCP stdio process; the Gateway then starts the configured GitLab container. The two YAML files have different jobs:

- `docker-mcp-server.yaml` describes the **GitLab MCP server** to Docker MCP Gateway: image, display metadata, secrets, and allowed network host.
- `agent.yaml` describes the **Docker Agent client** and tells it to connect to the Gateway profile.

## How the files fit together

```text
Codex / VS Code / Docker Agent
              │ MCP over stdio
              ▼
Docker MCP Gateway (profile: gitlab)
              │ starts container and routes tool calls
              ▼
gitlab-automation-mcp:local
              │ HTTPS GitLab REST API
              ▼
GitLab
```

The clients connect to the Gateway, not directly to the image metadata file. The Gateway uses the server definition saved under `%USERPROFILE%\.docker\mcp\catalogs\servers\gitlab.yaml` and the `gitlab` profile to start the container.

## Troubleshooting

- If a client only shows Playwright, it is probably using the `default` profile. Confirm its Gateway arguments include `--profile gitlab`.
- If Docker CLI lists the five GitLab tools but Docker Desktop's profile **Tools** tab is blank, restart Docker Desktop and reopen the `gitlab` profile.
- If tools appear but calls fail authentication, check that Docker MCP can retrieve `gitlab-automation.GITLAB_URL` and `gitlab-automation.GITLAB_TOKEN` from its secret store.
- On Windows, Docker MCP Gateway may take longer than a normal local process to start. If a client times out during connection, increase its MCP startup timeout where supported.

## References

- [Codex MCP setup](https://developers.openai.com/learn/docs-mcp)
- [VS Code MCP configuration](https://code.visualstudio.com/docs/agents/reference/mcp-configuration)
- [Docker MCP Profiles](https://docs.docker.com/ai/mcp-catalog-and-toolkit/profiles/)
- [Docker Agent MCP tool configuration](https://docs.docker.com/ai/docker-agent/configuration/tools/)
