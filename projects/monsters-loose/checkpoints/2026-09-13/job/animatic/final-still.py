import bpy,pathlib
s=bpy.context.scene;s.name='Monsters Loose - lyric timing';bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
s.frame_set(301);r=s.render;r.image_settings.media_type='IMAGE';r.image_settings.file_format='PNG';r.filepath=str(pathlib.Path(bpy.data.filepath).parent/'preview-12.5.png');bpy.ops.render.render(write_still=True)
