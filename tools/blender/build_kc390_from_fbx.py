"""Build the KC-390 Blender source scene from the authorized FSX conversion assets.

Run with Blender 4.2:
  blender.exe --background --python build_kc390_from_fbx.py

The script imports the Assimp FBX geometry, removes FSX-only conditional payloads,
merges the separated author animation takes into DCS argument actions, retargets
material images to the deployed DDS files, and saves KC-390-blender.blend.
"""

from __future__ import annotations

import bpy
import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from mathutils import Matrix, Vector


SOURCE_FBX = Path(r"D:\Desenvolvimento\FSPARADCS\DCS KC-390\mcx_author\KC390_author_animated_assimp.fbx")
TAKES_MANIFEST = Path(r"D:\Desenvolvimento\FSPARADCS\DCS KC-390\mcx_author\takes\manifest.json")
TEXTURE_DIR = Path(r"D:\Desenvolvimento\FSPARADCS\DCS KC-390\textures")
OUTPUT_BLEND = Path(r"D:\Desenvolvimento\FSPARADCS\DCS KC-390\KC-390-blender.blend")
REPORT_PATH = Path(r"D:\Desenvolvimento\FSPARADCS\DCS KC-390\_blender_build.json")

SOURCE_FPS = 24.0
MODEL_SCALE = 100.0
DCS_FORWARD_ROTATION_DEG = -90.0
EXPECTED_ARGS = {0, 2, 3, 5, 9, 10, 11, 12, 13, 15, 18, 19, 20, 21, 22, 28, 29, 30, 31, 101, 102, 103}

# These are FSX conditional payload/effect roots removed by the previous Max
# workflow. Names are mapped back to the original FBX frm_* hierarchy.
VISIBILITY_ROOTS = {
    "frm_1", "frm_2", "frm_3", "frm_4", "frm_5", "frm_6", "frm_7",
    "frm_8", "frm_9", "frm_10", "frm_43", "frm_85",
}

# Marker, DCS argument, source-to-DCS timing mode, label.
MAPPINGS = [
    ("AILERON_LEFT_DEFLECTION", 9, "bipolar_reverse_100", "aileron_left"),
    ("AILERON_RIGHT_DEFLECTION", 10, "bipolar_reverse_100", "aileron_right"),
    ("ELEVATOR_DEFLECTION", 11, "bipolar_100", "elevator"),
    ("RUDDER_DEFLECTION", 12, "bipolar_100", "rudder"),
    ("TRAILING_EDGE_FLAPS_LEFT", 13, "unipolar_100", "flaps"),
    ("TRAILING_EDGE_FLAPS_RIGHT", 13, "unipolar_100", "flaps"),
    ("SPOILERS_LEFT", 15, "unipolar_100", "spoilers"),
    ("SPOILERS_RIGHT", 15, "unipolar_100", "spoilers"),
    ("EXIT_OPEN_0", 18, "unipolar_100", "cargo_ramp"),
    ("RAMPA_MODO", 18, "unipolar_100", "cargo_ramp"),
    ("RAMPA_UPPER", 18, "unipolar_100", "cargo_ramp"),
    ("AMORTER", 18, "unipolar_100", "cargo_ramp"),
    ("EXIT_OPEN_1", 19, "unipolar_100", "side_door_1"),
    ("EXIT_OPEN_2", 20, "unipolar_100", "side_door_2"),
    ("ENG_N1_RPM_1", 21, "unipolar_100", "fan_left"),
    ("GENERAL_ENG_RPM_1", 21, "unipolar_100", "fan_left"),
    ("ENG_N1_RPM_2", 22, "unipolar_100", "fan_right"),
    ("GENERAL_ENG_RPM_2", 22, "unipolar_100", "fan_right"),
    ("GEAR_ANIMATION_POSITION_0", 0, "gear_nose_25", "nose_gear"),
    ("GEAR_ANIMATION_POSITION_1", 5, "gear_main_reverse_25", "main_gear_left"),
    ("GEAR_ANIMATION_POSITION_2", 3, "gear_main_reverse_25", "main_gear_right"),
    ("GEAR_CENTER_STEER_ANGLE", 2, "bipolar_200", "nose_steering"),
    ("CENTER_WHEEL_ROTATION", 101, "unipolar_100", "nose_wheel_spin"),
    ("LEFT_WHEEL_ROTATION", 103, "unipolar_100", "left_wheel_spin"),
    ("RIGHT_WHEEL_ROTATION", 102, "unipolar_100", "right_wheel_spin"),
    ("TURB_ENG_REVERSE_NOZZLE_PERCENT_1", 28, "unipolar_40", "reverse_left"),
    ("TURB_ENG_REVERSE_NOZZLE_PERCENT_2", 29, "unipolar_40", "reverse_right"),
    ("DEFLETORL", 30, "unipolar_100", "deflector_left"),
    ("DEFLETORR", 31, "unipolar_100", "deflector_right"),
]


def log(message: str) -> None:
    print(f"KC390_BLENDER: {message}")


def mapping_for_take(name: str):
    upper = name.upper()
    if "ELEVATOR_TRIM" in upper or "SMOKE_ENABLE" in upper:
        return None
    for marker, arg, mode, label in MAPPINGS:
        if marker in upper:
            return arg, mode, label
    return None


def active_action(animation_data):
    if not animation_data:
        return None
    if animation_data.action:
        return animation_data.action
    for track in animation_data.nla_tracks:
        for strip in track.strips:
            if strip.action:
                return strip.action
    return None


def dcs_frame(source_frame: float, mode: str) -> float:
    source_time = (source_frame - 1.0) / SOURCE_FPS
    if mode == "bipolar_reverse_100":
        return 200.0 - 2.0 * source_time
    if mode == "bipolar_100":
        return 2.0 * source_time
    if mode == "bipolar_200":
        return source_time
    if mode == "gear_nose_25":
        return 100.0 + 4.0 * source_time
    if mode == "gear_main_reverse_25":
        return 200.0 - 4.0 * source_time
    if mode == "unipolar_40":
        return 100.0 + 2.5 * source_time
    return 100.0 + source_time


def neutral_source_time(mode: str) -> float:
    if mode in ("bipolar_reverse_100", "bipolar_100"):
        return 50.0
    if mode == "bipolar_200":
        return 100.0
    if mode == "gear_main_reverse_25":
        return 25.0
    return 0.0


def remove_hierarchy(root: bpy.types.Object) -> int:
    items = []

    def collect(obj):
        items.append(obj)
        for child in list(obj.children):
            collect(child)

    collect(root)
    for obj in reversed(items):
        bpy.data.objects.remove(obj, do_unlink=True)
    return len(items)


def clean_image_key(value: str) -> str:
    name = os.path.basename(value).lower()
    while name.endswith(tuple(f".{index:03d}" for index in range(1, 1000))):
        name = name[:-4]
    for suffix in (".png.dds", ".tif.dds", ".jpg.dds", ".jpeg.dds"):
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return os.path.splitext(name)[0]


def retarget_textures(texture_dir: Path):
    index = {path.stem.lower(): path for path in texture_dir.glob("*.dds")}
    matched = set()
    unmatched = set()
    load_errors = []

    for material in bpy.data.materials:
        if not material.use_nodes or not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if node.type != "TEX_IMAGE" or not node.image:
                continue
            image = node.image
            candidates = [
                clean_image_key(image.filepath),
                clean_image_key(image.name),
            ]
            target = next((index[key] for key in candidates if key in index), None)
            if not target:
                unmatched.add(image.name)
                continue
            try:
                dds_image = bpy.data.images.load(str(target), check_existing=True)
                dds_image.name = target.name
                node.image = dds_image
                matched.add(target.name)
            except Exception as exc:
                load_errors.append(f"{target.name}: {exc}")

    return sorted(matched), sorted(unmatched), load_errors


def world_dimensions(meshes):
    corners = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    if not corners:
        return [0.0, 0.0, 0.0]
    minimum = [min(point[axis] for point in corners) for axis in range(3)]
    maximum = [max(point[axis] for point in corners) for axis in range(3)]
    return [maximum[axis] - minimum[axis] for axis in range(3)]


def main() -> None:
    for path in (SOURCE_FBX, TAKES_MANIFEST, TEXTURE_DIR):
        if not path.exists():
            raise FileNotFoundError(path)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = 24
    scene.frame_start = 0
    scene.frame_end = 200
    scene.frame_set(100)

    log(f"importing base {SOURCE_FBX}")
    bpy.ops.import_scene.fbx(filepath=str(SOURCE_FBX), use_anim=False, automatic_bone_orientation=False)
    roots = [obj for obj in bpy.data.objects if obj.parent is None]
    if len(roots) != 1:
        raise RuntimeError(f"Expected one FBX root, found {len(roots)}")
    root = roots[0]
    root.scale = tuple(value * MODEL_SCALE for value in root.scale)
    bpy.context.view_layer.update()
    root.matrix_world = (
        Matrix.Rotation(math.radians(DCS_FORWARD_ROTATION_DEG), 4, "Z")
        @ root.matrix_world
    )
    bpy.context.view_layer.update()

    removed_visibility = 0
    for name in sorted(VISIBILITY_ROOTS):
        obj = bpy.data.objects.get(name)
        if obj:
            removed_visibility += remove_hierarchy(obj)
    log(f"removed FSX-only visibility hierarchy objects={removed_visibility}")

    base_objects = {obj.name: obj for obj in bpy.data.objects}
    base_meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    dimensions = world_dimensions(base_meshes)
    log(f"base objects={len(base_objects)} meshes={len(base_meshes)} dimensions={dimensions}")

    matched_textures, unmatched_textures, texture_errors = retarget_textures(TEXTURE_DIR)
    log(f"DDS matched={len(matched_textures)} unmatched={len(unmatched_textures)} errors={len(texture_errors)}")

    manifest = json.loads(TAKES_MANIFEST.read_text(encoding="utf-8"))
    combined_actions = {}
    action_channels = set()
    missing_targets = set()
    skipped_takes = []
    processed_takes = []
    copied_fcurves = 0
    copied_keys = 0

    for take in manifest:
        take_name = take["name"]
        mapping = mapping_for_take(take_name)
        if not mapping:
            skipped_takes.append(take_name)
            continue
        arg, mode, label = mapping
        take_file = Path(take["file"])
        if not take_file.exists():
            raise FileNotFoundError(take_file)

        before_objects = {obj.as_pointer() for obj in bpy.data.objects}
        before_actions = {action.as_pointer() for action in bpy.data.actions}
        bpy.ops.import_scene.fbx(filepath=str(take_file), use_anim=True, automatic_bone_orientation=False)
        imported_objects = [obj for obj in bpy.data.objects if obj.as_pointer() not in before_objects]
        imported_actions = [action for action in bpy.data.actions if action.as_pointer() not in before_actions]

        take_fcurves = 0
        take_keys = 0
        for imported_obj in imported_objects:
            anim_data = imported_obj.animation_data
            source_action = active_action(anim_data)
            if not source_action:
                continue
            target_name = source_action.name.split("|", 1)[0]
            target_name = re.sub(r"\.\d{3}$", "", target_name)
            target = base_objects.get(target_name)
            if not target:
                missing_targets.add(target_name)
                continue

            action_key = (target_name, arg)
            target_action = combined_actions.get(action_key)
            if target_action is None:
                target_action = bpy.data.actions.new(f"{arg}_{label}_{target_name}")
                combined_actions[action_key] = target_action

            source_frames = defaultdict(set)
            for source_fcurve in source_action.fcurves:
                values = [float(point.co[1]) for point in source_fcurve.keyframe_points]
                if not values or max(values) - min(values) <= 1.0e-8:
                    continue
                if source_fcurve.data_path == "location":
                    group = "location"
                elif source_fcurve.data_path in ("rotation_euler", "rotation_quaternion"):
                    group = "rotation_quaternion"
                elif source_fcurve.data_path == "scale":
                    group = "scale"
                else:
                    continue
                source_frames[group].update(float(point.co[0]) for point in source_fcurve.keyframe_points)
            if mode in ("gear_nose_25", "gear_main_reverse_25"):
                for frames in source_frames.values():
                    frames.update((1.0, 1.0 + SOURCE_FPS * 25.0))

            base_location, base_quaternion, base_scale = target.matrix_local.decompose()
            neutral_frame = 1.0 + SOURCE_FPS * neutral_source_time(mode)
            neutral_whole = int(neutral_frame)
            scene.frame_set(neutral_whole, subframe=neutral_frame - neutral_whole)
            bpy.context.view_layer.update()
            neutral_location, neutral_quaternion, neutral_scale = imported_obj.matrix_local.decompose()
            if mode == "gear_main_reverse_25":
                base_location = neutral_location.copy()
                base_quaternion = neutral_quaternion.copy()
                base_scale = neutral_scale.copy()

            for group, frames in source_frames.items():
                channel_key = (target_name, arg, group)
                if channel_key in action_channels:
                    raise RuntimeError(f"Animation channel conflict: {channel_key} from {take_name}")
                action_channels.add(channel_key)

                samples = {}
                previous_quaternion = None
                for source_frame in sorted(frames):
                    frame = dcs_frame(source_frame, mode)
                    if not -1.0e-4 <= frame <= 200.0001:
                        continue
                    whole_frame = int(source_frame)
                    scene.frame_set(whole_frame, subframe=source_frame - whole_frame)
                    bpy.context.view_layer.update()
                    location, quaternion, scale = imported_obj.matrix_local.decompose()
                    if group == "location":
                        relative_location = location - neutral_location
                        value = tuple(float(component) for component in (base_location + relative_location))
                    elif group == "rotation_quaternion":
                        relative_quaternion = neutral_quaternion.inverted() @ quaternion
                        output_quaternion = base_quaternion @ relative_quaternion
                        output_quaternion.normalize()
                        if previous_quaternion and previous_quaternion.dot(output_quaternion) < 0.0:
                            output_quaternion.negate()
                        previous_quaternion = output_quaternion.copy()
                        value = tuple(float(component) for component in output_quaternion)
                    else:
                        value = tuple(
                            float(base_scale[index] * scale[index] / neutral_scale[index])
                            if abs(neutral_scale[index]) > 1.0e-9 else float(base_scale[index])
                            for index in range(3)
                        )
                    samples[round(frame, 6)] = value

                ordered = sorted(samples.items())
                if len(ordered) < 2:
                    continue
                component_count = len(ordered[0][1])
                for component_index in range(component_count):
                    target_fcurve = target_action.fcurves.new(
                        data_path=group,
                        index=component_index,
                    )
                    target_fcurve.keyframe_points.add(len(ordered))
                    for target_point, (frame, value) in zip(target_fcurve.keyframe_points, ordered):
                        target_point.co = (frame, value[component_index])
                        target_point.interpolation = "LINEAR"
                    target_fcurve.update()
                    copied_fcurves += 1
                    copied_keys += len(ordered)
                    take_fcurves += 1
                    take_keys += len(ordered)

        for imported_obj in imported_objects:
            bpy.data.objects.remove(imported_obj, do_unlink=True)
        for imported_action in imported_actions:
            if imported_action.users == 0:
                bpy.data.actions.remove(imported_action)

        processed_takes.append({
            "name": take_name,
            "arg": arg,
            "fcurves": take_fcurves,
            "keys": take_keys,
        })
        log(f"take {take_name} -> arg {arg}: fcurves={take_fcurves} keys={take_keys}")

    for (target_name, _arg), action in combined_actions.items():
        target = base_objects[target_name]
        if any(fcurve.data_path == "rotation_quaternion" for fcurve in action.fcurves):
            local_matrix = target.matrix_local.copy()
            location, quaternion, scale = local_matrix.decompose()
            target.rotation_mode = "QUATERNION"
            target.location = location
            target.rotation_quaternion = quaternion
            target.scale = scale
        target.animation_data_create()
        target.animation_data.action = action

    actual_args = {arg for _target, arg in combined_actions}
    if actual_args != EXPECTED_ARGS:
        raise RuntimeError(
            f"Argument mismatch missing={sorted(EXPECTED_ARGS - actual_args)} "
            f"extra={sorted(actual_args - EXPECTED_ARGS)}"
        )
    if missing_targets:
        raise RuntimeError(f"Animation targets missing from base FBX: {sorted(missing_targets)}")
    if len(combined_actions) < 140:
        raise RuntimeError(f"Too few animated targets: {len(combined_actions)}")

    scene.frame_set(100)
    OUTPUT_BLEND.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND), compress=True)

    report = {
        "source": str(SOURCE_FBX),
        "output_blend": str(OUTPUT_BLEND),
        "output_bytes": OUTPUT_BLEND.stat().st_size,
        "objects": len(bpy.data.objects),
        "meshes": len(base_meshes),
        "vertices": sum(len(obj.data.vertices) for obj in base_meshes),
        "polygons": sum(len(obj.data.polygons) for obj in base_meshes),
        "dimensions_xyz_m": dimensions,
        "dcs_forward_rotation_deg": DCS_FORWARD_ROTATION_DEG,
        "root_matrix_world": [list(row) for row in root.matrix_world],
        "visibility_objects_removed": removed_visibility,
        "processed_takes": processed_takes,
        "skipped_takes": skipped_takes,
        "animated_targets": len(combined_actions),
        "args": sorted(actual_args),
        "fcurves": copied_fcurves,
        "keys": copied_keys,
        "dds_matched": matched_textures,
        "unmatched_images": unmatched_textures,
        "texture_load_errors": texture_errors,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"saved {OUTPUT_BLEND} ({OUTPUT_BLEND.stat().st_size / 1024 / 1024:.1f} MB)")
    log(f"args={sorted(actual_args)} animated_targets={len(combined_actions)} fcurves={copied_fcurves} keys={copied_keys}")


if __name__ == "__main__":
    main()
