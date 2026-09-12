"""Live project bridge exposed on the bench as well as through MCP."""
from pathlib import Path
import json
import shutil
from ...spec import Tool, Field

def install(args):
    from ..bitwig.build import extensions_dir
    destination = Path(args.dest) if args.dest else extensions_dir().parent / "Controller Scripts" / "AMTW Live"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).with_name("Live.control.js"), destination / "Live.control.js")
    print(f"Installed: {destination / 'Live.control.js'}")
    print("Bitwig > Settings > Controllers > Add Controller > AG Music Tool Workbench > Live Project Bridge")
    return 0

def serve(args):
    from .service import serve
    serve()
    return 0

def snapshot(args):
    from .service import request
    print(json.dumps(request(), indent=2))
    return 0

def edit(args):
    from .service import request
    state = request()
    value = args.value
    if args.field in {"mute", "solo"}:
        if value.lower() not in {"true", "false"}:
            raise ValueError("Use true or false for mute/solo")
        value = value.lower() == "true"
    elif args.field in {"volume", "pan"}:
        value = float(value)
    # The typed expected name identifies what the user meant, even if tracks
    # moved between opening this form and pressing Run. The revision then
    # guards the small interval between our read and the controller's write.
    result = request("set_track", session=state["session"], revision=state["revision"],
                     index=args.index, expectedName=args.expected_name, field=args.field, value=value)
    print(json.dumps(result, indent=2))
    return 0 if result["verified"] else 1

TOOLS = [
    Tool(name="bitwig-live-install", title="Install live project bridge", group="Bitwig", order=30,
         blurb="Install the lightweight controller for live project reads and targeted track edits.", run=install,
         note="Enable Live Project Bridge in Bitwig Controllers once, then start the live bridge below. This is separate from Harmony Bridge.",
         fields=[Field("dest", "Controller script folder", "dir", flag="--dest", advanced=True)]),
    Tool(name="bitwig-live", title="Start live project bridge", group="Bitwig", order=31,
         blurb="Keep a local connection open for the workbench and the Bitwig Live MCP plugin.", run=serve, background=True,
         note="Localhost only. Supports track name, mute, solo, volume and pan with stale-state rejection and readback. Does not yet edit notes, tempo ramps or audio clips."),
    Tool(name="bitwig-live-snapshot", title="Read live Bitwig project", group="Bitwig", order=32,
         blurb="Read current tracks, mixer values and transport without exporting the project.", run=snapshot,
         note="Start the live bridge and enable its controller first. Up to 64 tracks, including group children; volume and pan use normalized 0–1 values."),
    Tool(name="bitwig-live-edit", title="Edit a live track", group="Bitwig", order=33,
         blurb="Change one named track property and verify the result in Bitwig.", run=edit,
         note="Use the index and exact current name from Read live Bitwig project. Mute/solo: true or false. Volume/pan: normalized 0–1, not dB; pan 0.5 is center. A stale target is rejected. On an uncertain outcome, read before retrying.",
         fields=[Field("index", "Track index", "int", flag="--index", default=0),
                 Field("expected_name", "Exact current track name", flag="--expected-name", required=True),
                 Field("field", "Property", flag="--field", default="name", choices=["name", "mute", "solo", "volume", "pan"]),
                 Field("value", "New value", flag="--value", required=True)])
]
