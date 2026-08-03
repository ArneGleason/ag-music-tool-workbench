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
import queue
import socket
import sys
import threading
import time
import traceback

from . import osc

RECV_PORT = 8732        # the extension sends here
SEND_PORT = 8733        # where the extension listens, if it got its first choice
SEND_PORT_TRIES = 10    # ...and the range it falls back through
HOST = "127.0.0.1"

PPQ = 480               # analysis tick resolution


def _compact(obj) -> str:
    """JSON with no spaces.

    The extension parses this with a regex rather than a JSON library, and the
    default json.dumps separators put a space after every colon. The pattern
    did not allow for that, matched nothing, and every write produced a blank
    clip. The extension tolerates whitespace now, but sending the compact form
    keeps the payload small and the two ends obviously in step.
    """
    return json.dumps(obj, separators=(",", ":"))


HELP = """
commands (type and press Enter):
  r          reduce the selected clip to a line, into a new clip
  a          analyse - name the chords in the selected clip
  p          pull the selected clip from Bitwig now
  m <mode>   set the line: smooth | top | bottom
  o <where>  where results go: file | inplace | newtrack | launcher
  t          write ONE test note into the selected clip and report back
  s          status
  q          quit
"""


class Bridge:
    def __init__(self, log=print):
        self.log = log
        self.notes: list[tuple[float, float, int, int]] = []
        self.step_size = 0.25
        self.clip_seen = False
        self.mode = "smooth"
        self.packets = 0                    # anything at all from the extension
        self.reply_port: int | None = None  # learned from the clip payload
        self.output = "file"               # file | inplace | newtrack | launcher
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._cmds: queue.Queue[str] = queue.Queue()

    # -- talking back -------------------------------------------------------

    def send(self, address: str, *args) -> None:
        """Send to the extension, sweeping the port range until it identifies itself.

        Bitwig's OscServer cannot be closed, so an extension instance holds its
        port for the life of the Bitwig process. Removing and re-adding the
        controller therefore lands the new instance on 8734, 8735 and so on.
        Until a clip arrives telling us which, every candidate gets the message
        — ten localhost datagrams, and it means the bridge works without the
        user having to know any of that happened.
        """
        try:
            data = osc.encode(address, *args)
            if self.reply_port:
                self._out.sendto(data, (HOST, self.reply_port))
            else:
                for i in range(SEND_PORT_TRIES):
                    self._out.sendto(data, (HOST, SEND_PORT + i))
        except OSError as e:
            self.log(f"  send failed: {e}")

    def notify(self, text: str) -> None:
        """A popup inside Bitwig, mirrored to this console.

        Mirroring matters more than it looks: if the extension is not loaded,
        or the popup is missed, the terminal is the only place the answer
        appears. Silence here reads as "nothing happened" when the truth is
        "it answered, somewhere you were not looking".
        """
        self.log(f"  > {text}")
        self.send("/amtw/notify", text[:200])

    # -- receiving ----------------------------------------------------------

    def on_clip(self, payload: str) -> None:
        data = json.loads(payload)
        port = data.get("inPort")
        if isinstance(port, int) and port > 0 and port != self.reply_port:
            self.reply_port = port
            if port != SEND_PORT:
                self.log(f"  extension is listening on {port} "
                         f"(not {SEND_PORT}) - replies will go there")
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

        if self.output == "file":
            path = self._write_midi(picks, f"{mode} line")
            self.log(f"  wrote {path}")
            self._reveal(path)
        elif self.output == "newtrack":
            path = self._write_midi(picks, f"{mode} line")
            self.log(f"  wrote {path}")
            self.send("/amtw/insertFile", str(path))
        elif self.output == "inplace":
            self.send("/amtw/inPlace", _compact(out))
        else:
            self.send("/amtw/newClip", f"{mode} line",
                      max(1, int(round(length_beats))), _compact(out))

        pct = (100 * stats["steps_or_less"] / stats["total_moves"]
               if stats["total_moves"] else 100)
        self.notify(f"{mode} line: {len(picks)} notes, mean leap "
                    f"{stats['mean_leap']} semitones, {pct:.0f}% stepwise")

    def _reveal(self, path) -> None:
        """Show the file in Explorer, selected and ready to drag into Bitwig.

        Bitwig's clip clipboard is a private format, so there is nothing to
        paste into a web page. Dragging a .mid file IS the cross-application
        convention that works, and unlike every write-back route tried so far
        it puts the user in control of exactly which track and which bar the
        notes land on. Popping the folder open makes that one drag instead of
        a hunt through Explorer.
        """
        import subprocess

        try:
            subprocess.Popen(["explorer", "/select,", str(path)])
            self.log("  Explorer opened - drag the file into Bitwig where you want it")
        except OSError as e:
            self.log(f"  (could not open Explorer: {e})")

    def _write_midi(self, picks, name: str):
        """A one-track MIDI file for Bitwig to import as a new track.

        Positions are kept exactly as they came out of the clip, so dropping
        the file in lines the notes up with the bars they were reduced from --
        assuming Bitwig places an inserted file at the start of the timeline.
        That is the one part of this route I cannot verify from here.
        """
        import mido

        from ...core.paths import OUTPUT_DIR

        out_dir = OUTPUT_DIR / "bitwig"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{name.replace(' ', '_')}.mid"

        mf = mido.MidiFile(type=1, ticks_per_beat=PPQ)
        tr = mido.MidiTrack()
        tr.append(mido.MetaMessage("track_name", name=name, time=0))
        events = []
        for p in picks:
            events.append((int(p.start), 1, p.pitch, p.velocity))
            events.append((int(p.end), 0, p.pitch, 0))
        events.sort(key=lambda e: (e[0], e[1]))     # offs before ons at a tick
        prev = 0
        for at, on, pitch, vel in events:
            tr.append(mido.Message("note_on" if on else "note_off", note=pitch,
                                   velocity=vel, time=max(0, at - prev)))
            prev = at
        mf.tracks.append(tr)
        mf.save(str(path))
        return path

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
        # ASCII only. This string is printed to a Windows console as well as
        # sent to Bitwig, and cp1252 turns an arrow into "a-with-circumflex,
        # dagger, right-arrow" -- the same class of bug that stopped amtw.ps1
        # parsing. Bitwig would render it fine; the terminal is the constraint.
        self.notify(" -> ".join(seq[:6])
                    + (" ..." if len(seq) > 6 else "")
                    + f"  |  fits: {keys}")
        self.log(f"  analyse: {len(seq)} chords {seq}, fits {fits}")

    # -- typed commands -----------------------------------------------------

    def _read_stdin(self) -> None:
        """Commands typed here rather than pressed in Bitwig.

        The extension streams the selected clip continuously, so the bridge
        already knows what you are looking at — a trigger is all that is
        missing, and it does not have to come from inside the DAW. This avoids
        hunting for a controller panel, and changing it needs no recompile.
        """
        for line in sys.stdin:
            self._cmds.put(line.strip())

    def pull(self, timeout: float = 2.0) -> bool:
        """Ask Bitwig to send the selected clip, and wait for it.

        The extension only sends when its note-step observer fires, which is on
        note CHANGES -- selecting a different clip does not necessarily count.
        So "select a clip, press r" found nothing while the clip was plainly
        there. /amtw/resend exists for this and the extension already handles
        it, so the pull happens automatically rather than needing a rebuild.
        """
        self.send("/amtw/resend")
        deadline = time.monotonic() + timeout
        before = self.notes
        while time.monotonic() < deadline:
            try:
                self._sock.settimeout(max(0.05, deadline - time.monotonic()))
                data, _ = self._sock.recvfrom(262144)
            except socket.timeout:
                break
            except OSError:
                break
            self.packets += 1
            try:
                address, args = osc.decode(data)
                if address == "/amtw/clip":
                    self.on_clip(*args)
                    if self.notes is not before:
                        self._sock.settimeout(0.3)
                        return True
            except Exception as e:  # noqa: BLE001
                # This used to escape pull() and kill the process. A bad packet
                # is a thing to report, never a reason for the bridge to vanish
                # while the user is mid-session.
                self.log(f"  bad packet during pull ({len(data)} bytes): {e}")
                continue
        self._sock.settimeout(0.3)
        return bool(self.notes)

    def _need_notes(self) -> bool:
        """True when we have notes, pulling first if we do not."""
        if self.notes:
            return True
        self.log("  no clip held - asking Bitwig for the selection ...")
        if self.pull():
            return True
        if self.packets == 0:
            self.log("  nothing has EVER arrived from the extension.")
            self.log("  check: is 'AMTW Harmony Bridge' enabled in")
            self.log("         Settings > Controllers, and does Bitwig's")
            self.log("         controller console show 'amtw harmony bridge ready'?")
        else:
            self.log("  the extension is talking, but the selected clip is empty")
            self.log("  (a clip must be SELECTED, not just the track)")
        return False

    def _do_command(self, cmd: str) -> bool:
        """-> False to stop."""
        if not cmd:
            return True
        head, _, rest = cmd.partition(" ")
        head = head.lower()
        if head in ("q", "quit", "exit"):
            return False
        if head in ("?", "h", "help"):
            self.log(HELP)
        elif head in ("o", "out", "output"):
            want = rest.strip().lower()
            if want in ("file", "newtrack", "inplace", "launcher"):
                self.output = want
                self.log(f"  output = {self.output}")
            else:
                self.log("  output must be file, inplace, newtrack or launcher")
        elif head in ("m", "mode"):
            want = rest.strip().lower()
            if want in ("smooth", "top", "bottom"):
                self.mode = want
                self.log(f"  mode = {self.mode}")
            else:
                self.log("  mode must be smooth, top or bottom")
        elif head in ("t", "test"):
            self.log("  asking Bitwig to write ONE note into the selected clip ...")
            self.send("/amtw/testNote")
        elif head in ("p", "pull"):
            if self.pull():
                self.log(f"  pulled {len(self.notes)} notes")
            else:
                self._need_notes()
        elif head in ("r", "reduce"):
            if self._need_notes():
                self.on_reduce(self.mode)
        elif head in ("a", "analyse", "analyze"):
            if self._need_notes():
                self.on_analyse()
        elif head in ("s", "status"):
            self.log(f"  mode={self.mode}  notes held={len(self.notes)}"
                     f"  out={self.output}  clip seen={self.clip_seen}"
                     f"  packets from extension={self.packets}")
        else:
            self.log(f"  unknown command {cmd!r} - type ? for help")
        return True

    # -- loop ---------------------------------------------------------------

    def serve(self) -> int:
        try:
            self._sock.bind((HOST, RECV_PORT))
        except OSError as e:
            # Almost always a bridge already running, often minimised and
            # forgotten. A traceback here reads as "the tool is broken" when
            # the truth is "it is already working, in the other window".
            self.log(f"cannot listen on {HOST}:{RECV_PORT}: {e}")
            self.log("A bridge is probably already running - use that window,")
            self.log(f"or stop it and retry, or: amtw bitwig-bridge --port {RECV_PORT + 10}")
            return 1
        self._sock.settimeout(0.3)
        self.log(f"bridge listening on {HOST}:{RECV_PORT}, "
                 f"replying to {SEND_PORT}")
        self.log("select a clip in Bitwig - the extension streams it here")
        self.log(HELP)
        threading.Thread(target=self._read_stdin, daemon=True).start()

        handlers = {
            "/amtw/clip": self.on_clip,
            "/amtw/reduce": self.on_reduce,
            "/amtw/analyse": self.on_analyse,
        }
        # Nothing below is allowed to end the process except q or Ctrl+C. A
        # bridge that disappears mid-session looks like a crash in Bitwig and
        # tells the user nothing; a bridge that prints a traceback and keeps
        # listening tells them everything.
        try:
            while True:
                try:
                    while not self._cmds.empty():
                        if not self._do_command(self._cmds.get()):
                            self.log("stopped.")
                            return 0
                    try:
                        data, _ = self._sock.recvfrom(262144)
                    except socket.timeout:
                        continue
                    self.packets += 1
                    address, args = osc.decode(data)
                    fn = handlers.get(address)
                    if not fn:
                        self.log(f"  unhandled {address}")
                        continue
                    fn(*args) if args else fn()
                except KeyboardInterrupt:
                    raise
                except Exception:  # noqa: BLE001
                    self.log("  --- error, bridge still running ---")
                    for line in traceback.format_exc().rstrip().splitlines():
                        self.log("  " + line)
        except KeyboardInterrupt:
            self.log("\nstopped.")
        finally:
            self._sock.close()
            self._out.close()
        return 0
