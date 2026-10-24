---
name: deploy-myproj
description: Create or reuse a release tag in anish5416/myproj, and run a requested GitLab job. Handles deploy proj, deploy myproj, and explicit tag/job requests for myproj; excludes myproj2.
---

## Find or create the requested tag

The project is exactly `anish5416/myproj`. Never substitute another project or invent a project ID.

Call prepare_release(project_path="anish5416/myproj", prefix="v", ref="main"). Omit tag_name for an automatic next-number release; if the user names a tag, pass that exact tag_name even if its format differs. Honor an explicitly requested branch/ref. This tool resolves the project ID and creates or reuses the tag; do not ask for a project ID or repository URL already specified here.

Use only the project_id, name, and target returned by prepare_release for subsequent steps. Report created=true as created and created=false as already existing. Never move an existing tag. If an earlier call used an incorrect ID, recover once through prepare_release using this exact path. Stop on failure of prepare_release and report the real error; never fabricate success.

## Run the requested job

Only run jobs when the user asks. Use their exact job name (for example `build_app`); if they only say "build job", try `build`.

1. Call list_pipelines(project_id, ref=confirmed_tag). Reuse the newest pipeline whose ref AND SHA match the confirmed tag. If absent, check again up to three times to allow tag CI to appear, then trigger_pipeline once on the confirmed tag if still absent. If the result is uncertain, recheck pipelines before any retry; never knowingly start a duplicate.
2. Call list_pipeline_jobs with the real pipeline ID. Find the exact requested job name. If absent, show actual candidates with similar names or build stage (for example build_app, build_image, or app_build) and their statuses. Ask "<requested> is absent; run <candidate> instead?" with concrete names. If no plausible match exists, show available names and ask which to run. Do not play an alternative job before approval.
3. After approval, re-read the SAME pipeline's jobs and run only the approved job. Continue the pending operation; do not create another tag or pipeline.
4. For status manual, call play_job once with the returned job ID. For created, pending, preparing, waiting_for_resource, or running, monitor the existing job. For success, report already succeeded. For failed/canceled/skipped, report status and stop rather than silently retrying; fetch get_job_log for failure.
5. Check list_pipeline_jobs at most ten times for that job. Claim success only on actual status success. If still running or pending, report the observed status and link. Starting a job is not completing it.

Requests to create the tag and run the named job authorize those operations. A pipeline may run other automatic jobs according to GitLab CI rules. Report verified tag/job outcomes, not an application deployment unless verified. Never invent tool results, IDs, or tags.
