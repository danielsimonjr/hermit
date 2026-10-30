---
orphan: true
---

# Roadmap: Pi as an acting agent

This page is a plan. None of it is implemented. `hermit deploy --host pi` and `hermit convert --target pi` already work; training and evaluation cannot name Pi as the acting agent.

The acting agent to add is the `pi` binary from the fork [danielsimonjr/pi](https://github.com/danielsimonjr/pi) (a fork of `earendil-works/pi`). The invocation below was read from that fork's `main` tree, under `packages/coding-agent/docs/`. Re-read those pages on the fork before coding. This repository stays the fork `danielsimonjr/hermit`. Nothing here is a change to `Infini-AI-Lab/hermit`.

## What already works

| Piece | Where | Behavior today |
|---|---|---|
| Workspace deploy | `hermit/hosts/pi.py` `prepare` | Writes `AGENTS.md`, `.pi/mcp.json`, and `.pi/skills`. Called by `hermit deploy --host pi` (`hermit/cli.py`, `--host` choices `codex`, `claude-code`, `pi`). |
| Role refusal | `hermit/hosts/pi.py` | An adapter whose rendered exports contain `agents` raises `ValueError` naming those roles and telling the caller to use `--host codex` or `--host claude-code`. `tests/test_deploy.py::test_pi_refuses_roles` covers that. |
| Trust split | `hermit/hosts/pi.py` module docstring | Pi reads `AGENTS.md` with no trust prompt. `.pi/mcp.json` and `.pi/skills` load only after the project is trusted. `~/.pi/agent` is never modified. |
| Plugin package | `hermit/plugins/pi_package.py` | `hermit convert --target pi` emits a package installed with `pi install`. A non-empty context or any roles are refused. `tests/test_convert.py::test_pi_package` covers the package. |
| Deploy tests | `tests/test_deploy.py::test_pi` | Lean template deploy writes the MCP entry, the managed `AGENTS.md` block, and `.pi/skills`, and a second deploy does not duplicate the block. |

`prepare` always writes `.pi/mcp.json` (`mcpServers` is `{}` when the adapter has no tools). On the fork, any of `.pi/mcp.json`, `.pi/skills`, or `.pi/extensions` is a trust-gated resource (`packages/coding-agent/docs/security.md`). Print and JSON modes cannot show the trust prompt. With no `--approve` and no saved decision, `defaultProjectTrust` of `"ask"` (the default) skips those resources. `AGENTS.md` still loads. `--approve` / `-a` trusts them for that process only (`packages/coding-agent/docs/cli.md`). It does not write `~/.pi/agent/trust.json`.

## What does not run Pi

The acting CLI is `hermit/agents/cli.py`. `BACKENDS` is `("codex", "claude")`. `_run` maps `claude-code` to `claude` and raises `ValueError` for anything else (`agent.params.backend must be one of ...`). `deploy()` imports `hermit.hosts.codex` or `hermit.hosts.claude_code` only. `command()` builds `codex exec --json ...` or `claude -p ... --output-format stream-json`.

Registration matches that pair:

- `hermit/agents/base.py` `builtin()` returns `CliAgent` for `cli`, `codex`, `claude-code`, and `claude`. `BUILTIN_NAMES` is `("react", "codex", "claude-code", "cli")`. `agent.name: pi` is loaded as a user callable and fails.
- `hermit/agents/__init__.py` documents `codex` and `claude-code` as the CLI agents.
- `hermit/backends.py` `CLI_AGENTS` is `{codex, claude-code, claude, cli}`. `NEEDS` maps `codex` to `responses` and `claude` to `messages`. `bind_agent_params` accepts kind `codex` or `claude` and raises otherwise. `normalize_config` and `bindings_of` map a `cli` backend only through `{codex, claude, claude-code}`.
- `hermit/isolate.py` `CLI_HOMES` is `codex` → (`.codex`, `CODEX_HOME`, `auth.json`) and `claude` → (`.claude`, `CLAUDE_CONFIG_DIR`, `.credentials.json`). `_cli_kind` returns a kind only when it is in `CLI_HOMES`, so an unknown name mounts no CLI binary and copies no login file.
- `hermit/sandbox.py` `ALWAYS` passes `CODEX_HOME` and `CLAUDE_CONFIG_DIR` even when `sandbox.env` is a list. `PI_CODING_AGENT_DIR` is absent.
- `hermit/evolver/agent.py` `parse_log` has a Codex branch (`thread.started`, `turn.completed`) and treats every other backend as Claude Code (`session_id`, `type: result`, `total_cost_usd`). `AgentEvolver._step` launches only `codex` and `claude`.

The docs describe the same pair. [Configuration](framework/configuration.md) lists built-in agents as `react`, `codex`, and `claude-code`. [Built-in agents](framework/task.md#built-in-agents) gives `codex` and `claude-code` the settings `model`, `prompt`, `files`, `args`, `price`, `timeout_s`, and `workspaces`. [Bring your own task](tutorials/your-own-task.md) tells the reader to write `pipeline.py:run` and to supply the adapter's exports from that pipeline. [Model backends](guides/model-backends.md) assigns Codex the Responses API and Claude Code the Messages API. The [field reference](reference/config-fields.md) repeats the acting-agent list and says a Codex or Claude Code reference becomes CLI provider settings.

`Usage` (`hermit/evolver/base.py`) has `input_tokens`, `cached_input_tokens`, `output_tokens`, `calls`, and `cost_usd`. There is no cache-write field.

## 1. Run Pi from the CLI acting agent

**Scope.** `agent.name: pi`, and `agent.name: cli` with `params.backend: pi`, run one task in a fresh workspace. When an adapter is passed, the workspace is filled by the existing `hermit.hosts.pi.prepare`. The process is the fork's one-shot JSON mode, with project trust granted for that process so the `.pi/` files `prepare` just wrote are loaded. An adapter that exports roles still fails with the `ValueError` `prepare` already raises. `~/.pi/agent` stays untouched.

This item does not parse usage and does not bind a model endpoint. A plain `--model` value is forwarded. Endpoint binding is item 3. The learner in `hermit/evolver/agent.py` stays on Codex and Claude Code.

**Files.**

- `hermit/agents/cli.py`. Add `"pi"` to `BACKENDS`. `deploy()` imports `prepare` from `hermit.hosts.pi` when the backend is `pi`. `command()` for `pi` returns:

  ```text
  pi --mode json --approve [--model MODEL] [extra args...] PROMPT
  ```

  `--mode json` runs the prompt, writes JSONL to stdout, and exits (`packages/coding-agent/docs/cli.md`). Stdout is already captured as `agent-<backend>.jsonl`. `--approve` is unconditional: `prepare` always writes `.pi/mcp.json`, and that file is trust-gated. The prompt is a positional argument. `subprocess.run` already sets `cwd` to the workspace and `stdin` to `DEVNULL` (a non-terminal stdin is extra prompt for these CLIs, and the fork prepends piped stdin to the first prompt). Do not add `--print`: that mode writes the final text to stdout and would replace the JSONL this log is.
- `hermit/agents/base.py`. `builtin("pi")` returns a `CliAgent` whose `params["backend"]` is `pi`, using the same pattern as `codex` and `claude-code`. Add `"pi"` to `BUILTIN_NAMES`.
- `hermit/agents/__init__.py`. Add `pi` to the `agent.name` table.
- Module docstring of `hermit/agents/cli.py`. Document `name: pi` beside `codex` and `claude-code`, including `--approve` and the role refusal.

**Tests.** Extend `tests/test_agents.py`:

- Add a `FAKE_PI` script and a third case of `test_cli_agent_with_fake_cli`. The fake executable is named `pi`. It records `"$*"` and prints one JSON object.
- `test_load_agent_builtin_class_function_and_alias`: `load_agent("pi", {"model": "m"}, tmp_path)` returns a `CliAgent` with `params["backend"] == "pi"`.
- A role adapter (the shape in `tests/test_deploy.py::subagent_adapter`) passed to `hermit.agents.cli.run` with `backend: pi` raises `ValueError` matching `reviewer`, and the workspace contains no `AGENTS.md` and no `.pi/`.
- `backend: hermes` still raises `ValueError` matching `BACKENDS`.

`tests/test_deploy.py::test_pi` and `tests/test_convert.py::test_pi_package` stay as they are.

**Acceptance.**

- `load_agent("pi", ..., base)` and `load_agent("cli", {"backend": "pi"}, base)` both construct `CliAgent`.
- With the file adapter at `docs/_examples/file_adapter` and a fake `pi` on `PATH`, the run returns that script's answer, `extra["backend"]` is `pi`, `extra["exit_code"]` is `0`, and the workspace is `<workspaces>/<task id>-<8 hex chars>`.
- The recorded argv contains `--mode`, `json`, and `--approve`, the formatted prompt, and the model when one was set. It contains neither `--print` nor `--api-key`.
- `AGENTS.md` in that workspace contains the managed block `hermit:file-example:start`. The log file is `agent-pi.jsonl`.
- A second call uses a new workspace directory.
- An adapter that exports a role fails with the existing Pi message from `hermit/hosts/pi.py`. Codex and Claude Code cases in `test_cli_agent_with_fake_cli` still pass.

## 2. Read Pi's JSON event stream into `RunOutput`

**Scope.** `parse_log(..., "pi", model)` and `last_message("pi", ...)` turn the JSONL from item 1 into the same `RunOutput` fields Codex and Claude Code already fill: `output`, `tokens`, `cost_usd`, and `api_speed["model_calls"]`. The workspace directory remains `RunOutput.log`.

The fork's event shapes (`packages/coding-agent/docs/json.md`, `packages/coding-agent/docs/message-types.md`):

- The first record is a session header: `{"type":"session","id":"...","cwd":"..."}`.
- An assistant `message_end` carries the completed message. `message.usage` is always present on an assistant message: `input`, `output`, `cacheRead`, `cacheWrite`, `totalTokens`, and `cost` (`input`, `output`, `cacheRead`, `cacheWrite`, `total`). `reasoning`, when present, is already included in `output`. `cacheWrite1h` is a subset of `cacheWrite`.
- `message_update.usage` is a cumulative snapshot for the in-flight assistant response. Summing those records counts the same tokens many times.
- `message_end.message.content` is an array of text, thinking, and tool-call blocks. Text lives on text blocks.
- A tool result may carry its own `usage` for nested model work. That usage is not the main model-call usage.

`parse_log`'s non-`codex` branch is Claude Code. Pi must be its own branch. Stderr is still merged into the log file (`stderr=subprocess.STDOUT` in `_run`). `parse_log` already skips lines that are not JSON.

**Files.**

- `hermit/evolver/agent.py` `parse_log`. For `backend == "pi"`: set the session from the `session` header's `id`. For each `message_end` whose `message.role` is `assistant`, add one call and that message's `usage` only. Map `input` → `input_tokens`, `cacheRead` → `cached_input_tokens`, `output` → `output_tokens`. Set `cost_usd` from `usage.cost.total` when it is a number. Ignore `message_update` and tool-result `usage`. Leave `cacheWrite` out of `Usage` (the dataclass has nowhere to put it).
- Before implementing the addition, record one `message_end` from the fork and see whether `usage.input` already includes `cacheRead`. `price_usage` bills `(input_tokens - cached_input_tokens)` at the input price and `cached_input_tokens` at the cached price (`hermit/evolver/agent.py`). Claude's parser adds cache reads into `input_tokens` so that formula does not drop them. The Codex fixture in `tests/test_agents.py` uses `input_tokens: 1000` and `cached_input_tokens: 200` and expects the cost to use 800 uncached tokens. Map Pi's numbers so the same formula bills uncached and cached tokens once each.
- `hermit/agents/cli.py` `last_message`. For `pi`, the output is the text blocks of the last assistant `message_end`, joined. A final assistant message that has no text block yields an empty string. The JSONL file is still the trajectory.
- Call the existing `price_usage` as `_run` does today. A `binding` whose `litellm` does not start with `anthropic/` clears a CLI-reported cost and replaces it from `params.price`. Pi's `cost.total` is that CLI-reported cost.

**Tests.** In `tests/test_agents.py`, extend the fake `pi` script to print:

1. a `session` header,
2. a `message_update` whose `usage.input` is large,
3. an assistant `message_end` with text content, a small `usage`, and `cost.total`,
4. a second assistant `message_end` whose text is the answer.

Assert the output is the second message's text, `tokens` is the sum of the two assistant messages' input and output (not the `message_update`), `api_speed["model_calls"]` is 2, and a `price` mapping produces the `price_usage` cost rather than the sum of `cost.total` when a non-Anthropic binding is present. A separate case with no binding and no `price` keeps `cost.total`. A tool-result record with its own `usage` does not change the totals.

**Acceptance.**

- Codex and Claude Code rows of `test_cli_agent_with_fake_cli` keep their token and cost assertions.
- Pi's `message_update` lines do not add tokens.
- `reasoning` is not added on top of `output`.
- `RunOutput.output` is the last assistant text. `RunOutput.log` is the workspace. `extra` still carries `backend`, `exit_code`, `timed_out`, and `workspace`.
- A timeout still sets `exit_code` to `-1` and `timed_out` to true, including when the log is empty or truncated.

## 3. Bind a hermit model backend into a private Pi agent directory

**Scope.** `agent.params.model` as a `<backend>/<model id>` reference configures the `pi` process to call that backend, the same way Codex receives `-c model_providers...` and Claude Code receives `ANTHROPIC_BASE_URL` (`hermit/backends.py` `bind_agent_params`, `Binding.codex_args`, `Binding.claude_env`). A model string that is not a reference stays a Pi model id and is passed as `--model`, which is the Codex and Claude Code rule for a plain id (`docs/guides/model-backends.md`).

Pi does not take a provider base URL on the command line. A compatible endpoint is a `providers` entry in `<agent-dir>/models.json` with `baseUrl`, `api`, `apiKey`, and `models[].id` (`packages/coding-agent/docs/models.md`, section "Configure a compatible endpoint"). The agent directory defaults to `~/.pi/agent` and moves with `PI_CODING_AGENT_DIR` (`packages/coding-agent/docs/environment-variables.md`, `packages/coding-agent/docs/configuration.md`). `apiKey` accepts `$NAME` interpolation. `--api-key` would put the secret on the command line; do not use it. `bind_agent_params` only edits the params dict, at config load, so it must not write the file. `_run` writes it.

`~/.pi/agent` is the global directory `hermit/hosts/pi.py` promises not to change. The acting agent always sets `PI_CODING_AGENT_DIR` to a directory it created for the call, whether or not the sandbox is on. Item 4 copies `auth.json` into that directory. This item writes `models.json` beside it and does not overwrite `auth.json`.

The `api` value comes from the backend's `apis` (`hermit/backends.py` `NEEDS` is the existing single-dialect table; Pi can speak more than one):

| Backend serves | `models.json` `api` | Dialect stored for preflight |
|---|---|---|
| `chat` | `openai-completions` | `chat` |
| `responses`, and not `chat` | `openai-responses` | `responses` |
| neither | no file; `problems_of` fails | |

Those two `api` strings are the ones the fork's models page names for OpenAI-compatible sampling. A backend that serves only `messages` fails preflight until a models.json `api` string for the Messages API is confirmed on the fork. `problems_of` already explains a missing `chat`, `responses`, or `messages` dialect; add a Pi-specific hint for this choice.

Built-in Pi provider names (`anthropic`, `openai`, `fireworks`, `deepseek`, and the others in the fork's providers table) are not used via `--provider` when a hermit binding exists. `--provider fireworks` would call Pi's own Fireworks endpoint, not the `base_url` in `hermit/backends.yaml`. The binding's `base_url` is `models.json` `baseUrl`.

`apiKey` is `$` plus the binding's `api_key_env` when that variable is set. When the backend has `key_required: false` and no key is set, `apiKey` is the existing placeholder `local` (`PLACEHOLDER_KEY` in `hermit/backends.py`). The literal key never goes into params, the JSONL, or `models.json`.

Model ids in this repo contain slashes (`accounts/fireworks/models/glm-5p3-flash` in `hermit/backends.yaml`). `models.json` `models[].id` stores that id whole. `--model` is `<provider>/<id>` only after a one-shot on the fork shows that a slashed id resolves; until that check, pass `--provider <name> --model <id>` as two arguments and record the fork's result in the test comment. The provider name written into `models.json` is the backend name sanitized to the character set Pi accepts for a provider key. Confirm that set on the fork; the unit test asserts the name `_run` actually wrote.

**Files.**

- `hermit/backends.py`. Extend `bind_agent_params` so kind `pi` sets `model` to the binding's model id, copies `price` and `binding` as the other kinds do, and stores a JSON-ready provider document on the params (the `baseUrl`, `api`, `apiKey` expression, model id, and chosen dialect). Raise for an unknown kind the way the function does now. Add `pi` to `CLI_AGENTS`. In `normalize_config` and `bindings_of`, treat a `cli` param `backend: pi` as kind `pi`. `bindings_of` reports the dialect chosen above so `problems_of` and `hermit/isolate.py` `_model_access` see the agent. `_model_access` already allows `binding.base_url` and appends `binding.api_key_env` for every binding whose label starts with `agent`.
- `hermit/agents/cli.py` `_run`. After `deploy`, if `PI_CODING_AGENT_DIR` is unset, create `<workspace>/.pi-agent` and export it on the child environment. Write `models.json` there when the params carry a provider document. Leave an existing `auth.json` in place.
- `hermit/evolver/agent.py` is unchanged. `evolver.name: codex` and `evolver.name: claude` keep their current commands.

**Tests.**

- `tests/test_backends.py`: a `bind_agent_params(..., "pi", ...)` case for `vllm/Qwen/Qwen3-30B-A3B-Instruct-2507-FP8` and for `fireworks/accounts/fireworks/models/glm-5p3-flash`. Assert `baseUrl`, `api` (`openai-completions` for both; those backends list `chat` in `hermit/backends.yaml`), the `$VARIABLE` key expression, and that the returned params contain no secret. A plain model id `sonnet` is returned unchanged. Kind `"hermes"` still raises `ValueError`.
- `normalize_config` with `agent.name: pi` and a top-level `model` reference fills `agent.params.binding`, and `bindings_of` yields `("agent (pi)", binding, "chat")`.
- `tests/test_agents.py`: the fake `pi` run with a bound model asserts `models.json` under the private agent dir and asserts the child environment contains `PI_CODING_AGENT_DIR` pointing at that dir. `~/.pi/agent` is not created by the test (use a temporary `HOME`).

**Acceptance.**

- `hermit train` preflight rejects a Pi agent bound to a backend whose `apis` are only `messages`, with the new hint, and accepts `vllm` and `fireworks`.
- The key variable name is in the child environment and in the sandbox allow-list via `_model_access`. The key value appears in neither `models.json` nor `agent.params`.
- A second task gets a new agent directory. The first directory's `models.json` is not reused.
- Codex and Claude Code bindings in `tests/test_backends.py` keep their `args` and `env` assertions.

## 4. Sandbox the Pi binary and its login

**Scope.** A sandboxed rollout, eval, or check (`hermit/isolate.py` `SandboxedAgent`) that runs `agent.name: pi` can execute `pi`, can read the copied login, and cannot keep that login after the call. The binary mount uses the existing `program_paths` helper (`hermit/sandbox.py`), which follows the `pi` symlink, the package above its `bin/` directory, and the `node` interpreter named by the shebang.

The fork stores saved credentials in `<agent-dir>/auth.json`. The user file is `~/.pi/agent/auth.json`.

**Files.**

- `hermit/isolate.py`. Add a `pi` entry to `CLI_HOMES`: directory `.pi/agent` relative to the call's home, variable `PI_CODING_AGENT_DIR`, login file `auth.json`. `_cli_kind` then returns `pi` for `agent.name: pi` and for `agent.name: cli` with `params.backend: pi`, because `CLI_AGENTS` from item 3 maps those names and the new entry is in `CLI_HOMES`. The existing block copies `~/.pi/agent/auth.json` into `<call home>/.pi/agent/auth.json`, sets the variable, and unlinks the copy in the `finally` (mode `0o600`, same as the Codex and Claude Code copies). `program_paths("pi")` is added to the readable paths because `self.cli` is set.
- `hermit/sandbox.py` `ALWAYS`. Add `PI_CODING_AGENT_DIR` next to `CODEX_HOME` and `CLAUDE_CONFIG_DIR`.
- `hermit/agents/cli.py` `_run`. When `PI_CODING_AGENT_DIR` is already set (the sandbox set it), write `models.json` into that directory and do not create a second one. When the sandbox is off, keep item 3's private directory under the workspace and copy `~/.pi/agent/auth.json` into it for the call, then delete the copy. The unsandboxed Codex path uses the real `~/.codex`; Pi does not use the real `~/.pi/agent`, because item 3 writes `models.json` and the host promise forbids changing that directory.

**Tests.**

- A unit test with the sandbox disabled (`profiles.rollout.enabled: false` is the existing switch; see `hermit/isolate.py` `profile`) is not required for the login copy. Add a focused test that calls `SandboxedAgent._cli_kind` logic through a config whose agent name is `pi` and asserts the kind is `pi`. Follow the style of `tests/test_isolate.py`.
- With bubblewrap available, one `@needs_bwrap` test, next to `test_a_cli_deploy_renders_the_adapter_in_a_sandbox`, runs a fake `pi` under `SandboxedAgent` and asserts: `PI_CODING_AGENT_DIR` is inside the call work directory; `auth.json` there matches a fixture planted in a temporary home; after the call the copy is gone; the planted `~/.pi/agent/auth.json` is unchanged; `models.json` from item 3 is in the same directory.
- Assert `program_paths` is asked for `pi`: the fake binary's directory is readable inside the sandbox (the script can read a marker file placed beside it). A home directory sibling of that binary is not readable.

**Acceptance.**

- `agent.name: codex` and `agent.name: claude-code` still copy `auth.json` and `.credentials.json` respectively. Their `CLI_HOMES` entries are unchanged.
- A missing `~/.pi/agent/auth.json` does not fail the call. Pi then has only `models.json` and the `$VARIABLE` key.
- The login file mode is `0o600`, and the unlink uses `missing_ok` as the current `finally` block does.
- `PI_CODING_AGENT_DIR` survives a `sandbox.profiles.rollout.env` allow-list because it is in `ALWAYS`.

## 5. Document the acting agent where tasks are configured

**Scope.** A reader of the configuration page and of [Bring your own task](tutorials/your-own-task.md) can point a run at Pi without writing `pipeline.py`. The tutorial's rule stands: the pipeline must supply the adapter's exports. For this built-in agent, `CliAgent` does that by calling `hermit.hosts.pi.prepare`, which is the same function as `hermit deploy --host pi`. Publish the limits that are already true: roles cannot be deployed, `.pi/` resources require the trust grant item 1 passes as `--approve`, and `~/.pi/agent` is not the place a run writes.

The learner is still Codex or Claude Code. `evolver.name` does not gain `pi`. Say that on the configuration page so `agent.name: pi` is not read as the learner.

**Files.**

- `docs/framework/task.md`, section "Built-in agents". Add a row for `pi` with the shared settings `model`, `prompt`, `files`, `args`, `env`, `price`, `timeout_s`, `workspaces`, plus the Pi-only facts: JSON mode, `--approve`, role refusal, private `PI_CODING_AGENT_DIR`.
- `docs/framework/configuration.md`. Add `pi` to the built-in list in the opening and in the `agent.name` row of "What each section controls". State that `llm.model` still does not change the acting CLI, and that Pi takes `agent.params.model`.
- `docs/tutorials/your-own-task.md`, section "Implement the acting pipeline". Add a short subsection: a task whose actor is Pi sets `agent.name: pi` and does not need `pipeline.py`. Show a minimal `run.yaml` fragment (`agent.name`, `agent.params.prompt`, `agent.params.model` as a `<backend>/<model id>` reference). Point at [Built-in agents](framework/task.md#built-in-agents) and at [Commands](framework/commands.md) for `deploy --host pi`. Keep the custom-pipeline path for everyone else.
- `docs/guides/model-backends.md`. Add a row: `agent.name: pi` speaks `openai-completions` when the backend serves `chat`, otherwise `openai-responses`. Note the private `models.json`.
- `docs/reference/config-fields.md`. Add `pi` to the `agent.name` cell and to the paragraph that describes how a reference becomes CLI provider settings. Pi's settings go into a per-call `models.json`, not into `args` or `env` alone.
- `docs/framework/commands.md`. The deploy and convert sections already describe Pi. Add one sentence under deploy: a training run with `agent.name: pi` deploys each task workspace the same way and then runs `pi --mode json --approve` there.

**Tests.** No new Python tests. The docs build is the test, and it is the only CI job (`.github/workflows/pages.yml`).

**Acceptance.**

- `bash docs/build.sh` exits 0. Every new link uses a path that exists, including `framework/task.md#built-in-agents`.
- The new sentences describe the behavior items 1–4 implement. They do not describe `evolver.name: pi`.
- `docs/framework/commands.md` still says `hermit deploy` does not launch the agent. The new sentence is about `agent.name: pi` during `train` and `eval`.

## Out of scope

- Teaching `AgentEvolver` (`hermit/evolver/agent.py` `_step`) to launch Pi, register evolver tools, or resume a Pi session. `parse_log` grows a Pi branch because the acting agent already shares that function. The learner command stays `codex` or `claude`.
- Changing `hermit/hosts/pi.py` or `hermit/plugins/pi_package.py`, except if item 1's tests show `prepare` writing something the fork no longer loads. Role refusal and the "do not edit `~/.pi/agent`" rule stay.
- A Hermes acting agent. Hermes is a convert target (`hermit/plugins/__init__.py` `EMITTERS`) and is not in `BACKENDS`.
- Editing `Infini-AI-Lab/hermit`.

## Suggested order

Item 1 is independently testable with a fake `pi` and a plain `--model`. Item 2 lands in the same change or immediately after, because the fake script already prints JSONL. Item 3 depends on item 1's child environment. Item 4 depends on item 3's `CLI_AGENTS` entry and on the private agent directory. Item 5 lands with the change that makes the behavior true, so the docs do not describe a missing agent.
