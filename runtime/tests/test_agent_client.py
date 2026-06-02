"""Tests for the Agent SDK adapter's pure translation surface — ADR-002 §3.3.

The live ``AnthropicAgentClient.propose`` needs the SDK + a key and is not exercised here;
``interpret_response`` and ``tool_schemas`` carry the SDK-agnostic logic and are tested in full.
"""

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
        argv = build_cli_argv("do it", system_prompt="you are X", model="claude-opus-4-8",
                              allowed_tools="Read,Grep")
        self.assertEqual(argv[:3], ["claude", "-p", "do it"])
        self.assertIn("--append-system-prompt", argv)
        self.assertIn("--allowedTools", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "Read,Grep")
        self.assertEqual(argv[argv.index("--model") + 1], "claude-opus-4-8")

    def test_build_argv_omits_empty_allowed_tools(self):
        argv = build_cli_argv("x", system_prompt="s", model="m", allowed_tools="")
        self.assertNotIn("--allowedTools", argv)

    def test_parse_result_extracts_text_and_usage(self):
        stdout = '{"result": "diagnosis here", "total_cost_usd": 0.012, ' \
                 '"usage": {"input_tokens": 100, "output_tokens": 50}}'
        text, usage = parse_cli_result(stdout)
        self.assertEqual(text, "diagnosis here")
        self.assertEqual(usage["total_cost_usd"], 0.012)
        self.assertEqual(usage["input_tokens"], 100)

    def test_build_argv_stream_json_adds_verbose(self):
        argv = build_cli_argv("x", system_prompt="s", model="m", allowed_tools="Read",
                              output_format="stream-json")
        self.assertIn("--verbose", argv)

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


if __name__ == "__main__":
    unittest.main()
