"""Local framed-JSON broker. No HTTP/CORS surface and no third-party runtime.

Only one controller can own the connection. Commands time out without replay:
an uncertain write must be resolved by reading Bitwig, never blindly retried.
"""
from __future__ import annotations
import argparse
import json
import socket
import socketserver
import struct
import threading
import uuid

HOST = "127.0.0.1"
CONTROLLER_PORT, CLIENT_PORT = 8766, 8767
MAX_FRAME = 1024 * 1024

def read_exact(sock, length):
    chunks = bytearray()
    while len(chunks) < length:
        part = sock.recv(length - len(chunks))
        if not part:
            raise ConnectionError("Connection closed")
        chunks.extend(part)
    return bytes(chunks)

def receive(sock):
    size, = struct.unpack(">I", read_exact(sock, 4))
    if not 0 < size <= MAX_FRAME:
        raise ValueError("Invalid frame size")
    return json.loads(read_exact(sock, size))

def send(sock, value):
    body = json.dumps(value, ensure_ascii=True, allow_nan=False).encode("utf-8")
    if len(body) > MAX_FRAME:
        raise ValueError("Frame too large")
    sock.sendall(struct.pack(">I", len(body)) + body)

def request(op="snapshot", **params):
    message = {"id": str(uuid.uuid4()), "op": op, **params}
    with socket.create_connection((HOST, CLIENT_PORT), timeout=8) as sock:
        send(sock, message)
        result = receive(sock)
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["result"]

class Broker:
    def __init__(self):
        self.controller = None
        self.lock = threading.Lock()
        self.pending = {}

    def call(self, message):
        if not isinstance(message, dict) or message.get("op") not in {"snapshot", "set_track"}:
            return {"error": "Unsupported request"}
        # A lock covers send/register but not the wait, allowing the receiver
        # to deliver replies. Bitwig itself serializes compare-before-write.
        event = threading.Event()
        ident = message.get("id")
        if not isinstance(ident, str) or len(ident) > 100:
            return {"error": "Invalid request id"}
        with self.lock:
            if self.controller is None:
                return {"id": ident, "error": "Bitwig is disconnected. Enable Live Project Bridge in Controllers."}
            if ident in self.pending:
                return {"id": ident, "error": "Request already pending"}
            slot = [event, None]
            self.pending[ident] = slot
            try:
                send(self.controller, message)
            except OSError as exc:
                del self.pending[ident]
                return {"id": ident, "error": str(exc)}
        event.wait(5)
        with self.lock:
            self.pending.pop(ident, None)
        return slot[1] or {"id": ident, "error": "No readback received; outcome unknown. Read state before any retry."}

def serve():
    broker = Broker()
    class Controller(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.settimeout(5)
            try:
                hello = receive(self.request)
                if hello.get("hello") != "amtw-live":
                    return
                with broker.lock:
                    if broker.controller is not None:
                        return
                    broker.controller = self.request
                self.request.settimeout(None)
                print("Bitwig connected: " + hello.get("session", "?"), flush=True)
                while True:
                    response = receive(self.request)
                    with broker.lock:
                        slot = broker.pending.get(response.get("id"))
                        if slot:
                            slot[1] = response
                            slot[0].set()
            except (OSError, ValueError, ConnectionError) as exc:
                print("Controller connection ended: " + str(exc), flush=True)
            finally:
                with broker.lock:
                    if broker.controller is self.request:
                        broker.controller = None
                        for ident, slot in broker.pending.items():
                            slot[1] = {"id": ident, "error": "Controller disconnected; outcome unknown. Read before retrying."}
                            slot[0].set()
    class Client(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.settimeout(8)
            try:
                send(self.request, broker.call(receive(self.request)))
            except (OSError, ValueError, ConnectionError):
                pass
    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = False
    with Server((HOST, CONTROLLER_PORT), Controller) as controllers, Server((HOST, CLIENT_PORT), Client) as clients:
        threading.Thread(target=controllers.serve_forever, daemon=True).start()
        print("AMTW live bridge: localhost 8766 (Bitwig), 8767 (clients)", flush=True)
        clients.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["serve", "snapshot"])
    args = parser.parse_args()
    if args.mode == "serve":
        serve()
    else:
        print(json.dumps(request(), indent=2))
