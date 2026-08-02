"""Compile the Bitwig extension without installing a JDK.

Bitwig ships a JRE but no compiler, and a full JDK is ~196 MB for one small
jar. The Eclipse batch compiler is a 3 MB jar that runs *on* a JRE, so the
whole toolchain is Bitwig's own java.exe plus ecj.

The API classes are not downloaded either — all 395 of them live inside
Bitwig's own `bin/bitwig.jar`, so that is the classpath. This means the
extension is always compiled against the installed Bitwig rather than a
version fetched from somewhere else.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from ...core.paths import RUNTIME_ROOT

HERE = Path(__file__).resolve().parent
SRC = HERE / "extension"
ECJ = RUNTIME_ROOT / "tools" / "ecj-3.46.0.jar"

DEFINITION = "amtw.AmtwHarmonyExtensionDefinition"
SERVICE = "META-INF/services/com.bitwig.extension.ExtensionDefinition"

BITWIG_DIRS = [
    Path(r"C:\Program Files\Bitwig Studio"),
    Path(r"C:\Program Files (x86)\Bitwig Studio"),
]


def find_bitwig() -> Path | None:
    env = os.environ.get("BITWIG_HOME")
    if env and Path(env).exists():
        return Path(env)
    for d in BITWIG_DIRS:
        if (d / "bin" / "bitwig.jar").exists():
            return d
    return None


def extensions_dir() -> Path:
    docs = Path.home() / "Documents" / "Bitwig Studio" / "Extensions"
    if docs.exists():
        return docs
    one = Path.home() / "OneDrive" / "Documents" / "Bitwig Studio" / "Extensions"
    return one if one.exists() else docs


def build(out: Path, log=print) -> Path:
    bw = find_bitwig()
    if not bw:
        raise SystemExit("Bitwig Studio not found — set BITWIG_HOME")
    java = bw / "jre" / "bin" / "java.exe"
    api = bw / "bin" / "bitwig.jar"
    if not java.exists():
        raise SystemExit(f"no java.exe in {java.parent}")
    if not ECJ.exists():
        raise SystemExit(f"ecj not found at {ECJ} — see docs/bitwig-bridge.md")

    classes = out.parent / "_classes"
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir(parents=True)

    # The API classes have to be unpacked to a DIRECTORY, not handed over as a
    # jar. Bitwig's bundled JRE is jlink-trimmed to 21 modules with no
    # jdk.zipfs, so ecj cannot mount a jar as a filesystem and dies with
    # "No provider for uri jar:file:...". Unpacking costs a second and removes
    # the whole problem.
    apidir = out.parent / "_api"
    if not (apidir / "com" / "bitwig" / "extension").exists():
        if apidir.exists():
            shutil.rmtree(apidir)
        apidir.mkdir(parents=True)
        with zipfile.ZipFile(api) as z:
            members = [n for n in z.namelist()
                       if n.startswith("com/bitwig/extension/") and n.endswith(".class")]
            z.extractall(apidir, members)
        log(f"  unpacked {len(members)} API classes from {api.name}")

    sources = sorted(str(p) for p in SRC.glob("*.java"))
    log(f"  compiling {len(sources)} source file(s)")
    # -source/-target 17 rather than --release: --release needs the JDK's
    # ct.sym, which a JRE does not ship. Bitwig's own API classes are Java 8
    # bytecode, so 17 is conservative and loads fine on its Java 25 runtime.
    cmd = [str(java), "-jar", str(ECJ), "-nowarn", "-source", "17", "-target", "17",
           "-cp", str(apidir), "-d", str(classes), *sources]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("compile failed")

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(classes.rglob("*.class")):
            z.write(p, p.relative_to(classes).as_posix())
        # Bitwig finds the extension through the standard ServiceLoader file
        z.writestr(SERVICE, DEFINITION + "\n")
    shutil.rmtree(classes, ignore_errors=True)
    log(f"  built {out.name} ({out.stat().st_size // 1024} KB)")
    return out
