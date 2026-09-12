"""Transport/protocol regression checks; no writes to a user's running DAW."""
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from amtw.tools.bitwiglive.service import Broker, receive

class LiveBridgeTests(unittest.TestCase):
    def test_fragmented_utf8_frame(self):
        a, b = socket.socketpair()
        value = {"name": "Koto — 弦", "id": "1"}
        payload = json.dumps(value, ensure_ascii=False).encode()
        data = struct.pack(">I", len(payload)) + payload
        def writer():
            with a:
                for byte in data:
                    a.sendall(bytes([byte]))
        t = threading.Thread(target=writer)
        t.start()
        with b:
            b.settimeout(2)
            self.assertEqual(receive(b), value)
        t.join()

    def test_oversized_frame_rejected_before_body(self):
        a, b = socket.socketpair()
        with a, b:
            a.sendall(struct.pack(">I", 2**30))
            with self.assertRaises(ValueError):
                receive(b)

    def test_disconnected_and_arbitrary_commands_rejected(self):
        b = Broker()
        self.assertIn("disconnected", b.call({"id": "1", "op": "snapshot"})["error"])
        self.assertIn("Unsupported", b.call({"id": "2", "op": "eval"})["error"])

    def test_mcp_lifecycle_and_bad_arguments(self):
        script = Path(__file__).resolve().parents[1] / "amtw/tools/bitwiglive/mcp_server.py"
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "bitwig_set_track", "arguments": {}}},
        ]
        result = subprocess.run([sys.executable, str(script)], input="\n".join(map(json.dumps, messages))+"\n",
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        replies = list(map(json.loads, result.stdout.splitlines()))
        self.assertEqual([r["id"] for r in replies], [1, 2, 3])
        self.assertEqual(len(replies[1]["result"]["tools"]), 2)
        self.assertTrue(replies[2]["result"]["isError"])

if __name__ == "__main__":
    unittest.main()
