"""The workbench end of the Bitwig bridge.

Topology, deliberately: the extension inside Bitwig is a transport with no
music theory in it. It reads the selected clip, writes notes, and shows
messages. Everything that knows what a chord is lives here, in the same Python
that `harm-read`, `harm-map` and `harm-reduce` already use — so there is one
implementation of the analysis rather than a Java twin that drifts from it.

The clip arrives as steps on a 1/16 grid. That is Bitwig's model, not ours, so
it is converted to ticks at the analysis ppq on the way in and back to steps on
the way out; nothing downstream needs to know Bitwig was involved.
"""
from __future__ import annotations

import json
import socket
import time

from . import osc

RECV_PORT = 8732        # the extension sends here
SEND_PORT = 8733        # the extension listens here
HOST = "127.0.0.1"

PPQ = 480               # analysis tick resolution


class Bridge:
    def __init__(self, log=print):
        self.log = log
        self.notes: list[tuple[float, float, int, int]] = []
        self.step_size = 0.25
        self.clip_seen = False
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # -- talking back -------------------------------------------------------

    def send(self, address: str, *args) -> None:
        try:
            self._out.sendto(osc.encode(address, *args), (HOST, SEND_PORT))
        except OSError as e:
            self.log(f"  send failed: {e}")

    def notify(self, text: str) -> None:
        """A popup inside Bitwig. Kept short — it is a heads-up, not a report."""
        self.send("/amtw/notify", text[:200])

    # -- receiving ----------------------------------------------------------

    def on_clip(self, payload: str) -> None:
        data = json.loads(payload)
        self.step_size = float(data.get("stepSize", 0.25))
        ticks_per_step = self.step_size * PPQ
        self.notes = [
            (n["x"] * ticks_per_step,
             (n["x"] + max(1.0, n["dur"] / self.step_size)) * ticks_per_step,
             int(n["y"]),
             max(1, min(127, int(round(n["vel"] * 127)))))
            for n in data.get("notes", [])
        ]
        self.clip_seen = True
        self.log(f"  clip: {len(self.notes)} notes")

    def on_reduce(self, mode: str) -> None:
        from ..harmony import reduce as RED

        if not self.notes:
            self.notify("AMTW: no notes — select a clip with chords first")
            return

        picks = RED.reduce_line(self.notes, mode=mode)
        stats = RED.describe(picks)
        if not picks:
            self.notify("AMTW: nothing to reduce")
            return

        ticks_per_step = self.step_size * PPQ
        out = [{"x": int(round(p.start / ticks_per_step)),
                "y": p.pitch,
                "vel": p.velocity,
                "dur": round((p.end - p.start) / ticks_per_step * self.step_size, 4)}
               for p in picks]
        length_beats = max(p.end for p in picks) / PPQ

        self.log(f"  reduce[{mode}]: {len(self.notes)} -> {len(picks)} notes, "
                 f"mean leap {stats['mean_leap']}")
        self.send("/amtw/newClip", f"{mode} line",
                  max(1, int(round(length_beats))), json.dumps(out))
        pct = (100 * stats["steps_or_less"] / stats["total_moves"]
               if stats["total_moves"] else 100)
        self.notify(f"{mode} line: {len(picks)} notes, mean leap "
                    f"{stats['mean_leap']} semitones, {pct:.0f}% stepwise")

    def on_analyse(self, _arg: str = "") -> None:
        """Name the chords in the clip, in order.

        Pooling every note in the clip into one pitch-class set and naming that
        produces things like "C9 +FA" — a set, not a chord, and useless. The
        clip is segmented the same way the reducer segments it, so what comes
        back is the progression.
        """
        from ..harmony import analysis as A
        from ..harmony import reduce as RED

        if not self.notes:
            self.notify("AMTW: no notes — select a clip first")
            return

        segs = RED.segments(self.notes)
        names = []
        for _, _, live in segs:
            pcs = {p % 12 for p, _ in live}
            bass = min(p for p, _ in live) % 12
            rs = A.readings(pcs, bass)
            names.append(rs[0].label(bass) if rs else "?")
        # collapse repeats: a chord held across two segments is one chord
        seq = [n for i, n in enumerate(names) if i == 0 or n != names[i - 1]]

        whole = {p % 12 for _, _, p, _ in self.notes}
        fits = A.key_fits(whole)
        keys = " ".join(fits) if fits else "no single major key"
        self.notify(f"{' → '.join(seq[:6])}"
                    + (" …" if len(seq) > 6 else "")
                    + f"  ·  fits: {keys}")
        self.log(f"  analyse: {len(seq)} chords {seq}, fits {fits}")

    # -- loop ---------------------------------------------------------------

    def serve(self) -> int:
        self._sock.bind((HOST, RECV_PORT))
        self._sock.settimeout(0.5)
        self.log(f"bridge listening on {HOST}:{RECV_PORT}, "
                 f"replying to {SEND_PORT}")
        self.log("waiting for Bitwig — select a clip and edit a note to wake it")
        handlers = {
            "/amtw/clip": self.on_clip,
            "/amtw/reduce": self.on_reduce,
            "/amtw/analyse": self.on_analyse,
        }
        try:
            while True:
                try:
                    data, _ = self._sock.recvfrom(262144)
                except socket.timeout:
                    continue
                try:
                    address, args = osc.decode(data)
                except Exception as e:  # noqa: BLE001
                    self.log(f"  bad packet: {e}")
                    continue
                fn = handlers.get(address)
                if not fn:
                    self.log(f"  unhandled {address}")
                    continue
                try:
                    fn(*args) if args else fn()
                except Exception as e:  # noqa: BLE001
                    self.log(f"  {address} failed: {e}")
                    self.notify(f"AMTW error: {e}")
        except KeyboardInterrupt:
            self.log("\nstopped.")
        finally:
            self._sock.close()
            self._out.close()
        return 0
