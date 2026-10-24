from pathlib import Path

from dotenv import load_dotenv
from mcp.server import MCPServer

from gitlab_client import GitLabClient


# This file is directly inside src/, so its parent directory is the project root.
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")


mcp = MCPServer("gitlab-deployment-mcp")


def get_gitlab_client() -> GitLabClient:
    return GitLabClient()


@mcp.tool()
def list_projects(search: str | None = None) -> list[dict]:
    """
    Search GitLab projects visible to the configured GitLab account.

    Use this when the user mentions a project by name but the exact
    GitLab project ID is not yet known.

    Args:
        search:
            Optional project name or partial project name.
            Example: "proj1"

    Returns:
        Matching GitLab projects.
    """

    client = get_gitlab_client()

    return client.list_projects(search=search)


@mcp.tool()
def list_tags(project_id: int) -> list[dict]:
    """List all repository tags across all pages, including name and target SHA."""
    client = get_gitlab_client()
    try:
        return client.list_tags(project_id)
    finally:
        client.close()


@mcp.tool()
def get_next_tag(project_id: int, prefix: str) -> dict:
    """Read tags and calculate the next numbered tag without creating it.

    Use prefix 'v' for v1, v2, ... or 'proj' for proj1, proj2, ... .
    Selects the largest positive integer, not the newest date or lexical order.
    Ignores other tag formats; starts at 1 when there are no matching tags.
    Returns latest_tag and next_tag. Use create_tag to create next_tag.
    """
    client = get_gitlab_client()
    try:
        return client.get_next_tag(project_id, prefix)
    finally:
        client.close()


@mcp.tool()
def prepare_release(project_path: str, prefix: str, tag_name: str | None = None,
                    ref: str = "main") -> dict:
    """Resolve project and create/reuse a release tag, without needing a project ID.

    For deploy proj2: project_path=anish5416/myproj2, prefix=proj.
    For deploy proj: project_path=anish5416/myproj, prefix=v.
    Omit tag_name to calculate the next numbered tag. Provide tag_name to use
    an explicitly requested tag. Returns real project_id, name, target, created.
    This creates tags but does not run pipelines or jobs.
    """
    client = get_gitlab_client()
    try:
        return client.prepare_release(project_path, prefix, tag_name, ref)
    finally:
        client.close()


@mcp.tool()
def ensure_tag(project_path: str, tag_name: str, ref: str = "main") -> dict:
    """Find or create an exact tag in an exact namespace/project path.

    Resolves the real project ID; no guessed ID is needed. Existing tags are
    reused without moving them. Missing tags are created from ref, default main.
    Returns project_id, project_path, name, target SHA, and created boolean.
    Use this for explicit requests such as v2 in anish5416/myproj2.
    """
    client = get_gitlab_client()
    try:
        return client.ensure_tag(project_path, tag_name, ref)
    finally:
        client.close()


@mcp.tool()
def create_tag(
    project_id: int,
    tag_name: str,
    ref: str,
) -> dict:
    """
    Create a Git tag in a GitLab project.

    Args:
        project_id:
            GitLab project ID.

        tag_name:
            Name of the tag to create.

        ref:
            Branch, existing tag, or commit SHA from which
            the new tag should be created.
    """

    client = get_gitlab_client()

    result = client.create_tag(
        project_id=project_id,
        tag_name=tag_name,
        ref=ref,
    )

    return {
        "name": result["name"],
        "target": result["target"],
    }


@mcp.tool()
def trigger_pipeline(
    project_id: int,
    ref: str,
    variables: dict[str, str] | None = None,
) -> dict:
    """
    Trigger a GitLab CI/CD pipeline.

    Args:
        project_id:
            GitLab project ID.

        ref:
            Branch or tag to run the pipeline against.

        variables:
            Optional GitLab CI/CD variables.
    """

    client = get_gitlab_client()

    result = client.trigger_pipeline(
        project_id=project_id,
        ref=ref,
        variables=variables,
    )

    return {
        "pipeline_id": result["id"],
        "status": result["status"],
        "ref": result["ref"],
        "web_url": result.get("web_url"),
    }


@mcp.tool()
def get_pipeline_status(
    project_id: int,
    pipeline_id: int,
) -> dict:
    """
    Get the current status of a GitLab pipeline.

    Args:
        project_id:
            GitLab project ID.

        pipeline_id:
            GitLab pipeline ID.
    """

    client = get_gitlab_client()

    result = client.get_pipeline_status(
        project_id=project_id,
        pipeline_id=pipeline_id,
    )

    return {
        "pipeline_id": result["id"],
        "status": result["status"],
        "ref": result["ref"],
        "sha": result["sha"],
        "web_url": result.get("web_url"),
    }


@mcp.tool()
def get_job_log(
    project_id: int,
    job_id: int,
) -> str:
    """
    Get the execution log for a GitLab CI/CD job.

    Args:
        project_id:
            GitLab project ID.

        job_id:
            GitLab job ID.
    """

    client = get_gitlab_client()

    log = client.get_job_log(
        project_id=project_id,
        job_id=job_id,
    )

    max_length = 20_000

    if len(log) > max_length:
        return log[-max_length:]

    return log


@mcp.tool()
def list_pipelines(project_id: int, ref: str) -> list[dict]:
    """List the 20 newest pipelines for an exact branch or tag ref, newest first."""
    client = get_gitlab_client()
    try:
        return client.list_pipelines(project_id, ref)
    finally:
        client.close()


@mcp.tool()
def list_pipeline_jobs(project_id: int, pipeline_id: int) -> list[dict]:
    """List all jobs in a pipeline, including actual job IDs, names and statuses."""
    client = get_gitlab_client()
    try:
        return client.list_pipeline_jobs(project_id, pipeline_id)
    finally:
        client.close()


@mcp.tool()
def play_job(project_id: int, job_id: int) -> dict:
    """Start an existing manual GitLab CI job. Use an ID from list_pipeline_jobs.

    Only call for a job with status manual that the user asked to run.
    Does not create a pipeline or retry failed jobs.
    """
    client = get_gitlab_client()
    try:
        return client.play_job(project_id, job_id)
    finally:
        client.close()


if __name__ == "__main__":
    mcp.run()
