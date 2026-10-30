---
orphan: true
---

# Phase 2 plan: Pi as an acting agent

Implementation plan for [roadmap](../roadmap.md) items 1, 2, 3, and 4, plus the pytest gate those code changes need. This page is a plan. It does not implement the acting agent.

Checked against `danielsimonjr/hermit` `main` at `53fecb12f40e6282856e08d8e6f0e54bc4004a7e` (the roadmap merge) and against `danielsimonjr/pi` `e4422efb6c67a3efe24cc368e956d90f77fd394c` (`packages/coding-agent/docs/` and the provider sources named below). Re-read the Pi fork before coding. The catalog and CLI move. This repository stays `danielsimonjr/hermit`. Nothing here is a change to `Infini-AI-Lab/hermit`.

## Pull requests

Five pull requests, merged in this order, each onto `main`. Do not open them in parallel. Do not stack them: this forge is GitHub, and a pull request whose base is the previous head would show every unmerged parent until it is retargeted. Each item below is independently reviewable once the previous item is on `main`.

| Order | Pull request | Depends on | Why it waits |
|---|---|---|---|
| 0 | Pytest CI | nothing | Items 1–4 change Python. Docs CI does not run it. |
| 1 | Run Pi from the CLI acting agent | 0 on `main` | The new check has to be on `main` so this pull request's Pytest job is the gate. |
| 2 | Read Pi's JSONL into `RunOutput` | 1 | Replaces the item 1 fixture and adds the `pi` branches in `parse_log` and `last_message`. |
| 3 | Bind a backend into a private Pi agent directory | 2 | Code depends on item 1's `_run`. It is sequenced after item 2 because both edit `tests/test_agents.py`. |
| 4 | Sandbox the Pi binary and its login | 3 | Needs `CLI_AGENTS["pi"]` and the private agent directory from item 3. |

Item 3 does not need item 2's parser. The merge order is still 2 then 3, so the two test edits do not collide.

Item 5 in the roadmap (documentation of the acting agent) is not one of these pull requests. The configuration pages still describe `react`, `codex`, and `claude-code`. Leave them until items 1–4 are on `main`. Writing them earlier would document an agent the code does not run.

Suggested branch names, each cut from `main` after the previous merge: `cursor/pytest-ci`, `cursor/pi-acting-agent`, `cursor/pi-jsonl-usage`, `cursor/pi-model-binding`, `cursor/pi-sandbox-login`.

## What the code does today

These are the facts the later sections edit. Line numbers are `53fecb12`.

| Claim | Where it is true |
|---|---|
| `BACKENDS = ("codex", "claude")`. `_run` maps `claude-code` to `claude` and raises otherwise. | `hermit/agents/cli.py` `BACKENDS`, `_run` |
| `deploy` imports `hermit.hosts.codex.prepare` or `hermit.hosts.claude_code.prepare`. The `else` is Claude Code. | `deploy` |
| `command` returns the Codex argv or, in the `else`, the Claude Code argv. | `command` |
| `last_message` reads Codex's `-o` file, and every other backend as Claude Code `type: result`. | `last_message` |
| `builtin` returns `CliAgent` for `cli`, `codex`, `claude-code`, and `claude`. `BUILTIN_NAMES` is `("react", "codex", "claude-code", "cli")` and has no other readers. | `hermit/agents/base.py` `builtin`, `BUILTIN_NAMES` |
| The acting-agent table lists `codex` and `claude-code`. | `hermit/agents/__init__.py` |
| `CLI_AGENTS` is `{codex, claude-code, claude, cli: None}`. `NEEDS` maps `codex` to `responses` and `claude` to `messages`. There is no `pi` key. | `hermit/backends.py` |
| `bind_agent_params` accepts kind `codex` or `claude` and raises `ValueError` otherwise (`kind must be codex or claude, not ...`). | `bind_agent_params` |
| `normalize_config` and `bindings_of` map `agent.name: cli` only through `{codex, claude, claude-code}`. | both functions |
| `problems_of` explains a missing `chat`, `responses`, or `messages` dialect. The hint table has only those three keys. | `problems_of` |
| `CLI_HOMES` is `codex` → (`.codex`, `CODEX_HOME`, `auth.json`) and `claude` → (`.claude`, `CLAUDE_CONFIG_DIR`, `.credentials.json`). | `hermit/isolate.py` |
| `_cli_kind` returns a kind only when it is in `CLI_HOMES`. For `agent.name: cli` the fallback is `{"claude-code": "claude"}.get(backend, backend)`. | `SandboxedAgent._cli_kind` |
| The login copy is `agent_home.mkdir()` with no `parents=True`, mode `0o600`, and `unlink(missing_ok=True)` in `finally`. | `SandboxedAgent.__call__` |
| `program_paths` follows the symlink chain, the package above `bin/`, and the shebang interpreter. If that package root is the home or a parent of the home, it binds the executable file only. | `hermit/sandbox.py` `program_paths` |
| `ALWAYS` passes `CODEX_HOME` and `CLAUDE_CONFIG_DIR` when `sandbox.env` is a list. `PI_CODING_AGENT_DIR` is absent. `Sandbox.wrap` keeps `ALWAYS` even when `env_allow` is set. | `ALWAYS`, `Sandbox.wrap` |
| `parse_log` has a Codex branch. Every other backend is Claude Code (`session_id`, `type: result`, `total_cost_usd`). Non-JSON lines are skipped. | `hermit/evolver/agent.py` `parse_log` |
| `price_usage` clears `cost_usd` when `binding.litellm` does not start with `anthropic/`, then fills it from `params.price`. `_run` already calls it. | `price_usage`, `hermit/agents/cli.py` `_run` |
| `Usage` has `input_tokens`, `cached_input_tokens`, `output_tokens`, `calls`, `cost_usd`. No cache-write field. | `hermit/evolver/base.py` `Usage` |
| `AgentEvolver._step` launches only `codex` and `claude`. | `AgentEvolver._step` |
| `prepare` writes `AGENTS.md` and `.pi/mcp.json`, and refuses roles before `output.mkdir`. | `hermit/hosts/pi.py` `prepare` |
| `hermit deploy --host` choices are `codex`, `claude-code`, `pi`. `convert --target` includes `hermes`. `EMITTERS` includes `hermes`. `BACKENDS` does not. | `hermit/cli.py`, `hermit/plugins/__init__.py` |
| `docs/_examples/file_adapter` exports a role. `exports.yaml` has `agents: agents` and `agents/reviewer.md` exists. | that tree |
| The only pull-request workflow is Docs CI. | `.github/workflows/docs-ci.yml` |

`tests/test_deploy.py::subagent_adapter` is a helper, not a test. `tests/test_deploy.py::test_pi` and `tests/test_convert.py::test_pi_package` already pass and stay as they are.

## Corrections to the roadmap

Use this page where it disagrees with `docs/roadmap.md`.

1. Docs CI is the pull-request gate. The workflow name is `Docs CI` (`.github/workflows/docs-ci.yml`, commit `3e4ae8f`). It checks out the sources, installs `docs/requirements.txt`, and runs `bash docs/build-pages.sh` and `python docs/check-pages.py`. `permissions` is `contents: read`. `.github/workflows/pages.yml` is `Deploy project site and docs`. It runs on push to `main` and `workflow_dispatch`, not on pull requests. The roadmap's item 5 sentence that `pages.yml` is the only workflow, and that Actions are not enabled, is stale.

2. A pytest job is required. Docs CI stays green if `tests/` fails. Items 1–4 do not change pages, so without step 0 a code pull request has no failing check when the new tests fail. Step 0 is its own pull request.

3. `docs/_examples/file_adapter` cannot be the Pi happy path. `prepare` raises `ValueError` naming `reviewer` before it writes `AGENTS.md` (`hermit/hosts/pi.py`). The marker `hermit:file-example:start` still comes from that adapter's id. The happy-path test copies the example and drops the role, using the same edits as `tests/test_convert.py::variant(..., roles=False)`. The Lean template is already role-free (`tests/test_deploy.py::test_pi`) but its marker is `hermit:lean-collab:start`, so it does not meet the file-example check.

4. There is no `ValueError` whose text contains `BACKENDS`. `_run` raises `agent.params.backend must be one of ('codex', 'claude')`. Match `must be one of`.

5. A role failure through `cli.run` still leaves an empty workspace directory. `_run` calls `workspace.mkdir` before `deploy`. `prepare` itself raises before `output.mkdir`, which is why `test_pi_refuses_roles` sees no directory. The CLI test asserts no `AGENTS.md` and no `.pi/`, not that the workspace path is absent.

6. Do not add `pi` to `NEEDS`. That table is one dialect per consumer. Pi's dialect depends on `backend.apis`. `bindings_of` would raise `KeyError` on `NEEDS["pi"]`.

7. `vllm` has `key_required: false` (`hermit/backends.yaml`). With `VLLM_API_KEY` unset, `Binding.key_env_if_set` returns `None`, and the Claude Code path stores `PLACEHOLDER_KEY` (`"local"`), not `$VLLM_API_KEY`. `$FIREWORKS_API_KEY` is the fireworks case (`key_required` stays true). The roadmap's single "`$VARIABLE` for both" assertion does not match `key_env_if_set`.

8. Item 1 does not parse usage. The current non-`codex` `last_message` only returns Claude Code `result` text. Item 1's fake script prints one Claude-shaped object so the run returns an answer without a Pi parser. Item 2 replaces that object. Item 1 must not assert tokens or cost: `parse_log`'s Claude branch would count that object as one turn.

9. Item 2 does not add a `price_usage` call. `hermit/agents/cli.py` `_run` already calls it after `parse_log`.

10. A fake `pi` placed under `HOME/bin` does not make a sibling marker readable. `program_paths` refuses to bind the home. The sandbox test puts the binary outside `HOME`.

Pi fork facts used below, from that pin:

- `pi --mode json` runs the prompt, writes JSONL to stdout, and exits. `--print` writes the final text to stdout instead. Piped stdin is prepended to the first prompt (`packages/coding-agent/docs/cli.md`).
- `--approve` / `-a` trusts project `.pi/` resources for that process. It does not write `~/.pi/agent/trust.json`. Print and JSON modes cannot show the trust prompt. With no `--approve` and no saved decision, `defaultProjectTrust` of `"ask"` skips `.pi/mcp.json` and `.pi/skills`. `AGENTS.md` still loads (`packages/coding-agent/docs/security.md`).
- `--model` accepts `provider/id` by splitting on the first slash when that prefix is a known provider. `--provider` requires `--model`. A model id that itself contains slashes is passed as `--provider <name> --model <id>` (`packages/coding-agent/src/core/model-resolver.ts`).
- `--api-key` puts the secret on the command line. Do not pass it.
- A compatible endpoint is `<agent-dir>/models.json` with `providers.<name>.baseUrl`, `api`, `apiKey`, and `models[].id`. `apiKey` accepts `$NAME`. Known `api` strings include `openai-completions`, `openai-responses`, and `anthropic-messages` (`packages/ai/src/types.ts`). A `providers.<name>` entry overlays that provider.
- Built-in provider ids that collide with `hermit/backends.yaml` names are `anthropic`, `openai`, `deepseek`, and `fireworks`. `vllm`, `sglang`, and `ollama` are not in `builtinProviders()`. `llama.cpp` is `LLAMA_PROVIDER_ID` in the coding-agent llama extension.
- The agent directory defaults to `~/.pi/agent` and moves with `PI_CODING_AGENT_DIR`. Credentials are `<agent-dir>/auth.json`.
- JSONL: a `session` header, then events. Assistant `message_end.message.usage` has `input`, `output`, `cacheRead`, `cacheWrite`, `totalTokens`, and `cost.total`. `reasoning` is already inside `output`. `cacheWrite1h` is a subset of `cacheWrite`. `message_update.usage` is cumulative. Tool-result `usage` is nested work, not the main model call. Text is `content[]` entries with `type: "text"` and `text`.

## Step 0 — Pytest CI

**Scope.** A pull request that changes `hermit/` or `tests/` fails when `python -m pytest tests` fails. The workflow grants `contents: read` and reads no secret. It does not install method groups, does not set API keys, and does not change `docs-ci.yml` or `pages.yml`.

**Files.**

- Add `.github/workflows/pytest.yml`. No other file.

**Workflow.** Match the shape of `.github/workflows/docs-ci.yml` (`actions/checkout@v7`, `actions/setup-python@v7`, Python 3.12, `permissions: contents: read`, the same concurrency expression). Trigger on `pull_request` and on `push` to `main`, with no path filter, so a Python-only pull request is gated.

Job `pytest` on `ubuntu-latest`:

1. Check out the sources.
2. Set up Python 3.12. Cache pip with `cache-dependency-path: pyproject.toml`.
3. `sudo apt-get update && sudo apt-get install -y bubblewrap`.
4. `bwrap --unshare-user --unshare-net --ro-bind / / true`. This step fails the job if user namespaces do not work. `@needs_bwrap` would otherwise skip, and item 4's sandbox test would not be a gate.
5. `python -m pip install -e '.[test]'` (the command in `CONTRIBUTING.md`). Do not pass `--group all`.
6. `python -m pytest tests`.

Do not reference `secrets`. Do not export `FIREWORKS_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or any other provider key. Tests that need a key set it themselves with `monkeypatch`.

`tests/test_harness2_codex.py`, `tests/test_harness2_upstream.py`, and the GEPA and SkillOpt cases in `tests/test_optimizer_evolvers.py` use `pytest.importorskip` and stay skipped. They are not the gate for items 1–4. `tests/test_sandbox.py::test_file_audit_sees_what_the_sandbox_opens` skips without `strace`. Do not install `strace` in this job.

**Tests.** None.

**Acceptance.**

- The workflow file is the only change.
- `permissions` is `contents: read`. The file does not contain `secrets`.
- On a pull request, the Pytest check runs `python -m pytest tests` and the bubblewrap probe. Docs CI still runs and stays green.
- A failing test in `tests/` fails this check.

**Verify locally.** Docs do not change.

```bash
python -m pip install -e '.[test]'
bwrap --unshare-user --unshare-net --ro-bind / / true
python -m pytest tests
```

The workflow YAML itself is reviewed by reading it. GitHub runs it on the pull request.

## 1. Run Pi from the CLI acting agent

**Scope.** `agent.name: pi`, and `agent.name: cli` with `params.backend: pi`, run one task in a fresh workspace. An adapter is deployed with the existing `hermit.hosts.pi.prepare`. The process is `pi --mode json --approve`, plus `--model` when `params.model` is set. A role export still fails with the `ValueError` `prepare` already raises. `~/.pi/agent` is not created or modified. Usage is not parsed. A model reference is not bound. `AgentEvolver._step` stays on Codex and Claude Code.

**Files and functions.**

- `hermit/agents/cli.py`
  - Module docstring: document `name: pi` beside `codex` and `claude-code`, including `--approve` and the role refusal. Do not describe `models.json` or `PI_CODING_AGENT_DIR` yet.
  - `BACKENDS`: `("codex", "claude", "pi")`.
  - `deploy`: `backend == "pi"` imports `prepare` from `hermit.hosts.pi`. Leave the `else` as Claude Code. Do not let `pi` fall through.
  - `command`: a `backend == "pi"` branch returns `["pi", "--mode", "json", "--approve", *(["--model", model] if model else []), *args, prompt]`. The prompt is the last, positional argument. Do not add `--print`, `--api-key`, or `--provider`. User `args` stay in front of the prompt, as they do for Codex.
  - Do not change `last_message`, `_run`'s `subprocess.run` call (`cwd` is the workspace, `stdin` is `DEVNULL`, stdout and stderr go to `agent-<backend>.jsonl`), or the `price_usage` call.
- `hermit/agents/base.py`
  - `builtin`: add `"pi"` to the CLI name tuple. Map `"pi"` to backend `"pi"` in the same dict as `codex` and `claude-code`, so `builtin("pi")` returns a `CliAgent` whose `params["backend"]` is `pi`. `builtin("cli")` still returns the class unchanged.
  - `BUILTIN_NAMES`: append `"pi"`.
  - The module docstring's built-in list: add `pi`.
- `hermit/agents/__init__.py`: add `pi` to the `agent.name` table, same row idea as `codex` and `claude-code`.

Do not change `hermit/hosts/pi.py`, `hermit/plugins/pi_package.py`, `hermit/evolver/agent.py`, `hermit/backends.py`, or `hermit/isolate.py`.

**Tests.** In `tests/test_agents.py`.

- `FAKE_PI`: a shell script named `pi` in the test's `bin` directory. It writes `"$*"` to `<workspace>/.args` and prints one line, `{"type":"result","result":"ANSWER 44"}`. That shape is what today's non-`codex` `last_message` already returns. It is not Pi's event stream. Item 2 replaces it.
- Extend `test_cli_agent_with_fake_cli` with `("pi", FAKE_PI, "ANSWER 44")`. The executable name is `pi` when `backend == "pi"`. Keep the Codex and Claude Code token assertions inside their own branches. The Pi branch asserts the bullets below and does not assert `tokens` or `cost_usd`.
- Extend `test_load_agent_builtin_class_function_and_alias`: `load_agent("pi", {"model": "m"}, tmp_path)` is a `CliAgent` with `params["backend"] == "pi"`. `load_agent("cli", {"backend": "pi"}, tmp_path)` is a `CliAgent` with `params["backend"] == "pi"`.
- New `test_pi_cli_refuses_roles`. Build the adapter with `subagent_adapter` from `tests/test_deploy.py`. Call `hermit.agents.cli.run` with `params={"backend": "pi", "prompt": "x"}`. `pytest.raises(ValueError, match="reviewer")`. The created workspace contains no `AGENTS.md` and no `.pi/`.
- New `test_cli_rejects_an_unknown_backend`. `run(..., params={"backend": "hermes", "prompt": "x"}, ...)` raises `ValueError` matching `must be one of`. The message contains `codex` and `pi`. No workspace directory is created.

The Pi case of `test_cli_agent_with_fake_cli` uses a role-free copy of `docs/_examples/file_adapter` (drop `exports.yaml`'s `agents` entry, the `agents/` learnable path, and the `agents/` directory, as `variant(..., roles=False)` does). Set `HOME` to a temporary directory for that parameter only. Assert `HOME/.pi` does not exist after the run.

`tests/test_deploy.py::test_pi`, `tests/test_deploy.py::test_pi_refuses_roles`, and `tests/test_convert.py::test_pi_package` stay as they are.

**Acceptance.**

- `load_agent("pi", ..., base)` and `load_agent("cli", {"backend": "pi"}, base)` both construct `CliAgent`.
- With the role-free file-example adapter and a fake `pi` on `PATH`, the run's `output` is `ANSWER 44`, `extra["backend"]` is `pi`, `extra["exit_code"]` is `0`, and `extra["timed_out"]` is false. `log` is the workspace directory. Its parent is `<base>/ws` when `workspaces` is `ws`, and its name matches `<task id>-` plus 8 hex characters (`uuid.uuid4().hex[:8]` in `_run`).
- The recorded argv contains `--mode`, `json`, `--approve`, the formatted prompt, and the model when one was set. It contains neither `--print` nor `--api-key` nor `--provider`.
- `AGENTS.md` in that workspace contains `hermit:file-example:start`. The log file is `agent-pi.jsonl`.
- A second call uses a different workspace directory.
- `HOME/.pi` is not created.
- An adapter that exports a role fails with the existing message from `hermit/hosts/pi.py` (`Pi has no subagents`, the role name `reviewer`).
- The Codex and Claude Code cases of `test_cli_agent_with_fake_cli` still pass, including their token and cost assertions.

**Verify locally.** Docs do not change.

```bash
python -m pip install -e '.[test]'
python -m pytest tests/test_agents.py tests/test_deploy.py::test_pi tests/test_deploy.py::test_pi_refuses_roles tests/test_convert.py::test_pi_package
python -m pytest tests
```

## 2. Read Pi's JSON event stream into `RunOutput`

**Scope.** `parse_log(..., "pi", model)` and `last_message("pi", ...)` fill the same `RunOutput` fields Codex and Claude Code already fill: `output`, `tokens`, `cost_usd`, and `api_speed["model_calls"]`. `RunOutput.log` stays the workspace directory. `extra` stays `backend`, `exit_code`, `timed_out`, and `workspace`.

**Files and functions.**

- `hermit/evolver/agent.py` `parse_log`. Add `elif backend == "pi":` before the Claude Code `else`. Do not change the Codex branch or the `else`.
  - Session id: the `session` header's `id` (`event["type"] == "session"`). Do not read `session_id`.
  - For each `message_end` whose `message.role` is `assistant`, add one call and that message's `usage` only.
  - Map usage the way the Claude branch combines cache reads: `input_tokens += input + cacheRead`, `cached_input_tokens += cacheRead`, `output_tokens += output`. `input` on the fork is uncached. `price_usage` then bills `(input_tokens - cached_input_tokens)` at the input price and `cached_input_tokens` at the cached price, which is each token once. The Codex fixture in `test_cli_agent_with_fake_cli` (`input_tokens: 1000`, `cached_input_tokens: 200`, cost on 800 uncached tokens) is the same rule.
  - Do not add `reasoning` to `output_tokens`. Do not store `cacheWrite` or `cacheWrite1h`. `Usage` has nowhere to put them.
  - When `usage.cost.total` is a number, add it to `usage.cost_usd` (start from 0 on the first such message). Each assistant message has its own total. Claude Code assigns once because it has one `result` event; Pi does not.
  - Ignore `message_update`. Ignore `usage` on any message whose role is not `assistant`, including a tool result (`role: "toolResult"`).
  - Non-JSON lines stay skipped. An empty file still returns `(None, [])`.
- `hermit/agents/cli.py` `last_message`. For `pi`, return the `text` fields of `type: "text"` blocks on the last assistant `message_end`, joined with no separator. A final assistant message with no text block returns `""`. Do not read thinking blocks. The JSONL file remains the trajectory inside the workspace; `RunOutput.log` is still the workspace.
- Do not add another `price_usage` call. `_run` already runs it. A `binding` whose `litellm` does not start with `anthropic/` clears the summed CLI cost and replaces it from `params.price`. Pi's summed `cost.total` is that CLI-reported cost.
- Replace `FAKE_PI` so the item 1 parametrize case now prints Pi's stream (below). `last_message` for `pi` must be in the same pull request, or that case stops returning `ANSWER 44`.

Do not change `AgentEvolver._step`, `price_usage`, `Usage`, or the Codex and Claude command builders.

**Tests.** In `tests/test_agents.py` unless noted.

- Update `FAKE_PI` to print, in order: a `session` header `{"type":"session","id":"ps1","cwd":"/tmp"}`; a `message_update` with `usage.input` of `99999`; an assistant `message_end` whose content has a text block `draft` and a thinking block, with `usage` `{input: 10, output: 4, cacheRead: 3, cacheWrite: 1, reasoning: 2, cost: {total: 0.01}}`; a tool-result record `{"type":"message_end","message":{"role":"toolResult","usage":{"input":100,"output":50,"cacheRead":0,"cost":{"total":9}}}}`; a second assistant `message_end` whose only text block is `ANSWER 44`, with `usage` `{input: 20, output: 5, cacheRead: 0, cacheWrite: 0, cost: {total: 0.02}}`.
- `test_cli_agent_with_fake_cli` Pi case: `output` is still `ANSWER 44`. Keep the Codex and Claude Code token assertions unchanged.
- New `test_pi_jsonl_fills_output_tokens_and_cost`. Same script, two runs.
  - With `price: {input: 1, cached_input: 0.5, output: 2}` and a non-Anthropic `binding` (`litellm` such as `hosted_vllm/q`): `output` is `ANSWER 44`; `tokens` is `42` (input `(10+3)+(20+0)`, output `4+5`); `api_speed["model_calls"]` is `2`; `cost_usd` is `((33-3)*1 + 3*0.5 + 9*2) / 1e6`, not `0.03`.
  - With no `binding` and no `price`: `cost_usd` is `0.03` (the sum of the two `cost.total` values) and `tokens` is `42`.
- New `test_parse_log_pi_ignores_snapshots_reasoning_and_tool_usage`. Call `parse_log` on a file with the records above. `calls` is 2. `output_tokens` is 9, not 11. The `99999` and the tool-result `100` are absent. `cacheWrite` is absent from the `Usage`. Session id is `ps1`.
- New `test_pi_timeout_sets_exit_code`. The fake `pi` sleeps. `timeout_s` is small (`0.2`). `extra["exit_code"]` is `-1` and `extra["timed_out"]` is true. This is the existing `subprocess.TimeoutExpired` path in `_run`.
- New `test_parse_log_pi_skips_a_truncated_line`. A file whose last line is a truncated `{` still returns the usage of the complete assistant `message_end` above it. An empty file returns no usage. `last_message("pi", empty, ...)` returns `""`.

**Acceptance.**

- Codex and Claude Code rows of `test_cli_agent_with_fake_cli` keep their token and cost assertions.
- Pi `message_update` lines do not add tokens. Tool-result `usage` does not add tokens. `reasoning` is not added on top of `output`.
- `RunOutput.output` is the last assistant text. `RunOutput.log` is the workspace. `extra` still carries `backend`, `exit_code`, `timed_out`, and `workspace`.
- A timeout sets `exit_code` to `-1` and `timed_out` to true, including when the log is empty or the last line is not JSON.
- With a non-Anthropic binding and a `price` mapping, the cost is `price_usage`'s figure. Without a binding and without `price`, the cost is the sum of assistant `cost.total` values.

**Verify locally.** Docs do not change.

```bash
python -m pip install -e '.[test]'
python -m pytest tests/test_agents.py tests/test_backends.py::test_claude_cost_counts_only_on_anthropic
python -m pytest tests
```

## 3. Bind a hermit model backend into a private Pi agent directory

**Scope.** `agent.params.model` as a `<backend>/<model id>` reference configures the `pi` process to call that backend. A string that is not a reference stays a Pi model id and is passed as `--model` only, which is the Codex and Claude Code rule for a plain id. `bind_agent_params` only edits the params dict. `_run` writes `models.json`. The literal key never goes into params, the JSONL, or `models.json`.

The acting agent sets `PI_CODING_AGENT_DIR` to a directory it created for the call. Item 4 copies `auth.json` into that directory. This item writes `models.json` beside it and does not create or overwrite `auth.json`.

`hermit/evolver/agent.py` is unchanged in this pull request. `evolver.name: codex` and `evolver.name: claude` keep their commands.

**Dialect.** One helper, `pi_api(apis) -> tuple[str, str] | None`, in `hermit/backends.py`. Both `bind_agent_params` and `bindings_of` call it. Do not duplicate the table.

| `apis` contains | `models.json` `api` | dialect for `bindings_of` / `problems_of` |
|---|---|---|
| `chat` | `openai-completions` | `chat` |
| `responses`, and not `chat` | `openai-responses` | `responses` |
| `messages`, and not `chat` or `responses` | `anthropic-messages` | `messages` |
| none of those | no provider document and no `models.json` | `chat`, so `problems_of` fails with the existing chat hint |

`vllm` and `fireworks` in `hermit/backends.yaml` both list `chat`, so both use `openai-completions` even though they also list `responses` and `messages`. `anthropic` lists only `messages`, so it uses `anthropic-messages`. An empty `apis` list is legal (`Backend.from_dict` only rejects unknown names). Passing a new dialect string into `problems_of` would raise `KeyError` on the hint table. Report `chat` instead, and do not edit that hint in this pull request.

**Provider key.** A constant `PI_BUILTIN_PROVIDERS` in `hermit/agents/cli.py`, the built-in ids from the Pi pin: every `id` passed to `builtinProviders()` in `packages/ai/src/providers/all.ts`, plus `llama.cpp`. Re-copy the set from the fork at coding time. If `binding.backend.name` is in the set, the `models.json` key is `hermit-` plus that name (`hermit-fireworks`, `hermit-anthropic`). Otherwise the key is the backend name (`vllm`). The unit test asserts the key `_run` wrote.

**`apiKey`.** Same expression as `Binding.claude_env` without `expand`: `Binding.key_env_if_set()` then `f"${key_env}"`, else `PLACEHOLDER_KEY` (`"local"`). Fireworks with or without `FIREWORKS_API_KEY` set yields `$FIREWORKS_API_KEY` because `key_required` is true. vLLM with `VLLM_API_KEY` unset yields `local`. vLLM with the variable set yields `$VLLM_API_KEY`.

**Files and functions.**

- `hermit/backends.py`
  - Add `pi_api`.
  - `CLI_AGENTS`: add `"pi": "pi"`. Leave `"cli": None`.
  - `bind_agent_params`: kind `pi` sets `model` to `binding.model`, copies `price` and `binding` as the other kinds do, and, when `pi_api` returns a pair, sets `pi_provider` to `{name, baseUrl, api, apiKey, models: [{id: model}]}`. Do not put the provider settings in `args` or `env`. Do not write a file. An unknown kind still raises `ValueError`; change the message to name `codex`, `claude`, and `pi`.
  - `normalize_config`: the `cli` backend map gains `"pi": "pi"`. Call `bind_agent_params` when `kind in ("codex", "claude", "pi")`. Update the docstring that currently says only Codex and Claude Code get provider settings.
  - `bindings_of`: for kind `pi` and a `binding` dict, append `(f"agent ({name})", Binding.from_spec(...), dialect)`. `name` is `agent["name"]`, so the label is `agent (pi)` or `agent (cli)`. The dialect is `pi_api(binding.backend.apis)` or `chat` when `pi_api` returns `None`. Do not index `NEEDS["pi"]`.
  - Do not change `Binding.codex_args`, `Binding.claude_env`, or `NEEDS`.
  - `_model_access` in `hermit/isolate.py` is unchanged. It already allows `binding.base_url` and appends `binding.api_key_env` for every label that starts with `agent`. Once `bindings_of` yields the Pi agent, the key name is on the sandbox allow-list.
- `hermit/agents/cli.py`
  - `command`, `pi` branch: when `params["pi_provider"]` is set, insert `--provider`, the provider name, `--model`, and `params["model"]` as four arguments. `params["model"]` is the id only, including slashes (`accounts/fireworks/models/glm-5p3-flash`, `Qwen/Qwen3-30B-A3B-Instruct-2507-FP8`). When `pi_provider` is absent, keep item 1's optional `--model`. Never add `--api-key`.
  - `_run`, after `deploy` and before `subprocess.run`: if `PI_CODING_AGENT_DIR` is unset, create `<workspace>/.pi-agent`, put that path in the child environment, and do not create `HOME/.pi`. When the variable is already set, use that directory and do not create a second one (item 4 sets it). If `pi_provider` is present, write `<dir>/models.json` as `{"providers": {name: {baseUrl, api, apiKey, models}}}`. If `auth.json` already exists there, leave it. The child environment is the existing `{**os.environ, **expanded params.env}` plus `PI_CODING_AGENT_DIR`.
  - Module docstring: state that a reference becomes a per-call `models.json`, and that `~/.pi/agent` is not that directory.
- `hermit/agents/base.py` and `hermit/agents/__init__.py`: no further behavior change. Docstrings may mention `params.model` as a reference only if item 1's wording would otherwise say a plain id is the only form.

**Tests.**

- `tests/test_backends.py::test_bind_pi_provider_document`
  - `bind_agent_params(..., "pi", ...)` on `vllm/Qwen/Qwen3-30B-A3B-Instruct-2507-FP8` with `VLLM_API_KEY` unset: `model` is `Qwen/Qwen3-30B-A3B-Instruct-2507-FP8`, `baseUrl` is `http://127.0.0.1:8000/v1`, `api` is `openai-completions`, `apiKey` is `local`, provider name is `vllm`, and the params JSON contains no secret.
  - The same helper on `fireworks/accounts/fireworks/models/glm-5p3-flash` with `FIREWORKS_API_KEY` set to a sentinel: `baseUrl` is `https://api.fireworks.ai/inference/v1`, `api` is `openai-completions`, `apiKey` is `$FIREWORKS_API_KEY`, provider name is `hermit-fireworks`, `price["output"]` is `0.5`, and the sentinel is absent from the params.
  - `anthropic/claude-x`: `api` is `anthropic-messages`, provider name is `hermit-anthropic`, `apiKey` is `$ANTHROPIC_API_KEY`.
  - A custom backend whose `apis` are `["responses"]` only: `api` is `openai-responses` and the dialect helper returns `responses`.
  - A plain model id `sonnet` is returned unchanged (`bind_agent_params` returns the same dict, as it does for Codex).
  - Kind `"hermes"` raises `ValueError`.
- `tests/test_backends.py::test_normalize_config_binds_a_pi_agent`. `agent.name: pi` and a top-level `model: vllm/q` fill `agent.params.binding` and `agent.params.pi_provider`. `bindings_of` yields `("agent (pi)", binding, "chat")`. `agent.name: cli` with `params.backend: pi` does the same and the label is `agent (cli)`.
- `tests/test_backends.py::test_pi_problems_of_rejects_a_backend_with_no_dialect`. A backend with `apis: []` and `key_required: false` produces no `pi_provider`. `bindings_of` reports dialect `chat`. `problems_of` is non-empty. `Trainer._prepare` raises `SystemExit` matching `train refuses to start`, using the same shape as `test_check_reports_models_and_train_refuses_a_missing_dialect` (`_tiny_run`, top-level model still a vLLM reference so the evolver's `responses` check stays quiet, `agent.params.model` pointing at the empty backend). `run_check(..., probe=False)` accepts `agent.name: pi` bound to `vllm/q` and to a fireworks reference when the fireworks key is set, and accepts `anthropic/claude-x` on the dialect check (the key must be set or `key_required` relaxed in the test registry; do not call the network).
- `tests/test_agents.py::test_pi_models_json_uses_a_private_agent_dir`. Fake `pi` records `"$*"` and `PI_CODING_AGENT_DIR`. `HOME` is a temporary directory. Params carry the fireworks `pi_provider` from `bind_agent_params`, not a hand-built dict with a literal key. After the run, `models.json` is `<workspace>/.pi-agent/models.json`, the child environment's `PI_CODING_AGENT_DIR` is that directory, `HOME/.pi` does not exist, argv contains `--provider`, `hermit-fireworks`, `--model`, and `accounts/fireworks/models/glm-5p3-flash` as separate arguments, and argv does not contain `--api-key` or the sentinel. A second call uses a different `.pi-agent` directory. The first `models.json` is not the file the second call wrote.
- `tests/test_isolate.py` (or `tests/test_backends.py`): call `_model_access` on the normalized Pi config and assert the fireworks base URL and `FIREWORKS_API_KEY` are returned. This is the sandbox allow-list. `_model_access` itself is not edited.

`test_bind_agent_params`, `test_codex_args_and_claude_env`, and `test_normalize_config_resolves_llm_agent_and_default` keep their current `args` and `env` assertions.

**Acceptance.**

- `hermit train` preflight (`Trainer._prepare` / `run_check(..., probe=False)`) accepts a Pi agent bound to `vllm` and `fireworks` (`openai-completions`, dialect `chat`) and to `anthropic` (`anthropic-messages`, dialect `messages`). A backend that serves none of `chat`, `responses`, or `messages` fails `problems_of`.
- The key variable name is in the child environment when it was set on the parent (the child inherits `os.environ`) and in `_model_access`'s key list. The key value appears in neither `models.json` nor `agent.params`.
- A second task gets a new agent directory. The first directory's `models.json` is not reused.
- Codex and Claude Code bindings keep their `args` and `env` assertions.
- `~/.pi/agent` is not created.

**Verify locally.** Docs do not change.

```bash
python -m pip install -e '.[test]'
python -m pytest tests/test_backends.py tests/test_agents.py tests/test_isolate.py::test_the_agents_model_endpoint_is_allowed_or_forwarded
python -m pytest tests
```

The new `_model_access` assertion lives in whichever file the pull request adds it to; include that node id in the focused command.

## 4. Sandbox the Pi binary and its login

**Scope.** A sandboxed rollout, eval, or check (`SandboxedAgent`) that runs `agent.name: pi` can execute `pi`, can read the copied login, and cannot keep that login after the call. The binary mount uses the existing `program_paths`. The fork stores saved credentials in `<agent-dir>/auth.json`. The user file is `~/.pi/agent/auth.json`.

**Files and functions.**

- `hermit/isolate.py`
  - `CLI_HOMES`: add `"pi": (".pi/agent", "PI_CODING_AGENT_DIR", "auth.json")`. Do not change the `codex` or `claude` tuples.
  - `SandboxedAgent._cli_kind`: no new branch. After item 3, `CLI_AGENTS["pi"]` is `"pi"`. For `agent.name: cli` and `params.backend: pi`, the existing fallback uses the backend string (`{"claude-code": "claude"}.get(backend, backend)`), and the `CLI_HOMES` membership test then returns `pi`.
  - `SandboxedAgent.__call__` copy block: `agent_home.mkdir(parents=True)` so `home / ".pi/agent"` is created. `parents=True` is required; `.codex` and `.claude` are a single path component and do not need it. Copy `Path.home() / ".pi/agent/auth.json"` when it is a file, `chmod` `0o600`, set `PI_CODING_AGENT_DIR` to that agent home, and append the variable to `keep`. A missing source does not fail the call. The `finally` unlink stays `missing_ok=True` and uses `CLI_HOMES[self.cli]`, which already addresses `home / ".pi/agent" / "auth.json"`.
  - `program_paths(self.cli)` is already added to the readable paths when `self.cli` is set (`SandboxedAgent.__init__`). With `_cli_kind` returning `pi`, that call is `program_paths("pi")`. Do not add a second mount.
- `hermit/sandbox.py` `ALWAYS`: add `"PI_CODING_AGENT_DIR"` next to `CODEX_HOME` and `CLAUDE_CONFIG_DIR`. `Sandbox.wrap` then keeps it when `env_allow` is a list.
- `hermit/agents/cli.py` `_run`
  - When `PI_CODING_AGENT_DIR` is already set, write `models.json` into that directory and do not create `<workspace>/.pi-agent`. Item 3 already says this. This pull request is what makes the sandbox set the variable first.
  - When the sandbox is off, keep item 3's `<workspace>/.pi-agent`. If `Path.home() / ".pi/agent/auth.json"` is a file, copy it into that directory with mode `0o600` before the process starts, and `unlink(missing_ok=True)` the copy in a `finally` so a timeout still removes it. Do not delete the user's file. Do not copy when the sandbox already set `PI_CODING_AGENT_DIR`: `isolate.py` owns that copy. The unsandboxed Codex path uses the real `~/.codex`. Pi does not use the real `~/.pi/agent`, because item 3 writes `models.json` and `hermit/hosts/pi.py` promises not to change that directory.

Do not change `program_paths`. Do not change `CLI_HOMES["codex"]` or `CLI_HOMES["claude"]`.

**Tests.**

- `tests/test_isolate.py::test_pi_cli_kind`. Build a config with `make_task` from `tests/test_training.py`, `agent.name` `pi`, and `sandbox.enabled` false so no bubblewrap is required. Construct `SandboxedAgent` and assert `_cli_kind()` is `pi`. A second config with `agent.name` `cli` and `params.backend` `pi` also returns `pi`. `codex` and `claude-code` still return `codex` and `claude`.
- `tests/test_isolate.py::test_cli_homes_keeps_codex_and_claude_and_adds_pi`. `CLI_HOMES["codex"]` is `(".codex", "CODEX_HOME", "auth.json")`. `CLI_HOMES["claude"]` is `(".claude", "CLAUDE_CONFIG_DIR", ".credentials.json")`. `CLI_HOMES["pi"]` is `(".pi/agent", "PI_CODING_AGENT_DIR", "auth.json")`.
- `tests/test_sandbox.py::test_pi_coding_agent_dir_survives_an_env_allow_list`. `Sandbox(enabled=False, env_allow=["LANG"]).wrap(["true"], env={"LANG": "C", "PI_CODING_AGENT_DIR": "/tmp/agent", "NOT_A_SECRET": "x"})` keeps `PI_CODING_AGENT_DIR` and drops `NOT_A_SECRET`. `enabled=False` applies the allow-list without bubblewrap (`Sandbox.wrap` filters `env` before the bwrap check).
- `tests/test_isolate.py::test_sandboxed_pi_mounts_the_binary_and_drops_the_login`, directly after `test_a_cli_deploy_renders_the_adapter_in_a_sandbox`, decorated with the file's `@needs_bwrap`. Place the fake `pi` at `<tmp>/opt/pi/bin/pi`, not under `HOME`. Put a marker file beside it. Set `HOME` to a different temporary directory and plant `HOME/.pi/agent/auth.json` with a known body. `program_paths("pi")` then binds the install prefix (the parent of `bin/`) and does not bind `HOME`, which is the rule in `program_paths` when the package root is not the home. The script prints the marker, prints whether `HOME/secret.txt` (a file next to the install tree, outside the prefix) was readable, prints `PI_CODING_AGENT_DIR`, and prints the contents of `auth.json` in that directory. Run it under `SandboxedAgent` with a role-free adapter and a `pi_provider` so item 3 writes `models.json`. Assert: `PI_CODING_AGENT_DIR` is inside the call work directory (`work/home/.pi/agent`); the `auth.json` the script read matches the fixture; after the call that copy is gone; the planted `HOME/.pi/agent/auth.json` is unchanged; `models.json` is in the same directory as the copy was; the marker was readable; the home sibling was not; `<workspace>/.pi-agent` was not created.
- `tests/test_agents.py::test_unsandboxed_pi_copies_auth_then_deletes_it`. No bubblewrap. This is the `_run` copy, which the sandbox test does not execute (`isolate.py` copies instead when `PI_CODING_AGENT_DIR` is set). Plant `HOME/.pi/agent/auth.json`. The fake `pi` prints the mode of `<PI_CODING_AGENT_DIR>/auth.json`. After the call the copy is gone, the planted file is unchanged, the recorded mode is `0o600`, and `models.json` is in `<workspace>/.pi-agent`. A second run with no planted file succeeds and writes `models.json` only.

A test that sets `profiles.rollout.enabled: false` is not required. That switch skips `SandboxedAgent`. The unsandboxed copy is the direct `cli.run` test above.

**Acceptance.**

- `agent.name: codex` and `agent.name: claude-code` still copy `auth.json` and `.credentials.json`. Their `CLI_HOMES` entries are unchanged.
- A missing `~/.pi/agent/auth.json` does not fail the call. Pi then has `models.json` and the `$VARIABLE` key only.
- The login file mode is `0o600`. The unlink uses `missing_ok=True`.
- `PI_CODING_AGENT_DIR` survives a `sandbox.profiles.rollout.env` allow-list because it is in `ALWAYS`.
- The fake binary's directory is readable inside the sandbox. A file outside that install prefix, in the user's home, is not.
- `~/.pi/agent` is not modified. The sandbox does not leave a second agent directory under the workspace.

**Verify locally.** Docs do not change. The bubblewrap test runs only when the probe succeeds. The others run either way.

```bash
python -m pip install -e '.[test]'
bwrap --unshare-user --unshare-net --ro-bind / / true
python -m pytest tests/test_isolate.py::test_pi_cli_kind tests/test_isolate.py::test_cli_homes_keeps_codex_and_claude_and_adds_pi tests/test_isolate.py::test_sandboxed_pi_mounts_the_binary_and_drops_the_login tests/test_sandbox.py::test_pi_coding_agent_dir_survives_an_env_allow_list tests/test_agents.py::test_unsandboxed_pi_copies_auth_then_deletes_it tests/test_isolate.py::test_a_cli_deploy_renders_the_adapter_in_a_sandbox
python -m pytest tests
```

## Out of scope

- Roadmap item 5. Do not edit `docs/framework/task.md`, `docs/framework/configuration.md`, `docs/tutorials/your-own-task.md`, `docs/guides/model-backends.md`, `docs/reference/config-fields.md`, or `docs/framework/commands.md` in these pull requests.
- Teaching `AgentEvolver._step` to launch Pi, register evolver tools, or resume a Pi session. `parse_log` grows a Pi branch in item 2 because the acting agent already shares that function. The learner command stays `codex` or `claude`.
- Changing `hermit/hosts/pi.py` or `hermit/plugins/pi_package.py`. Role refusal and the "do not edit `~/.pi/agent`" rule stay. The Pi docs at the pin still treat `.pi/mcp.json` and `.pi/skills` as trust-gated and `AGENTS.md` as loaded without trust, which is what `prepare` writes.
- A Hermes acting agent. Hermes stays a convert target (`EMITTERS`) and stays out of `BACKENDS`.
- A `cache_write_tokens` field on `Usage`.
- Editing `Infini-AI-Lab/hermit`.

## Verification for this plan

This pull request adds only this page. `docs/conf.py` builds every Markdown file under `docs/` with `-W`. The page is `orphan: true`, same as `docs/roadmap.md`, so it is not added to a toctree.

```bash
bash docs/build-pages.sh && python docs/check-pages.py
```
