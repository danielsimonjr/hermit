"""The built-in acting agents: the react loop against a scripted chat server, the CLI agent against fake CLIs,
and pipeline.params reaching a pipeline that asks for them."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading

import pytest

from hermit.task import load_pipeline

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs" / "_examples" / "file_adapter"

TOOLS_PY = '''
from hermit.agents import tool

@tool("Add two integers.", {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
      "required": ["a", "b"]})
def add(a: int, b: int) -> dict:
    return {"sum": a + b}

@tool("The task id.")
def whoami(_task) -> str:
    return _task["id"]
'''


class Scripted:
    """A chat/completions server that answers from a list of scripted assistant messages and records requests."""

    def __init__(self, replies):
        self.replies, self.requests = list(replies), []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                message = outer.replies.pop(0)
                payload = {"choices": [{"message": message, "finish_reason": "stop"}],
                           "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
                data = json.dumps(payload).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

            def log_message(self, *args):
                pass
        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"


def call(name, arguments, cid):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def test_react_loop(tmp_path):
    (tmp_path / "tools.py").write_text(TOOLS_PY)
    (tmp_path / "prompt.md").write_text("You add numbers.\n\n{context}\n")
    server = Scripted([
        {"role": "assistant", "content": None, "tool_calls": [call("add", {"a": 2, "b": 3}, "c1"), call("whoami", {}, "c2")]},
        {"role": "assistant", "content": None, "tool_calls": [call("count_words", {"text": "x y z"}, "c3"), call("nope", {}, "c4")]},
        {"role": "assistant", "content": "The sum is 5."},
        {"role": "assistant", "content": "<FINAL_ANSWER>5</FINAL_ANSWER>"},
    ])
    params = {"model": {"base_url": server.url, "model": "m", "price": {"input": 1, "output": 2}},
              "prompt": "prompt.md", "tools": "tools.py", "user": "Q: {question}", "answer_tag": "FINAL_ANSWER",
              "logs": "logs"}
    run = load_pipeline("hermit.agents.react:run", tmp_path, params)
    out = run({"id": "t1", "question": "2+3?"}, EXAMPLE)

    first = server.requests[0]
    assert first["messages"][0]["content"].startswith("You add numbers.") and "Review the task" in first["messages"][0]["content"]
    assert first["messages"][1] == {"role": "user", "content": "Q: 2+3?"}
    assert [t["function"]["name"] for t in first["tools"]] == ["add", "whoami", "count_words"]
    tool_msgs = [m for m in out.messages if m["role"] == "tool"]
    assert [m["content"] for m in tool_msgs] == ['{"sum": 5}', '"t1"', '{"count": 3}', "Error: unknown tool nope"]
    assert "tools" not in server.requests[3]          # the answer-tag retry goes without tools
    assert out.output == "<FINAL_ANSWER>5</FINAL_ANSWER>" and out.extra == {"turns": 4, "tool_calls": 4}
    assert out.tokens == 440 and out.cost_usd == pytest.approx((400 * 1 + 40 * 2) / 1e6)
    assert out.log.parent == tmp_path / "logs" and json.loads(out.log.read_text())["task"] == "t1"
    server.server.shutdown()


def test_react_without_adapter_or_tools(tmp_path):
    server = Scripted([{"role": "assistant", "content": "hello"}])
    run = load_pipeline("hermit.agents.react:run", tmp_path, {"model": {"base_url": server.url, "model": "m"},
                                                                       "prompt": "Be brief."})
    out = run({"id": "t2", "prompt": "hi"}, None)
    assert out.output == "hello" and out.cost_usd is None and "tools" not in server.requests[0]
    assert server.requests[0]["messages"][0]["content"] == "Be brief.\n"
    server.server.shutdown()


FAKE_CODEX = '''#!/bin/sh
# a stand-in for `codex exec --json ... -o LAST PROMPT`: records the arguments, writes events and the last message
last=""; prev=""
for a in "$@"; do [ "$prev" = "-o" ] && last="$a"; prev="$a"; done
printf '%s\\n' "$*" > "$(dirname "$last")/.args"
echo '{"type":"thread.started","thread_id":"th1"}'
echo '{"type":"turn.completed","usage":{"input_tokens":1000,"cached_input_tokens":200,"output_tokens":50}}'
printf 'ANSWER 42' > "$last"
'''
FAKE_CLAUDE = '''#!/bin/sh
printf '%s\\n' "$*" > .args
echo '{"type":"system","session_id":"s1"}'
echo '{"type":"result","result":"ANSWER 43","num_turns":3,"total_cost_usd":0.5,"usage":{"input_tokens":10,"output_tokens":5,"cache_read_input_tokens":0}}'
'''
FAKE_PI = '''#!/bin/sh
printf '%s\\n' "$@" > .args
echo '{"type":"session","id":"ps1","cwd":"/tmp"}'
echo '{"type":"message_update","usage":{"input":99999}}'
echo '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"draft"},{"type":"thinking","thinking":"x"}],"usage":{"input":10,"output":4,"cacheRead":3,"cacheWrite":1,"reasoning":2,"cost":{"total":0.01}}}}'
echo '{"type":"message_end","message":{"role":"toolResult","usage":{"input":100,"output":50,"cacheRead":0,"cost":{"total":9}}}}'
echo '{"type":"message_end","message":{"role":"assistant","content":[{"type":"thinking","thinking":"plan"},{"type":"text","text":"ANSWER 44"}],"usage":{"input":20,"output":5,"cacheRead":0,"cacheWrite":0,"cost":{"total":0.02}}}}'
'''


def _isolated_home(tmp_path, monkeypatch, name="home"):
    """A temporary HOME, so a test can see whether anything is written under `~/.pi`. The real user site stays
    importable: the deployed adapter's MCP check runs a fresh interpreter."""
    import site
    user_site = site.getusersitepackages()
    if user_site:
        monkeypatch.setenv("PYTHONPATH", user_site + os.pathsep + os.environ.get("PYTHONPATH", ""))
    home = tmp_path / name
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.mark.parametrize("backend,script,answer", [
    ("codex", FAKE_CODEX, "ANSWER 42"),
    ("claude-code", FAKE_CLAUDE, "ANSWER 43"),
    ("pi", FAKE_PI, "ANSWER 44"),
])
def test_cli_agent_with_fake_cli(tmp_path, monkeypatch, backend, script, answer):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if backend == "codex":
        exe = bin_dir / "codex"
    elif backend == "pi":
        exe = bin_dir / "pi"
    else:
        exe = bin_dir / "claude"
    exe.write_text(script)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    (tmp_path / "prompt.md").write_text("Solve {question} in this workspace.")
    params = {"backend": backend, "prompt": "prompt.md", "price": {"input": 1, "cached_input": 0.5, "output": 2},
              "workspaces": "ws", "model": "m1"}
    adapter = EXAMPLE
    if backend == "pi":
        from test_convert import variant
        adapter = variant(tmp_path / "pi_adapter", roles=False)      # Pi refuses the example's role
        home = _isolated_home(tmp_path, monkeypatch)
    run = load_pipeline("hermit.agents.cli:run", tmp_path, params)
    out = run({"id": "q7", "question": "6*7"}, adapter)

    ws = out.log
    assert ws.parent == tmp_path / "ws" and re.fullmatch(r"q7-[0-9a-f]{8}", ws.name) and out.output == answer
    if backend == "codex":
        context_file = ws / "AGENTS.md"
    elif backend == "pi":
        context_file = ws / "AGENTS.md"
    else:
        context_file = ws / "CLAUDE.md"
    assert "hermit:file-example:start" in context_file.read_text()     # the adapter was deployed
    args = (ws / ".args").read_text()
    assert "Solve 6*7 in this workspace." in args
    if backend != "pi":
        assert "m1" in args
    log_name = {"codex": "codex", "claude-code": "claude", "pi": "pi"}[backend]
    assert (ws / f"agent-{log_name}.jsonl").is_file()
    if backend == "codex":
        assert out.tokens == 1050 and out.cost_usd == pytest.approx((800 * 1 + 200 * 0.5 + 50 * 2) / 1e6)
    elif backend == "claude-code":
        assert out.cost_usd == 0.5 and out.tokens == 15
    else:
        assert args.splitlines() == ["--mode", "json", "--approve", "--model", "m1", "--",
                                     "Solve 6*7 in this workspace."]
        assert not (home / ".pi").exists()
        assert run({"id": "q7", "question": "6*7"}, adapter).log != ws
    assert out.extra["exit_code"] == 0 and out.extra["backend"] in ("codex", "claude", "pi")
    assert out.extra["timed_out"] is False


def test_load_pipeline_binds_only_what_is_asked(tmp_path):
    (tmp_path / "p.py").write_text(
        "def plain(task, adapter):\n    return ('plain', task, adapter)\n"
        "def wants(task, adapter, *, params, base):\n    return (params, base)\n")
    plain = load_pipeline("p.py:plain", tmp_path, {"k": 1})
    assert plain({"id": 1}, None) == ("plain", {"id": 1}, None)
    wants = load_pipeline("p.py:wants", tmp_path, {"k": 1})
    assert wants({"id": 1}, None) == ({"k": 1}, tmp_path)


def test_load_agent_builtin_class_function_and_alias(tmp_path):
    from hermit.agents import Agent, FunctionAgent, load_agent
    from hermit.agents.react import ReactAgent
    from hermit.agents.cli import CliAgent
    from hermit.config import Config
    assert isinstance(load_agent("react", {"model": {}}, tmp_path), ReactAgent)
    claude = load_agent("claude-code", {"model": "m"}, tmp_path)
    assert isinstance(claude, CliAgent) and claude.params["backend"] == "claude" and claude.base == tmp_path.resolve()
    pi = load_agent("pi", {"model": "m"}, tmp_path)
    assert isinstance(pi, CliAgent) and pi.params["backend"] == "pi"
    cli_pi = load_agent("cli", {"backend": "pi"}, tmp_path)
    assert isinstance(cli_pi, CliAgent) and cli_pi.params["backend"] == "pi"
    (tmp_path / "agent.py").write_text(
        "from hermit.agents import Agent\nfrom hermit.task import RunOutput\n"
        "class Mine(Agent):\n    def run(self, task, adapter):\n        return RunOutput(output=(self.params['k'], str(self.base.name), adapter))\n"
        "def plain(task, adapter):\n    return RunOutput(output='plain')\n")
    mine = load_agent("agent.py:Mine", {"k": 1}, tmp_path)
    assert isinstance(mine, Agent) and mine.run({"id": 1}, None).output == (1, tmp_path.name, None)
    plain = load_agent("agent.py:plain", {}, tmp_path)
    assert isinstance(plain, FunctionAgent) and plain.run({}, None).output == "plain"
    with pytest.raises(ValueError):
        load_agent("", {}, tmp_path)
    # the older `pipeline:` spelling still configures the agent
    (tmp_path / "tasks.jsonl").write_text('{"id": "a"}\n'); (tmp_path / "train.txt").write_text("a\n")
    (tmp_path / "judge.py").write_text("def score(task, output):\n    return 1.0\n")
    (tmp_path / "run.yaml").write_text(
        "data: {tasks: tasks.jsonl, train: train.txt}\npipeline: {run: 'agent.py:plain', concurrency: 2, params: {x: 1}}\n"
        "judge: {path: judge.py}\ntemplate: prompt-only@1.0\nevolver: {name: gepa}\n")
    cfg = Config.load(tmp_path / "run.yaml", [])
    assert cfg["agent"] == {"name": "agent.py:plain", "concurrency": 2, "timeout_min": None, "params": {"x": 1}}


def test_pi_cli_refuses_roles(tmp_path, monkeypatch):
    from test_deploy import subagent_adapter
    from hermit.agents.cli import run

    adapter = subagent_adapter(tmp_path)
    with pytest.raises(ValueError, match="reviewer"):
        run({"id": "t1"}, adapter, params={"backend": "pi", "prompt": "x"}, base=tmp_path)
    [ws] = (tmp_path / ".logs" / "workspaces").iterdir()      # `_run` makes the workspace before it deploys
    assert not (ws / "AGENTS.md").exists() and not (ws / ".pi").exists()


def test_cli_rejects_an_unknown_backend(tmp_path):
    from hermit.agents.cli import run

    with pytest.raises(ValueError, match="must be one of") as exc:
        run({"id": "t1"}, None, params={"backend": "hermes", "prompt": "x"}, base=tmp_path)
    msg = str(exc.value)
    assert "codex" in msg and "pi" in msg
    assert not (tmp_path / ".logs").exists()


def _fake_pi_on_path(tmp_path, monkeypatch, script=FAKE_PI):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    exe = bin_dir / "pi"
    exe.write_text(script)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def _pi_run(tmp_path, monkeypatch, params=None):
    from test_convert import variant

    _fake_pi_on_path(tmp_path, monkeypatch)
    _isolated_home(tmp_path, monkeypatch)
    adapter = tmp_path / "pi_adapter" / "adapter"
    if not adapter.is_dir():
        variant(tmp_path / "pi_adapter", roles=False)
    (tmp_path / "prompt.md").write_text("Solve {question}.")
    run = load_pipeline("hermit.agents.cli:run", tmp_path,
                        {"backend": "pi", "prompt": "prompt.md", "workspaces": "ws", "model": "m1", **(params or {})})
    return run({"id": "q7", "question": "6*7"}, adapter)


def test_pi_jsonl_fills_output_tokens_and_cost(tmp_path, monkeypatch):
    binding = {"ref": "vllm/q", "backend": "vllm", "model": "q", "base_url": "http://127.0.0.1:8000/v1",
               "litellm": "hosted_vllm/q", "apis": ["chat"]}
    out = _pi_run(tmp_path, monkeypatch, {"price": {"input": 1, "cached_input": 0.5, "output": 2}, "binding": binding})
    assert out.output == "ANSWER 44"
    assert out.tokens == 42 and out.api_speed["model_calls"] == 2
    assert out.cost_usd == pytest.approx(((33 - 3) * 1 + 3 * 0.5 + 9 * 2) / 1e6)
    out2 = _pi_run(tmp_path, monkeypatch)
    assert out2.cost_usd == 0.03 and out2.tokens == 42


def test_parse_log_pi_ignores_snapshots_reasoning_and_tool_usage(tmp_path):
    from hermit.evolver.agent import parse_log

    log = tmp_path / "agent-pi.jsonl"
    log.write_text(
        '{"type":"session","id":"ps1","cwd":"/tmp"}\n'
        '{"type":"message_update","usage":{"input":99999}}\n'
        '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"draft"}],'
        '"usage":{"input":10,"output":4,"cacheRead":3,"cacheWrite":1,"reasoning":2,"cost":{"total":0.01}}}}\n'
        '{"type":"message_end","message":{"role":"toolResult","usage":{"input":100,"output":50,"cacheRead":0,"cost":{"total":9}}}}\n'
        '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"ANSWER 44"}],'
        '"usage":{"input":20,"output":5,"cacheRead":0,"cacheWrite":0,"cost":{"total":0.02}}}}\n'
    )
    session, usage = parse_log(log, "pi", "m")
    assert session == "ps1" and len(usage) == 1
    u = usage[0]
    assert u.calls == 2 and u.output_tokens == 9
    assert u.input_tokens == 33 and u.cached_input_tokens == 3
    assert u.cost_usd == pytest.approx(0.03)                  # the tool result's 9 is nested work, not this call
    assert not [name for name in vars(u) if "write" in name]  # Usage has nowhere to put cacheWrite


@pytest.mark.parametrize("script", [FAKE_PI.replace("#!/bin/sh", "#!/bin/sh\nsleep 2"),
                                    "#!/bin/sh\nprintf '{\"type\":'\nsleep 2\n"], ids=["empty-log", "truncated-line"])
def test_pi_timeout_sets_exit_code(tmp_path, monkeypatch, script):
    _fake_pi_on_path(tmp_path, monkeypatch, script)
    run = load_pipeline("hermit.agents.cli:run", tmp_path,
                        {"backend": "pi", "prompt": "hi", "timeout_s": 0.2, "workspaces": "ws"})
    out = run({"id": "t1"}, None)
    assert out.extra["exit_code"] == -1 and out.extra["timed_out"] is True
    assert out.output == "" and out.tokens is None and out.cost_usd is None


def test_pi_models_json_uses_a_private_agent_dir(tmp_path, monkeypatch):
    import site
    from test_backends import GLM, reg
    from test_convert import variant
    from hermit.backends import bind_agent_params

    monkeypatch.setenv("FIREWORKS_API_KEY", "sekret")
    bound = bind_agent_params({"backend": "pi", "model": f"fireworks/{GLM}"}, "pi", reg())
    script = FAKE_PI.replace("#!/bin/sh", '#!/bin/sh\necho "$PI_CODING_AGENT_DIR" > .pi-dir')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "pi").write_text(script)
    (bin_dir / "pi").chmod(stat.S_IEXEC | stat.S_IRUSR | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    user_site = site.getusersitepackages()
    if user_site:
        monkeypatch.setenv("PYTHONPATH", user_site + os.pathsep + os.environ.get("PYTHONPATH", ""))
    adapter_root = tmp_path / "pi_adapter"
    adapter = variant(adapter_root, roles=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (tmp_path / "prompt.md").write_text("Solve {question}.")
    run = load_pipeline("hermit.agents.cli:run", tmp_path, {"backend": "pi", "prompt": "prompt.md", "workspaces": "ws",
                                                             **bound})
    out = run({"id": "q7", "question": "6*7"}, adapter)
    ws = out.log
    agent_dir = ws / ".pi-agent"
    models = json.loads((agent_dir / "models.json").read_text())
    assert agent_dir.is_dir() and not (home / ".pi").exists()
    prov = bound["pi_provider"]
    assert models["providers"][prov["name"]]["apiKey"] == "$FIREWORKS_API_KEY"
    args = (ws / ".args").read_text()
    assert "--provider" in args and prov["name"] in args and "--model" in args and GLM in args
    assert "--api-key" not in args and "sekret" not in args
    first_dir = agent_dir.resolve()
    out2 = run({"id": "q8", "question": "6*7"}, adapter)
    second_dir = (out2.log / ".pi-agent").resolve()
    assert second_dir != first_dir
    assert not first_dir.joinpath("models.json").samefile(second_dir / "models.json")

    from hermit.agents.cli import last_message
    from hermit.evolver.agent import parse_log

    log = tmp_path / "agent-pi.jsonl"
    log.write_text(
        '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"ANSWER 44"}],'
        '"usage":{"input":20,"output":5,"cacheRead":0,"cost":{"total":0.02}}}}\n'
        "42\n"                     # JSON, but no record: stderr shares this file
        "{\n"
    )
    _, usage = parse_log(log, "pi", "m")
    assert usage[0].output_tokens == 5
    assert last_message("pi", log, tmp_path / ".last") == "ANSWER 44"
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    assert parse_log(empty, "pi", "m") == (None, [])
    assert last_message("pi", empty, tmp_path / ".last") == ""


def test_last_message_pi_is_the_text_of_the_last_assistant_message(tmp_path):
    from hermit.agents.cli import last_message

    log = tmp_path / "agent-pi.jsonl"
    text = '{"type":"message_end","message":{"role":"assistant","content":[%s]}}\n'
    log.write_text(text % '{"type":"text","text":"a"},{"type":"thinking","thinking":"x"},{"type":"text","text":"b"}')
    assert last_message("pi", log, tmp_path / ".last") == "ab"              # joined with no separator
    with log.open("a") as out:
        out.write('{"type":"message_end","message":{"role":"toolResult","content":[{"type":"text","text":"tool"}]}}\n')
    assert last_message("pi", log, tmp_path / ".last") == "ab"              # a tool result is not the answer
    with log.open("a") as out:
        out.write(text % '{"type":"toolCall","id":"c1","name":"bash","arguments":{}}')
    assert last_message("pi", log, tmp_path / ".last") == ""                # the last message has no text block
