import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ANIMATION_ARGUMENTS = {
    "c_gear": 0, "r_gear": 3, "l_gear": 5,
    "custom_anim_GEAR_CENTER_STEER_ANGLE_01": 2,
    "l_aileron_percent_key": 9, "r_aileron_percent_key": 10,
    "elevator_percent_key": 11, "trimtab_elevator": 11,
    "rudder_percent_key": 12, "l_flap_percent_key": 13, "r_flap_percent_key": 13,
    "l_spoiler_key": 15, "r_spoiler_key": 15,
    "custom_anim_rampa_amorte": 18, "custom_anim_rampa_inferior": 18,
    "custom_anim_rampa_superior": 18, "door_0": 19, "door_1": 19, "door_2": 20,
    "custom_anim_ENG_N1_RPM_1_00": 21, "custom_anim_GENERAL_ENG_RPM_1_01": 21,
    "custom_anim_ENG_N1_RPM_2_01": 22, "custom_anim_GENERAL_ENG_RPM_2_03": 22,
    "thrust_rev_1": 28, "thrust_rev_2": 29,
    "custom_anim_defletor_esq": 30, "custom_anim_defletor_dir": 31,
    "c_tire_blurred_key": 101,
    "r_tire_blurred_key": 102, "r_tire_still_key": 102,
    "l_tire_blurred_key": 103, "l_tire_still_key": 103,
}
DCS_TRANSFORM = Matrix(((0, 1, 0, 0), (0, 0, 1, 0), (1, 0, 0, 0), (0, 0, 0, 1)))


def damage_cell(material, name, position):
    material = material.lower()
    name = name.lower()
    forward, height, lateral = position
    side = "L" if lateral < 0 else "R"
    if "light" in name or "blur" in name or "antena" in name:
        return None
    if material.startswith("kc-390_gear_"):
        return "WHEEL_F" if material.endswith("nose") else "WHEEL_" + side
    if "rudder" in name:
        return "RUDDER"
    if material == "kc-390_elevator":
        return "ELEVATOR_" + side
    if material == "kc-390_horiz_stabiliser":
        return "STABILIZER_" + side + "_OUT"
    if material.startswith("kc-390_wing"):
        if "aileron" in material:
            return "AILERON_" + side
        if "flap" in material:
            return "FLAP_" + side + ("_IN" if abs(lateral) < 7 else "_OUT")
        section = "IN" if abs(lateral) < 6 else "CENTER" if abs(lateral) < 13.5 else "OUT"
        return "WING_" + side + "_" + section
    if material.startswith("iae") or material == "kc-390_iae novo":
        return "ENGINE_" + side
    if material.startswith("kc-390_fuselage") or material == "kc-390_glass":
        if material == "kc-390_fuselage g":
            return "TAIL_BOTTOM"
        if forward > 10:
            return "NOSE_CENTER"
        if forward > 7 and height > -1:
            return "COCKPIT"
        if forward < -16:
            return "TAIL"
        if forward < -11:
            return "TAIL_LEFT_SIDE" if side == "L" else "TAIL_RIGHT_SIDE"
        return "FUSELAGE_LEFT_SIDE" if side == "L" else "FUSELAGE_RIGHT_SIDE"
    return None


def prepare_animations():
    from version_specific import get_fcurves

    summary = {}
    for obj in bpy.context.scene.objects:
        if not obj.animation_data or not obj.animation_data.action:
            continue
        tag = obj.get("fsx_anim_tag")
        argument = ANIMATION_ARGUMENTS.get(tag)
        if argument is None:
            obj.animation_data.action = None
            continue
        action = obj.animation_data.action.copy()
        obj.animation_data.action = action
        curves = get_fcurves(action)
        frames = sorted({point.co.x for curve in curves for point in curve.keyframe_points})
        assert frames and frames[-1] > frames[0], obj.name
        summary.setdefault(tag, {"argument": argument, "source_frames": frames})
        action.name = f"{argument}_collision_{obj.name}"
        for curve in curves:
            for point in curve.keyframe_points:
                source_frame = point.co.x
                if argument == 2:
                    target_frame = {0: 100, 100: 200, 200: 0}[round(source_frame)]
                else:
                    normalized = (source_frame - frames[0]) / (frames[-1] - frames[0])
                    target_frame = normalized * 200 if argument in {9, 10, 11, 12} else 100 + normalized * 100
                point.co.x = target_frame
                point.handle_left.x = target_frame
                point.handle_right.x = target_frame
                point.interpolation = "LINEAR"
            curve.update()
    bpy.context.scene.frame_set(100)
    bpy.context.view_layer.update()
    return summary


def build_collision(output):
    from animation import extract_transform_animation
    from pyedm_platform_selector import pyedm

    animations = prepare_animations()
    model = pyedm.Model()
    root = model.getRootTransform().addChild(pyedm.Transform("KC390_DCS_axes", DCS_TRANSFORM))
    controls = {}
    cells = Counter()
    bounds = []
    shell_count = 0

    def control_for(obj):
        if obj.name not in controls:
            parent = control_for(obj.parent) if obj.parent else root
            controls[obj.name] = extract_transform_animation(parent, obj)
        return controls[obj.name]

    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or not obj.data.polygons:
            continue
        world_matrix = DCS_TRANSFORM @ obj.matrix_world
        material_names = [slot.material.name if slot.material else "" for slot in obj.material_slots]
        if not any(damage_cell(name, obj.name, world_matrix.translation) for name in material_names):
            continue
        obj.data.calc_loop_triangles()
        triangle_count = len(obj.data.loop_triangles)
        triangle_limit = 96
        if obj.name == "fuselage a":
            triangle_limit = 2400
        elif any(name == "kc-390_wing" for name in material_names):
            triangle_limit = 480
        elif any(name in {"kc-390_horiz_stabiliser", "kc-390_IAE novo"} for name in material_names):
            triangle_limit = 384
        elif any(name.startswith("kc-390_gear_") for name in material_names):
            triangle_limit = 48
        if triangle_count > triangle_limit:
            modifier = obj.modifiers.new("KC390_collision_simplification", "DECIMATE")
            modifier.ratio = triangle_limit / triangle_count
            modifier.use_collapse_triangulate = True
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            groups = defaultdict(list)
            for triangle in mesh.loop_triangles:
                vertices = [mesh.vertices[index].co.copy() for index in triangle.vertices]
                if (vertices[1] - vertices[0]).cross(vertices[2] - vertices[0]).length_squared < 1e-14:
                    continue
                centroid = world_matrix @ ((vertices[0] + vertices[1] + vertices[2]) / 3)
                cell = damage_cell(material_names[triangle.material_index], obj.name, centroid)
                if cell:
                    groups[cell].extend(vertices)
            for cell, vertices in groups.items():
                positions = [coordinate for vertex in vertices for coordinate in vertex]
                assert all(math.isfinite(coordinate) for coordinate in positions), obj.name
                shell = pyedm.ShellNode(cell)
                shell.setPositions(positions)
                shell.setIndices(list(range(len(vertices))))
                shell.setControlNode(control_for(obj))
                model.addShellNode(shell)
                cells[cell] += len(vertices) // 3
                bounds.extend(world_matrix @ vertex for vertex in vertices)
                shell_count += 1
        finally:
            evaluated.to_mesh_clear()
    required = {"NOSE_CENTER", "COCKPIT", "FUSELAGE_LEFT_SIDE", "FUSELAGE_RIGHT_SIDE", "ENGINE_L", "ENGINE_R", "TAIL", "RUDDER"}
    assert required.issubset(cells), sorted(required.difference(cells))
    assert len(cells) >= 25, cells
    assert sum(cells.values()) < 25000, "Collision triangle budget exceeded"
    minimum = [min(vertex[axis] for vertex in bounds) for axis in range(3)]
    maximum = [max(vertex[axis] for vertex in bounds) for axis in range(3)]
    model.setBBox(tuple(minimum + maximum))
    model.setUserBox(tuple(minimum + maximum))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".staged.edm")
    result = model.save(str(temporary), 10)
    assert not result, result
    assert b"model::ShellNode" in temporary.read_bytes(), "No exported collision nodes"
    temporary.replace(output)
    return {
        "output": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "cells": dict(sorted(cells.items())), "shell_nodes": shell_count,
        "triangles": sum(cells.values()), "animations": animations,
        "minimum": minimum, "maximum": maximum,
    }


def inspect_source(source, addon):
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    sys.path.insert(0, str(addon))
    from pyedm_platform_selector import pyedm

    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.scene.frame_set(100)
    meshes = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        meshes.append({
            "name": obj.name,
            "materials": [slot.material.name for slot in obj.material_slots if slot.material],
            "vertices": len(obj.data.vertices),
            "minimum": [min(corner[axis] for corner in corners) for axis in range(3)],
            "maximum": [max(corner[axis] for corner in corners) for axis in range(3)],
            "action": obj.animation_data.action.name if obj.animation_data and obj.animation_data.action else None,
        })
    api = {}
    for class_name in ("Model", "ShellNode", "SegmentsNode", "Transform"):
        api_class = getattr(pyedm, class_name)
        api[class_name] = {
            "constructor": api_class.__init__.__doc__,
            "methods": {
                name: getattr(api_class, name).__doc__
                for name in dir(api_class) if not name.startswith("_")
            },
        }
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    return {
        "source": str(source),
        "source_sha256": source_hash,
        "blender": bpy.app.version_string,
        "exporter_binary": str(Path(pyedm.__file__).name),
        "api": api,
        "meshes": meshes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--addon", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    report = inspect_source(options.source, options.addon)
    if options.output:
        report["collision"] = build_collision(options.output)
    assert hashlib.sha256(options.source.read_bytes()).hexdigest() == report["source_sha256"]
    options.report.parent.mkdir(parents=True, exist_ok=True)
    options.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PASS: inspected {len(report['meshes'])} meshes using Blender {report['blender']}; source unchanged")
    if options.output:
        collision = report["collision"]
        print(f"PASS: {len(collision['cells'])} damage cells, {collision['shell_nodes']} shells, {collision['triangles']} triangles")


if __name__ == "__main__":
    main()