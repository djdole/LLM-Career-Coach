# Setting up the resume-generation workflow

This document walks through the one-time GitHub configuration needed for
`.github/workflows/generate-resumes.yml` to run successfully. It assumes
the LiteLLM/Ollama/Open WebUI stack from your `docker-compose.yml` is
already up and running somewhere.

## What this workflow does

On every push that changes `data/resume_data.json`, it calls your
self-hosted LiteLLM proxy to regenerate a baseline (no-specific-job)
resume and cover letter in pdf/docx/txt/md/json, then opens a pull
request with the results. It never pushes straight to `main`, and it
never calls a paid API.

## Step 1: Decide how the workflow will reach LiteLLM

This is the one decision that affects everything else, so make it first.

GitHub's default hosted runners (`ubuntu-latest`) run on the public
internet. They cannot reach a container on your home LAN unless you
expose it. You have two options:

**Option A: Expose LiteLLM publicly (tunnel/reverse proxy)**
Put a Cloudflare Tunnel, Tailscale Funnel, or authenticated reverse proxy
in front of the `litellm` container's port, and use that public address
as `LITELLM_BASE_URL` in Step 3. Keep `runs-on: ubuntu-latest` in the
workflow file as-is. Simpler to set up, but means a local LLM endpoint is
reachable from the internet, so make sure whatever you put in front of
it actually enforces auth (don't rely on `LITELLM_MASTER_KEY` alone as
your only line of defense against a scanner finding the port).

**Option B: Self-hosted GitHub Actions runner (recommended for a home LAN)**
Install a GitHub Actions runner on a machine on the same network as your
Docker stack, so nothing needs to be exposed to the internet at all.

1. In the repo: **Settings -> Actions -> Runners -> New self-hosted runner**.
2. Pick your OS and follow GitHub's generated `config.sh`/`config.cmd`
   commands on the machine that can reach the `litellm` container
   (e.g. the same host running `docker-compose.yml`, or another machine
   on the same LAN/VPN).
3. Run the runner as a service so it survives reboots (the setup script
   offers this, or use `./svc.sh install && ./svc.sh start` on Linux).
4. In `.github/workflows/generate-resumes.yml`, change:
   ```yaml
   runs-on: ubuntu-latest
   ```
   to:
   ```yaml
   runs-on: self-hosted
   ```
5. `LITELLM_BASE_URL` (Step 3) can then just be a plain LAN address, e.g.
   `http://192.168.1.50:4000` or `http://litellm:4000` if the runner
   itself is on the Docker network.

## Step 2: Add repo secrets

**Settings -> Secrets and variables -> Actions -> Secrets -> New repository secret**

| Secret name | Value |
|---|---|
| `LITELLM_BASE_URL` | The address from Step 1 (tunnel URL or LAN address), pointing at `${LITELLM_PORT}` -- **not** Open WebUI's `${UI_PORT}` |
| `LITELLM_API_KEY` | The same value as `LITELLM_MASTER_KEY` in your Docker stack's `.env` |

## Step 3: Add a repo variable

**Settings -> Secrets and variables -> Actions -> Variables -> New repository variable**

| Variable name | Value |
|---|---|
| `LITELLM_MODEL` | `ollama/${MODEL_NAME}`, using the actual value of `MODEL_NAME` from your stack's `.env` (e.g. `ollama/llama3.1:70b`) |

This isn't a secret, so it's a Variable rather than a Secret -- makes it
easier to see and change without digging through secret values.

> **Keep this in sync manually.** If you ever change `MODEL_NAME` in the
> Docker stack's `.env`, you need to update `LITELLM_MODEL` here too --
> they live in two different places and nothing keeps them in sync
> automatically. A mismatch here is the most common cause of a
> "model not found" failure (see Troubleshooting below).

## Step 4: Place the knowledge base file

The workflow expects the knowledge base at `data/resume_data.json` in
this repo. Commit it there (this is the file we've been editing
throughout this conversation).

## Step 5: Test it manually before relying on the automatic trigger

1. Go to the **Actions** tab -> **Generate resumes and cover letters** ->
   **Run workflow** (this uses the `workflow_dispatch` trigger, so you
   don't need to touch `data/resume_data.json` yet).
2. Watch the run. If it fails, check Troubleshooting below -- the script
   prints a specific reason rather than a bare stack trace.
3. If it succeeds, a pull request titled *"Auto: regenerate
   resumes/cover letters from resume_data.json"* will appear. Read the
   diff in `generated/` before merging -- local-model output can drift
   more than a hosted model's, so this first run is worth a close look.

Once a manual run succeeds, future pushes that touch
`data/resume_data.json` will trigger this automatically.

## Troubleshooting

| Symptom in the Actions log | Likely cause | Fix |
|---|---|---|
| `LITELLM_BASE_URL and/or LITELLM_API_KEY are not set` | Secrets missing or misnamed | Re-check Step 2 spelling exactly |
| `Could not reach LiteLLM at ...` | Runner can't reach the instance | Revisit Step 1 -- tunnel not up, self-hosted runner not on the right network, or firewall blocking the port |
| `LiteLLM returned an error (HTTP 401...)` | Wrong API key | `LITELLM_API_KEY` must match `LITELLM_MASTER_KEY` exactly |
| `LiteLLM returned an error (HTTP 400...)` mentioning the model | Model name mismatch | `LITELLM_MODEL` must match what LiteLLM was started with (`ollama/${MODEL_NAME}`) |
| `Model did not return valid JSON` | The local model didn't follow the output-format instructions | Try a larger/more capable model in `MODEL_NAME`/`LITELLM_MODEL` -- smaller local models are less reliable at strict JSON output than a hosted model would be |
| Workflow times out after 15 minutes | Instance hung, overloaded, or unreachable but not erroring cleanly | Check the Docker stack's own logs (`docker compose logs ollama litellm`) |