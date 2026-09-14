# Monsters Loose — narrative animatic / 02

Watch and annotate at http://127.0.0.1:8742/animatic/notes-narrative.html .
This page uses the same saved notes, master-time positions and local dictation
as the original listening page. The scene selector seeks without starting playback.

The MP4 is a native Blender VSE render at 1280×720, 24 fps, 5,290 frames.
The editable project is `MonstersLoose-narrative-animatic-v02.blend`.
All original lyric timing strips, measured vocal meters, beat ticks and locked
master audio remain in the project. Narrative text is native editable text,
and scene backgrounds are native color strips.

Fifteen broad scenes contain 28 short narrative cards. These are proposed
groupings of the user's approximately positioned notes, not a shot list.
Color identifies a setting or story phase; returning settings can reuse a color.
The narrative follows the user's delayed creature reveals, scientist reveal,
escape sequence, and relaxed return-to-nature ending. Open choices are retained
as possibilities. Detailed camera choices and creature designs are not locked.

Source: `narrative-v02-source-notes.json`, a snapshot of revision 46 containing
40 notes. The active source notes were not edited or marked addressed.
The condensed outline is in `narrative-v02.md`; timed scene/card data is in
`narrative-v02.json`. The repeated-play correction, early-five correction and
un/until vocalization interpretation remain pending in the lyric timing pass.

Rebuild with Blender's background Python runner on `build-narrative.py`, adding
`-- --render` to render the MP4. Run `prepare-narrative-review.py` with ordinary
Python to refresh the generated review page from the existing notes template.
The render script starts from lyric v01; it does not overwrite that original.

Native validation: all 360 word strips and the source audio properties match
v01. All 15 background ranges and both lines of all 28 caption cards provide
continuous coverage from frame 1 through frame 5,290. See
`narrative-native-validation.json`. Six preview frames were rendered, with
visual checks of the tour, dense showdown lyrics and tentative swamp reveal.
