"""Reopen once so Blender has activated the saved VSE space before setting its view."""
import bpy
s=bpy.context.scene
for a in bpy.context.screen.areas:
 if a.type=='SEQUENCE_EDITOR':a.spaces.active.view_type='SEQUENCER_PREVIEW'
for f in bpy.data.fonts:
 if f.filepath and not f.packed_file:
  try:f.pack()
  except RuntimeError:pass
bpy.ops.file.make_paths_relative()
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Saved VSE preview + timeline workspace and relative media paths.')
