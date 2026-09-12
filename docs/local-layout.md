# Canonical layout and recovery

Established 2026-09-12 after discovering Windows packaged-app redirection of
LOCALAPPDATA. The complete runtime existed in Claude's LocalCache; the ordinary
AppData location held a second, incomplete harmony runtime. Treat missing models
as a path-resolution question before downloading or rebuilding anything.

## This machine

| Purpose | Canonical location |
|---|---|
| Code, findings, tools, listening notes | `C:\code\github\ag-music-tool-workbench` |
| Shared runtime, engines, models, jobs | `C:\audio\shared\amtw-runtime` |
| Per-user runtime pointer | `%USERPROFILE%\.config\amtw\runtime.json` |
| Rollback copy of incomplete runtime | `C:\audio\archives\amtw-partial-runtime-2026-09-12` |
| Earlier repository/audio archive | `C:\Users\arneg\OneDrive\Documents\VocalStemRegen` |

The repository remote is `https://github.com/ArneGleason/ag-music-tool-workbench`.
The OneDrive repository has no unique code commits: its initial commit is an
ancestor of the canonical repository. Its ground-truth label JSON is equivalent
apart from formatting. It still has historical rendered audio and is retained
as an archive; its launchers and agent notice redirect to the canonical repo.

Both old runtime locations are **directory junctions**, not duplicate copies:

- `%USERPROFILE%\AppData\Local\VocalStemRegen`
- `%USERPROFILE%\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\VocalStemRegen`

Keep these compatibility links: virtualenv entry points and older projects
contain absolute paths. Do not recursively delete a junction as if it were an
independent stale folder. The runtime was moved on the same drive; no model
re-download or virtualenv rebuild was needed. Other local projects may point to
its model files directly, or use AMTW_RUNTIME. Do not merge incompatible engine
environments into one Python installation.

Before migration the complete runtime occupied about 48.8 GB logical file size:
27.3 GB venvs, 15.6 GB third-party trees, 4.85 GB models and 0.93 GB HF cache,
plus soundfonts/tools. The retained partial runtime is about 5.9 GB, including
the redundant 341 MB Apollo download and incomplete second MSST install.
It is inactive rollback material, not a second active installation. Its jobs
and additional tools were copied into the canonical runtime before switching.
No rollback data has been deleted or claimed as reclaimed disk space.

## Starting and stopping

Double-click `Workbench.cmd` in the canonical repo; it resolves the runtime
through `amtw.ps1` and `scripts/resolve_runtime.ps1`. The canonical workbench is
`http://127.0.0.1:8730/`. Start the live Bitwig bridge from its Bitwig tool group
when needed. The bridge uses localhost 8766/8767 and reconnects automatically.
One workbench and one bridge were left running after migration; logs are in
the shared runtime's `logs/` directory. Windows venv launches have a wrapper
and a child Python process; that pair is one server, not two.

## Another machine

1. Clone the GitHub repository outside cloud-synced folders.
2. Choose a runtime directory outside the repo. Write
   `%USERPROFILE%\.config\amtw\runtime.json` with
   `{"runtime_root":"D:\\AudioTools\\runtime"}` (use that machine's path).
3. Use `scripts/setup_harmony.ps1` for the lightweight bridge/MIDI tools, or
   `scripts/setup_runtime.ps1` for the complete pipeline. Both use the same
   resolver. `AMTW_RUNTIME` and legacy `VSR_RUNTIME` override the pointer.
4. Run `amtw.ps1 doctor`. Check `docs/runtime-resources.json` for actual model
   hashes and third-party revisions. `docs/runtime-environments/` records the
   working package versions; it is an inventory, not a cross-platform lockfile.
5. Install the Bitwig controller via the workbench. The local Codex MCP plugin
   points to this checkout's `amtw/tools/bitwiglive/mcp_server.py`; regenerate
   its Python/repo paths on the new machine rather than copying absolute paths.

Do not copy virtualenv folders to a different machine as a substitute for setup.
Copy/cache verified model files if available, or download from recorded sources.
Audio, weights, environments and generated renders stay out of Git. Source
code, model/configuration provenance and listening verdicts belong in Git.
Archived listening notes retain their original file paths as provenance; those
paths do not imply the audio is shipped in the repository.

## Pending music work

MonstersUndone's cleaned MIDI and groove map were accepted by ear. The user
requested a short lead-vocal cleanup audition before full-song processing,
then paused it for this consolidation. No audition variants have been rendered
and no replacement vocal has been inserted. Continue with the recovered Apollo
runtime and `docs/using-the-ab-tool.md`; compare short contrasting sections,
keep the original, and wait for a listening verdict before a full pass.
