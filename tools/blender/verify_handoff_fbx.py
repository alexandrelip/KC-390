import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"D:\down\kc390tudo\FBX\KC-390_animado.fbx")

animated = 0
fcurves = 0
keys = 0
for obj in bpy.data.objects:
    ad = obj.animation_data
    action = ad.action if ad else None
    if not action and ad:
        for track in ad.nla_tracks:
            for strip in track.strips:
                if strip.action:
                    action = strip.action
                    break
    if not action:
        continue
    animated += 1
    fcurves += len(action.fcurves)
    keys += sum(len(fc.keyframe_points) for fc in action.fcurves)

missing_img = [i.name for i in bpy.data.images if i.source == "FILE" and not i.has_data]
print(f"KC390_VERIFY: objetos={len(bpy.data.objects)} animados={animated} fcurves={fcurves} keys={keys}")
print(f"KC390_VERIFY: imagens={len(bpy.data.images)} sem_dados={len(missing_img)} {missing_img[:5]}")
