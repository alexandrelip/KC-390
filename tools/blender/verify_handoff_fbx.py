import bpy
import os
import sys
from pathlib import Path

ADDON_DIR = Path(bpy.utils.user_resource("SCRIPTS", path="addons")) / "io_scene_edm"
sys.path.insert(0, str(ADDON_DIR))
from version_specific import get_fcurves

FBX_PATH = Path(r"D:\down\kc390tudo\FBX\KC-390_animado.fbx")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(FBX_PATH))

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
    action_fcurves = list(get_fcurves(action))
    fcurves += len(action_fcurves)
    keys += sum(len(fc.keyframe_points) for fc in action_fcurves)

file_images = [image for image in bpy.data.images if image.source == "FILE" and image.filepath]
missing_images = [
    f"{image.name} ({image.filepath})"
    for image in file_images
    if not Path(bpy.path.abspath(image.filepath)).is_file()
]
meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]

print(
    f"KC390_VERIFY: objetos={len(bpy.data.objects)} meshes={len(meshes)} "
    f"animados={animated} fcurves={fcurves} keys={keys}"
)
print(
    f"KC390_VERIFY: imagens={len(file_images)} ausentes={len(missing_images)} "
    f"{missing_images[:5]}"
)

failures = []
if len(meshes) < 300:
    failures.append(f"poucas malhas: {len(meshes)}")
if animated < 100:
    failures.append(f"poucos objetos animados: {animated}")
if fcurves < 500 or keys < 1000:
    failures.append(f"animacao incompleta: fcurves={fcurves}, keys={keys}")
if not file_images:
    failures.append("FBX sem referencias de textura")
if missing_images:
    failures.append(f"imagens ausentes: {missing_images[:5]}")

if failures:
    print(f"KC390_VERIFY: FAIL {'; '.join(failures)}")
    sys.stdout.flush()
    os._exit(1)
print("KC390_VERIFY: PASS")
