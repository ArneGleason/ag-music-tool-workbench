import bpy
print('CURRENT',bpy.context.window,bpy.context.screen.name if bpy.context.screen else None)
for a in bpy.context.screen.areas:
 if a.type=='VIEW_3D':
  a.type='SEQUENCE_EDITOR'
  print('AFTER',a.type,[(sp.type) for sp in a.spaces])
print('WORKSPACES',[w.name for w in bpy.data.workspaces])
