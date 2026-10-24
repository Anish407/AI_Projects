import os
import re
from urllib.parse import quote

import httpx
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[1]

load_dotenv(project_root / ".env")

class GitLabClient:
    def __init__(self):
        self.gitlab_url = os.environ["GITLAB_URL"].rstrip("/")
        self.token = os.environ["GITLAB_TOKEN"]

        self.client = httpx.Client(
            base_url=f"{self.gitlab_url}/api/v4",
            headers={
                "PRIVATE-TOKEN": self.token
            },
            timeout=30.0,
        )

    def list_projects(self, search: str | None = None) -> list[dict]:
        """
        List GitLab projects visible to the authenticated user.

        If search is provided, GitLab filters projects by name/path.
        """

        params = {
            "membership": True,
            "simple": True,
            "per_page": 50,
            "order_by": "name",
            "sort": "asc",
        }

        if search:
            params["search"] = search

        response = self.client.get(
            "/projects",
            params=params,
        )

        response.raise_for_status()

        projects = response.json()

        return [
            {
                "id": project["id"],
                "name": project["name"],
                "path": project["path"],
                "path_with_namespace": project["path_with_namespace"],
                "default_branch": project.get("default_branch"),
                "web_url": project.get("web_url"),
            }
            for project in projects
        ]

    def create_tag(
        self,
        project_id: int,
        tag_name: str,
        ref: str,
    ) -> dict:
        """
        Create a Git tag in the specified project.
        """

        response = self.client.post(
            f"/projects/{project_id}/repository/tags",
            params={
                "tag_name": tag_name,
                "ref": ref,
            },
        )

        response.raise_for_status()

        return response.json()

    def list_tags(self, project_id: int) -> list[dict]:
        """Read every page of repository tags, without relying on sort order."""
        tags = []
        page = 1
        while True:
            response = self.client.get(
                f"/projects/{project_id}/repository/tags",
                params={"per_page": 100, "page": page},
            )
            response.raise_for_status()
            batch = response.json()
            tags.extend({"name": tag["name"], "target": tag["target"]} for tag in batch)
            next_page = response.headers.get("X-Next-Page")
            if next_page:
                page = int(next_page)
            elif len(batch) == 100:
                page += 1
            else:
                return tags

    def get_next_tag(self, project_id: int, prefix: str) -> dict:
        """Calculate the next positive integer tag; this does not create it."""
        if prefix not in {"v", "proj"}:
            raise ValueError("Supported prefixes are 'v' and 'proj'.")
        pattern = re.compile(re.escape(prefix) + r"([1-9][0-9]*)")
        latest_name = None
        latest_number = 0
        for tag in self.list_tags(project_id):
            match = pattern.fullmatch(tag["name"])
            if match and int(match[1]) > latest_number:
                latest_name = tag["name"]
                latest_number = int(match[1])
        return {
            "latest_tag": latest_name,
            "next_tag": f"{prefix}{latest_number + 1}",
        }

    def prepare_release(self, project_path: str, prefix: str,
                        tag_name: str | None = None, ref: str = "main") -> dict:
        """Resolve project, calculate an omitted tag, and ensure that tag exists."""
        if tag_name is None:
            response = self.client.get(f"/projects/{quote(project_path, safe='')}")
            response.raise_for_status()
            project = response.json()
            if project["path_with_namespace"] != project_path:
                raise ValueError("Resolved project path does not match the requested project.")
            next_tag = self.get_next_tag(project["id"], prefix)
            tag_name = next_tag["next_tag"]
        else:
            next_tag = None
        result = self.ensure_tag(project_path, tag_name, ref)
        if next_tag is not None:
            result["previous_tag"] = next_tag["latest_tag"]
        return result

    def ensure_tag(self, project_path: str, tag_name: str, ref: str = "main") -> dict:
        """Resolve the exact project and reuse or create a tag without moving it."""
        response = self.client.get(f"/projects/{quote(project_path, safe='')}")
        response.raise_for_status()
        project = response.json()
        if project["path_with_namespace"] != project_path:
            raise ValueError("Resolved project path does not match the requested project.")
        project_id = project["id"]
        for tag in self.list_tags(project_id):
            if tag["name"] == tag_name:
                return {"project_id": project_id, "project_path": project_path,
                        "name": tag_name, "target": tag["target"], "created": False}
        try:
            tag = self.create_tag(project_id, tag_name, ref)
        except (httpx.HTTPStatusError, httpx.RequestError):
            # A concurrent creator or lost response may have created the tag.
            for existing in self.list_tags(project_id):
                if existing["name"] == tag_name:
                    return {"project_id": project_id, "project_path": project_path,
                            "name": tag_name, "target": existing["target"], "created": False}
            raise
        return {"project_id": project_id, "project_path": project_path,
                "name": tag["name"], "target": tag["target"], "created": True}

    def trigger_pipeline(
        self,
        project_id: int,
        ref: str,
        variables: dict[str, str] | None = None,
    ) -> dict:
        """
        Trigger a GitLab pipeline for the specified project.
        """

        data = {
            "ref": ref,
        }

        if variables:
            data["variables"] = [
                {
                    "key": key,
                    "value": value,
                }
                for key, value in variables.items()
            ]

        response = self.client.post(
            f"/projects/{project_id}/pipeline",
            json=data,
        )

        response.raise_for_status()

        return response.json()

    def get_pipeline_status(
        self,
        project_id: int,
        pipeline_id: int,
    ) -> dict:
        """
        Get details and current status for a pipeline.
        """

        response = self.client.get(
            f"/projects/{project_id}/pipelines/{pipeline_id}"
        )

        response.raise_for_status()

        return response.json()

    def get_job_log(
        self,
        project_id: int,
        job_id: int,
    ) -> str:
        """
        Get the execution log/trace for a GitLab CI/CD job.
        """

        response = self.client.get(
            f"/projects/{project_id}/jobs/{job_id}/trace"
        )

        response.raise_for_status()

        return response.text

    def close(self):
        """
        Close the underlying HTTP connection pool.
        """

        self.client.close()

    def list_pipelines(self, project_id: int, ref: str) -> list[dict]:
        response = self.client.get(
            f"/projects/{project_id}/pipelines",
            params={"ref": ref, "order_by": "id", "sort": "desc", "per_page": 20},
        )
        response.raise_for_status()
        return response.json()

    def list_pipeline_jobs(self, project_id: int, pipeline_id: int) -> list[dict]:
        jobs = []
        page = 1
        while True:
            response = self.client.get(
                f"/projects/{project_id}/pipelines/{pipeline_id}/jobs",
                params={"per_page": 100, "page": page, "include_retried": False},
            )
            response.raise_for_status()
            batch = response.json()
            jobs.extend({key: job.get(key) for key in
                         ("id", "name", "stage", "status", "ref", "web_url", "failure_reason")}
                        for job in batch)
            next_page = response.headers.get("X-Next-Page")
            if next_page:
                page = int(next_page)
            elif len(batch) == 100:
                page += 1
            else:
                return jobs

    def play_job(self, project_id: int, job_id: int) -> dict:
        response = self.client.post(f"/projects/{project_id}/jobs/{job_id}/play")
        response.raise_for_status()
        job = response.json()
        return {key: job.get(key) for key in ("id", "name", "status", "ref", "web_url")}
