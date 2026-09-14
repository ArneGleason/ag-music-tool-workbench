import bpy,pathlib
s=bpy.context.scene
s.frame_set(round(116*24)+1)
s.render.image_settings.media_type='IMAGE';s.render.image_settings.file_format='PNG';s.render.filepath=str(pathlib.Path(bpy.data.filepath).parent/'preview-dense.png')
bpy.ops.render.render(write_still=True)
print('VIEW',[(a.type,getattr(a.spaces.active,'view_type',None)) for a in bpy.context.screen.areas])
print('FONT',[(f.name,bool(f.packed_file)) for f in bpy.data.fonts if f.filepath])
