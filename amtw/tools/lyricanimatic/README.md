# Blender lyric timing animatic

Use **Video / Build Blender lyric animatic** in the workbench. Select the
combined word timing JSON, the locked DAWproject export, and a new output folder.
Tick Render full-song video to export an MP4 as well as the editable .blend.

This follows Rivers of Mars' `tools/blender_comp.py` VSE approach. Blender is
the animation and rendering rig; no HTML/canvas renderer or baked lyric movie
is imported. The native TEXT/COLOR strips expose words, highlights, movement,
meters, beat pads and readouts. A measured static envelope image is created
inside Blender, saved alongside the project, and added as a reference strip.
The source image supplied by the user inspired the palette only; it is not
altered or included in the picture. Caption boxes and speech/thought bubbles
are deliberately deferred by the user's brief.

`prepare.py` uses the existing vevo2 environment's NumPy/soundfile to measure
frame-rate RMS and integrates DAWproject linear-in-beat BPM ramps analytically.
The builder currently targets an English 4/4 project at 24 fps / 1280x720.
Font: Barlow Semi Condensed SemiBold from the official Google Fonts repository;
font and OFL license are downloaded into the output directory and cached there.
No packages are installed. Blender is required separately (tested 5.2.1).

Frame 1 is master second zero. A word's acoustic seconds are preserved as custom
strip properties. Word highlights round to the closest frame; ±20.83 ms display
quantization is not an alignment correction. The movie uses ceil(duration*24)
frames, so its end can extend by less than one frame. The master starts at zero
and is never time-stretched. A fixed -60 to 0 dBFS range drives the RMS bars;
they are not peak or loudness/LUFS meters. Lead amplitude drives the overview.

Whole phrases preview by up to 0.5 seconds and hold by up to 1 second, limited
by neighboring phrases. Overlapping candidate phrases share a page. This
preserves all acoustic word spans rather than cutting the preceding words to
make room for an early preview. Native text is measured with Blender's font
API, wrapped and centred. Upcoming words are muted, spoken words cream; a
growing red underline shows each word's independent interval. Selected words
receive restrained scale emphasis and every word a small entry lift.

`animatic-data.json` stores measured references, source paths and provisional
phrase data; `layout.json` stores presentation pages and word positions. Neither
overwrites the timing input. A wordless unresolved event is labelled as such,
not transcribed into invented words. The draft label and amber review cue remain
visible. These animations do not repair a mistaken acoustic endpoint.

`finish.py` reopens the file to activate Blender's saved editor space, selects
combined preview/timeline, packs the font and makes media paths relative. Keep
the output folder together: the .blend references its master and overview PNG.
The output filename currently uses the Monsters Loose title; this is an initial
project-specific tool, not a generic song package generator.
