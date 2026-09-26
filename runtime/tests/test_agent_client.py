"""Tests for the Agent SDK adapter's pure translation surface — ADR-002 §3.3.

The live ``AnthropicAgentClient.propose`` needs the SDK + a key and is not exercised here;
``interpret_response`` and ``tool_schemas`` carry the SDK-agnostic logic and are tested in full.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.agent_client import (  # noqa: E402
    build_cli_argv,
    cli_allowed_tools,
    interpret_response,
    parse_cli_result,
    parse_cli_stream,
    tool_schemas,
    with_identity_lock,
)
from cortex_runtime.safety import ActionKind  # noqa: E402
from cortex_runtime.tools import Tool, ToolRegistry  # noqa: E402


class InterpretResponseTests(unittest.TestCase):
    def test_tool_use_blocks_become_tool_calls(self):
        blocks = [
            {"type": "text", "text": "let me check"},
            {"type": "tool_use", "name": "read_db", "input": {"q": "SELECT 1"}},
        ]
        turn = interpret_response(blocks)
        self.assertFalse(turn.is_final)
        self.assertEqual(len(turn.tool_calls), 1)
        self.assertEqual(turn.tool_calls[0].name, "read_db")
        self.assertEqual(turn.tool_calls[0].args, {"q": "SELECT 1"})

    def test_text_only_is_final(self):
        turn = interpret_response([{"type": "text", "text": "diagnosis: "},
                                   {"type": "text", "text": "OOM"}])
        self.assertTrue(turn.is_final)
        self.assertEqual(turn.final_text, "diagnosis: OOM")

    def test_works_with_object_blocks(self):
        class Block:
            def __init__(self, **kw):
                self.__dict__.update(kw)
        turn = interpret_response([Block(type="tool_use", name="comment", input={})])
        self.assertEqual(turn.tool_calls[0].name, "comment")


class ToolSchemasTests(unittest.TestCase):
    def test_renders_anthropic_tool_defs(self):
        reg = ToolRegistry()
        reg.register(Tool("read_db", ActionKind.DB_READ, lambda **k: None, description="read the DB"))
        reg.register(Tool("comment", ActionKind.INTERNAL_COMMENT, lambda **k: None))
        schemas = tool_schemas(reg)
        self.assertEqual([s["name"] for s in schemas], ["comment", "read_db"])  # sorted
        self.assertEqual(schemas[1]["description"], "read the DB")
        self.assertEqual(schemas[0]["description"], "internal-comment")          # falls back to kind
        self.assertEqual(schemas[0]["input_schema"]["type"], "object")


class ClaudeCliHelpersTests(unittest.TestCase):
    def test_allowed_tools_maps_read_only_by_default(self):
        self.assertEqual(cli_allowed_tools(["code-read"]), "Read,Grep,Glob")

    def test_allowed_tools_adds_write_when_granted(self):
        self.assertEqual(cli_allowed_tools(["code-read", "code-write"]),
                         "Read,Grep,Glob,Edit,Write")

    def test_allowed_tools_ignores_non_cli_actions(self):
        # db-read / issue-create have no built-in CLI tool → not mapped
        self.assertEqual(cli_allowed_tools(["db-read", "issue-create", "internal-comment"]), "")

    def test_build_argv_shape(self):
        argv = build_cli_argv(system_prompt_file="/tmp/sp.md", model="claude-opus-4-8",
                              allowed_tools="Read,Grep")
        self.assertEqual(argv[:2], ["claude", "-p"])
        self.assertEqual(argv[argv.index("--append-system-prompt-file") + 1], "/tmp/sp.md")
        self.assertIn("--allowedTools", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "Read,Grep")
        self.assertEqual(argv[argv.index("--model") + 1], "claude-opus-4-8")

    def test_build_argv_omits_empty_allowed_tools(self):
        argv = build_cli_argv(system_prompt_file="/tmp/sp.md", model="m", allowed_tools="")
        self.assertNotIn("--allowedTools", argv)

    def test_parse_result_extracts_text_and_usage(self):
        stdout = '{"result": "diagnosis here", "total_cost_usd": 0.012, ' \
                 '"usage": {"input_tokens": 100, "output_tokens": 50}}'
        text, usage = parse_cli_result(stdout)
        self.assertEqual(text, "diagnosis here")
        self.assertEqual(usage["total_cost_usd"], 0.012)
        self.assertEqual(usage["input_tokens"], 100)

    def test_build_argv_stream_json_adds_verbose(self):
        argv = build_cli_argv(system_prompt_file="/tmp/sp.md", model="m", allowed_tools="Read",
                              output_format="stream-json")
        self.assertIn("--verbose", argv)

    def test_allowed_tools_includes_mcp_bindings(self):
        # internal-comment (granted by default) maps to the workspace's Jira MCP tool
        bindings = {"internal-comment": ["mcp__jira__add_comment"], "issue-read": ["mcp__jira__get_issue"]}
        tools = cli_allowed_tools(["code-read", "internal-comment"], bindings)
        self.assertIn("Read", tools)                       # built-in for code-read
        self.assertIn("mcp__jira__add_comment", tools)     # MCP for internal-comment
        self.assertNotIn("mcp__jira__get_issue", tools)    # issue-read not granted here

    def test_identity_lock_prepends_override(self):
        out = with_identity_lock("# Support Engineer\nYou are the N2...")
        self.assertTrue(out.startswith("⚠️ RUNTIME IDENTITY LOCK"))
        self.assertIn("do NOT orchestrate", out)
        self.assertIn("# Support Engineer", out)          # the resolved role still follows

    def test_build_argv_passes_mcp_config(self):
        argv = build_cli_argv(system_prompt_file="/tmp/sp.md", model="m", allowed_tools="Read",
                              mcp_config_path="/tmp/mcp.json")
        self.assertEqual(argv[argv.index("--mcp-config") + 1], "/tmp/mcp.json")

    def test_parse_stream_collects_tools_text_and_metrics(self):
        # shaped exactly like the real CLI output (tool_use ids + a rich result event)
        stream = "\n".join([
            '{"type":"system","subtype":"init"}',
            '{"type":"assistant","message":{"content":['
            '{"type":"text","text":"looking"},'
            '{"type":"tool_use","id":"t1","name":"Read","input":{"path":"a.py"}},'
            '{"type":"tool_use","id":"t2","name":"Grep","input":{}}]}}',
            'not-json-skip-me',
            '{"type":"result","subtype":"success","is_error":false,"result":"final diagnosis",'
            '"total_cost_usd":0.25,"num_turns":8,"duration_ms":36483,"ttft_ms":4026,'
            '"usage":{"input_tokens":3085,"output_tokens":2394,"cache_read_input_tokens":94658}}',
        ])
        text, usage, actions = parse_cli_stream(stream)
        self.assertEqual(text, "final diagnosis")
        self.assertEqual(usage["total_cost_usd"], 0.25)
        self.assertEqual((usage["num_turns"], usage["duration_ms"], usage["ttft_ms"]), (8, 36483, 4026))
        self.assertEqual(usage["cache_read_input_tokens"], 94658)
        self.assertEqual(actions, [("Read", "code-read", False), ("Grep", "code-read", False)])

    def test_parse_stream_marks_denied_tool_as_gated(self):
        stream = "\n".join([
            '{"type":"assistant","message":{"content":'
            '[{"type":"tool_use","id":"bash1","name":"Bash","input":{"command":"ls"}}]}}',
            '{"type":"assistant","message":{"content":'
            '[{"type":"tool_use","id":"read1","name":"Read","input":{}}]}}',
            '{"type":"result","result":"ok","permission_denials":[{"tool_name":"Bash",'
            '"tool_use_id":"bash1","tool_input":{}}]}',
        ])
        _, _, actions = parse_cli_stream(stream)
        # Bash was refused (not in allowedTools) → gated=True; Read ran → gated=False
        self.assertEqual(actions, [("Bash", "code-write", True), ("Read", "code-read", False)])



class CliArgumentSizeTests(unittest.TestCase):
    """Linux caps one argument at 128 KiB (MAX_ARG_STRLEN): a system prompt or a task past it made
    the claude CLI fail to start. Neither travels in the argv any more — the system prompt goes in
    a file, the task on stdin."""

    def test_a_prompt_past_the_argument_limit_reaches_the_cli(self):
        import os
        import shutil
        import stat
        import tempfile
        from cortex_runtime.agent_client import ClaudeCodeCliClient

        tmp = Path(tempfile.mkdtemp(prefix="cortex-cli-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        seen = tmp / "seen.json"
        fake = tmp / "claude"
        fake.write_text(f"""#!{sys.executable}
import json, sys
argv = sys.argv[1:]
system = open(argv[argv.index("--append-system-prompt-file") + 1], encoding="utf-8").read()
json.dump({{"longest_arg": max(map(len, argv)), "system": len(system), "system_tail": system[-5:],
           "task": len(sys.stdin.read()), "file": argv[argv.index("--append-system-prompt-file") + 1]}},
          open({str(seen)!r}, "w"))
print(json.dumps({{"type": "result", "result": "done", "usage": {{}}}}))
""", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        client = ClaudeCodeCliClient(cli=str(fake), root=tmp, timeout=20)   # a task left unsent: fails, not hangs
        turn = client.propose("S" * 300_000 + "-END-", [{"role": "input", "content": "T" * 300_000}])
        got = json.loads(seen.read_text(encoding="utf-8"))
        self.assertEqual(turn.final_text, "done")
        self.assertLess(got["longest_arg"], 4096)
        self.assertEqual((got["system_tail"], got["task"]), ("-END-", 300_000))
        self.assertGreater(got["system"], 300_000)
        self.assertFalse(os.path.exists(got["file"]), "the system prompt file outlived the run")

    def test_a_cli_that_cannot_start_says_so(self):
        import shutil
        import tempfile
        from cortex_runtime.agent_client import ClaudeCodeCliClient

        tmp = Path(tempfile.mkdtemp(prefix="cortex-cli-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        fake = tmp / "claude"
        fake.write_text("#!/nonexistent/interpreter\n", encoding="utf-8")
        fake.chmod(0o755)
        client = ClaudeCodeCliClient(cli=str(fake), root=tmp)
        with self.assertRaisesRegex(RuntimeError, "claude CLI could not be started"):
            client.propose("s", [{"role": "input", "content": "t"}])


if __name__ == "__main__":
    unittest.main()
