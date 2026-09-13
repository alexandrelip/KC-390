from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]


def measure_tail_uv(work: Path) -> None:
    from mathutils.bvhtree import BVHTree
    from mathutils.geometry import barycentric_transform

    vertices = []
    coordinates = []
    triangles = []
    for object_ in bpy.context.scene.objects:
        if object_.type != "MESH" or "rudder" in object_.name.lower():
            continue
        mesh = object_.data
        if not mesh.uv_layers.active:
            continue
        mesh.calc_loop_triangles()
        for triangle in mesh.loop_triangles:
            material = object_.material_slots[triangle.material_index].material if triangle.material_index < len(object_.material_slots) else None
            if material is None or material.name != "kc-390_fuselage a5":
                continue
            start = len(vertices)
            triangles.append((start, start + 1, start + 2))
            for index, loop in zip(triangle.vertices, triangle.loops):
                vertices.append(object_.matrix_world @ mesh.vertices[index].co)
                uv = mesh.uv_layers.active.data[loop].uv
                coordinates.append(Vector((uv.x * 2048, (1 - uv.y) * 2048, 0)))
    surface = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    desired_centre = Vector((0, -20.8, 4.6))
    toward_tip = Vector((0, -3.5, 4)).normalized() * 2.5
    toward_leading_edge = Vector((0, 4, 3.5)).normalized() * 0.39
    report = {}
    offsets = sorted((Vector((0, step_y * 0.2, step_z * 0.2)) for step_y in range(-10, 11) for step_z in range(-5, 6)), key=lambda offset: offset.length_squared)
    for offset in offsets:
        centre = desired_centre + offset
        report = {}
        for side, sign in (("positive_x", 1), ("negative_x", -1)):
            right = toward_tip * -sign
            corners = [centre - right + toward_leading_edge, centre + right + toward_leading_edge, centre + right - toward_leading_edge, centre - right - toward_leading_edge]
            pixels = []
            for corner in corners:
                origin = Vector((sign * 50, corner.y, corner.z))
                position, normal, triangle_index, _ = surface.ray_cast(origin, Vector((-sign, 0, 0)), 100)
                if position is None or triangle_index is None or abs(normal.x) < 0.6:
                    break
                indices = triangles[triangle_index]
                uv = barycentric_transform(position, *(vertices[index] for index in indices), *(coordinates[index] for index in indices))
                if not (0 <= uv.x <= 2048 and 0 <= uv.y <= 2048):
                    break
                pixels.append([uv.x, uv.y])
            if len(pixels) != 4:
                break
            report[side] = {"corners_pixels": pixels, "width_metres": 5.0, "height_metres": 0.78, "centre_world": list(centre)}
        if len(report) == 2:
            break
    if len(report) != 2:
        raise ValueError("A matching marking footprint could not be fitted to both sides of the main fin")
    (work / "tail-uv-projection.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


def image_node(tree, path: Path, linear: bool = False):
    if not path.is_file():
        raise FileNotFoundError(path)
    image = bpy.data.images.load(str(path), check_existing=True)
    image.colorspace_settings.name = "Non-Color" if linear else "sRGB"
    if image.size[0] == 0:
        raise ValueError(f"Blender could not decode {path}")
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    return node


def apply_materials(work: Path, variant: str) -> dict:
    names = {"fab": "FAB 2852 - Refinada", "embraer": "Embraer Millennium - Cinza"}
    manifest = json.loads((ROOT / "Liveries" / "KC-390" / names[variant] / "build.json").read_text(encoding="utf-8"))
    source_files = {path.stem.lower(): path for path in (ROOT / "Textures").glob("*.dds")}
    records = {}
    for material in bpy.data.materials:
        candidates = []
        if material.node_tree:
            candidates = [node.image.name.lower().split(".dds")[0] for node in material.node_tree.nodes if node.type == "TEX_IMAGE" and node.image]
        part = next((name for name in candidates if name in manifest["parts"]), None)
        original = next((name for name in candidates if name in source_files), None)
        original_colour = tuple(material.diffuse_color)
        material.use_nodes = True
        tree = material.node_tree
        tree.nodes.clear()
        output = tree.nodes.new("ShaderNodeOutputMaterial")
        shader = tree.nodes.new("ShaderNodeBsdfPrincipled")
        shader.inputs["Base Color"].default_value = original_colour
        shader.inputs["Roughness"].default_value = 0.65
        tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
        if part:
            maps = manifest["parts"][part]["maps"]
            sources = work / "sources" / variant / part
            colour = image_node(tree, sources / (maps["colour"]["texture"] + ".png"))
            tree.links.new(colour.outputs["Color"], shader.inputs["Base Color"])
            roughmet = image_node(tree, sources / (maps["roughmet"]["texture"] + ".png"), linear=True)
            channels = tree.nodes.new("ShaderNodeSeparateColor")
            tree.links.new(roughmet.outputs["Color"], channels.inputs["Color"])
            tree.links.new(channels.outputs["Green"], shader.inputs["Roughness"])
            tree.links.new(channels.outputs["Blue"], shader.inputs["Metallic"])
            normal_texture = image_node(tree, sources / (maps["normal"]["texture"] + ".png"), linear=True)
            normal_channels = tree.nodes.new("ShaderNodeSeparateColor")
            invert = tree.nodes.new("ShaderNodeMath")
            invert.operation = "SUBTRACT"
            invert.inputs[0].default_value = 1
            combine = tree.nodes.new("ShaderNodeCombineColor")
            tree.links.new(normal_texture.outputs["Color"], normal_channels.inputs["Color"])
            tree.links.new(normal_channels.outputs["Red"], combine.inputs["Red"])
            tree.links.new(normal_channels.outputs["Green"], invert.inputs[1])
            tree.links.new(invert.outputs[0], combine.inputs["Green"])
            tree.links.new(normal_channels.outputs["Blue"], combine.inputs["Blue"])
            normal = tree.nodes.new("ShaderNodeNormalMap")
            tree.links.new(combine.outputs["Color"], normal.inputs["Color"])
            tree.links.new(normal.outputs["Normal"], shader.inputs["Normal"])
            records[material.name] = {"part": part, "maps": [maps[role]["texture"] for role in ("colour", "normal", "roughmet")]}
        elif original:
            colour = image_node(tree, source_files[original])
            tree.links.new(colour.outputs["Color"], shader.inputs["Base Color"])
            records[material.name] = {"original": original}
        if material.name in ("kc-390_glass", "kc-390_glass_gold", "kc-390_HUD_glass", "oculos_vidro"):
            shader.inputs["Roughness"].default_value = 0.12
            shader.inputs["Transmission Weight"].default_value = 0.65
            shader.inputs["IOR"].default_value = 1.45
    changed = {entry["part"] for entry in records.values() if "part" in entry}
    if changed != set(manifest["parts"]):
        raise ValueError(f"Unmapped generated parts in source scene: {set(manifest['parts']) - changed}")
    return records


def aim(object_, target: Vector) -> None:
    object_.rotation_euler = (target - object_.location).to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic 3D livery renders; these are not DCS screenshots.")
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--variant", choices=("fab", "embraer"), required=True)
    parser.add_argument("--view", choices=("left", "right", "front", "top"), default="left")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--measure-uv", action="store_true")
    parser.add_argument("--frame", type=int, default=0)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source = Path(bpy.data.filepath)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    scene = bpy.context.scene
    scene.frame_set(100)
    if args.measure_uv:
        measure_tail_uv(args.work)
        return
    neutral_controls = {object_.name: object_.matrix_basis.copy() for object_ in scene.objects if any(part in object_.name.lower() for part in ("rudder", "aileron", "elevator"))}
    scene.frame_set(args.frame)
    if args.frame == 0:
        for name, matrix in neutral_controls.items():
            object_ = bpy.data.objects[name]
            object_.animation_data_clear()
            object_.matrix_basis = matrix
    for object_ in list(scene.objects):
        if object_.type in ("LIGHT", "CAMERA"):
            bpy.data.objects.remove(object_, do_unlink=True)
    materials = apply_materials(args.work, args.variant)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 8
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("KC390 diagnostic studio")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.34, 0.37, 0.40, 1)
    background.inputs["Strength"].default_value = 0.7
    target = Vector((0, -5.5, 0))
    sun_data = bpy.data.lights.new("KC390 daylight", "SUN")
    sun_data.energy = 2.5
    sun_data.angle = math.radians(10)
    sun = bpy.data.objects.new("KC390 daylight", sun_data)
    scene.collection.objects.link(sun)
    sun.location = (30, 20, 45)
    aim(sun, target)
    fill_data = bpy.data.lights.new("KC390 fill", "AREA")
    fill_data.energy = 7000
    fill_data.shape = "DISK"
    fill_data.size = 35
    fill = bpy.data.objects.new("KC390 fill", fill_data)
    scene.collection.objects.link(fill)
    fill.location = (-25, 15, 20)
    aim(fill, target)
    camera_data = bpy.data.cameras.new("KC390 diagnostic camera")
    camera = bpy.data.objects.new("KC390 diagnostic camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = {"left": (60, -5.5, 4), "right": (-60, -5.5, 4), "front": (30, 55, 24), "top": (0, -5.5, 70)}[args.view]
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 49
    aim(camera, target)
    scene.camera = camera
    destination = args.work / "renders"
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / f"{args.variant}-{args.view}.png"
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    if hashlib.sha256(source.read_bytes()).hexdigest() != before:
        raise ValueError("Source Blender scene changed during diagnostic rendering")
    report = {"renderer": "Blender Cycles CPU; not DCS", "source_sha256": before, "variant": args.variant, "view": args.view, "mapped_materials": materials, "output": str(output)}
    (destination / f"{args.variant}-{args.view}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS diagnostic render: {output}; all generated parts mapped; original scene unchanged")


if __name__ == "__main__":
    main()