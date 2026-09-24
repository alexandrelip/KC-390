import argparse
import contextlib
import dataclasses
import hashlib
import io
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path


MODEL_NAMES = ("KC-390.edm", "KC-390_lod01.edm", "KC-390_lod02.edm", "KC-390_lod03.edm")
DAMAGE_IDS = {
    "NOSE_CENTER": 0, "NOSE_LEFT_SIDE": 1, "NOSE_RIGHT_SIDE": 2,
    "COCKPIT": 3, "CABIN_LEFT_SIDE": 4, "CABIN_RIGHT_SIDE": 5, "CABIN_BOTTOM": 6,
    "FRONT_GEAR_BOX": 8, "FUSELAGE_LEFT_SIDE": 9, "FUSELAGE_RIGHT_SIDE": 10,
    "ENGINE_L": 11, "ENGINE_R": 12, "LEFT_GEAR_BOX": 15, "RIGHT_GEAR_BOX": 16,
    "WING_L_OUT": 23, "WING_R_OUT": 24, "AILERON_L": 25, "AILERON_R": 26,
    "WING_L_CENTER": 29, "WING_R_CENTER": 30, "FLAP_L_OUT": 31, "FLAP_R_OUT": 32,
    "WING_L_IN": 35, "WING_R_IN": 36, "FLAP_L_IN": 37, "FLAP_R_IN": 38,
    "STABILIZER_L_OUT": 45, "STABILIZER_R_OUT": 46,
    "ELEVATOR_L": 51, "ELEVATOR_R": 52, "RUDDER": 53,
    "TAIL": 55, "TAIL_LEFT_SIDE": 56, "TAIL_RIGHT_SIDE": 57, "TAIL_BOTTOM": 58,
    "FUSELAGE_BOTTOM": 82, "WHEEL_F": 83, "WHEEL_L": 84, "WHEEL_R": 85,
    "TAIL_TOP": 100,
}
DAMAGE_ARGUMENTS = {name: 140 + index for index, name in enumerate(DAMAGE_IDS)}
VISIBILITY_PREFIX = "KC390_DAMAGE_"
VISIBLE_DAMAGE_LIMIT = 0.999
FRAGMENTS = {
    "KC-390_NoseCone.edm": {"NOSE_CENTER", "NOSE_LEFT_SIDE", "NOSE_RIGHT_SIDE"},
    "KC-390_WingLeft.edm": {name for name in DAMAGE_IDS if name.startswith(("WING_L_", "FLAP_L_")) or name in {"AILERON_L", "ENGINE_L"}},
    "KC-390_WingRight.edm": {name for name in DAMAGE_IDS if name.startswith(("WING_R_", "FLAP_R_")) or name in {"AILERON_R", "ENGINE_R"}},
    "KC-390_CargoDoor.edm": {"TAIL_BOTTOM"},
}


def damage_cell(material, name, position):
    material, name = material.lower(), name.lower()
    forward, height, lateral = position
    side = "L" if lateral < 0 else "R"
    if "light" in name or "blur" in name or "antena" in name:
        return None
    if any(part in name for part in ("ramp_1", "ramp_2", "ramp_strut", "fuselage g_ramp")) and forward < -5.8:
        return "TAIL_BOTTOM"
    if material.startswith("kc-390_gear_"):
        front = material.endswith("nose")
        if any(word in name for word in ("wheel", "tire", "roda", "nose landing gear f")) or height < -3.2:
            return "WHEEL_F" if front else "WHEEL_" + side
        return "FRONT_GEAR_BOX" if front else "LEFT_GEAR_BOX" if side == "L" else "RIGHT_GEAR_BOX"
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
        if forward > 11.3:
            return "NOSE_CENTER"
        if forward > 10:
            return "NOSE_LEFT_SIDE" if side == "L" else "NOSE_RIGHT_SIDE"
        if forward > 7 and height > -1:
            return "COCKPIT"
        if forward > 5:
            if height < -1:
                return "CABIN_BOTTOM"
            return "CABIN_LEFT_SIDE" if side == "L" else "CABIN_RIGHT_SIDE"
        if forward < -11 and height > 2:
            return "TAIL_TOP"
        if forward < -16:
            return "TAIL"
        if forward < -11:
            return "TAIL_LEFT_SIDE" if side == "L" else "TAIL_RIGHT_SIDE"
        if height < -1.7:
            return "FUSELAGE_BOTTOM"
        return "FUSELAGE_LEFT_SIDE" if side == "L" else "FUSELAGE_RIGHT_SIDE"
    return None


def visual_cell(material, name, position):
    cell = damage_cell(material, name.replace("blur", "fan").replace("light", "lamp"), position)
    if cell:
        return cell
    lowered = material.lower()
    side = "L" if position[2] < 0 else "R"
    if lowered.startswith("revo_"):
        return "WING_" + side + "_CENTER"
    if "iae" in name.lower():
        return "ENGINE_" + side
    return damage_cell("kc-390_fuselage", name, position) or "FUSELAGE_BOTTOM"


def read_model(path, parser_class):
    class RecordingParser(parser_class):
        def __init__(self, stream):
            super().__init__(stream)
            self.records = {}
            self.headers = {}
            self.active_record = None

        def _read_index_map(self):
            result = super()._read_index_map()
            if result:
                raise ValueError("Expected the empty indices used by the KC-390 exporter")
            return result

        def _read_named_type(self):
            start = self.r.tell()
            previous = self.active_record
            self.active_record = start
            result = super()._read_named_type()
            self.records[id(result)] = (start, self.r.tell())
            self.active_record = previous
            return result

        def _read_base_node(self):
            result = super()._read_base_node()
            self.headers[self.active_record] = self.r.tell()
            return result

        def _read_parent_data(self):
            start = self.r.tell()
            result = super()._read_parent_data()
            self.records[id(result)] = (start, self.r.tell())
            return result

        def _read_vertex_data(self):
            start = self.r.tell()
            result = super()._read_vertex_data()
            self.records[id(result)] = (start, self.r.tell())
            return result

        def _read_index_data(self):
            start = self.r.tell()
            result = super()._read_index_data()
            self.records[id(result)] = (start, self.r.tell())
            return result

    data = path.read_bytes() if isinstance(path, Path) else path
    parser = RecordingParser(io.BytesIO(data))
    messages = io.StringIO()
    with contextlib.redirect_stdout(messages):
        model = parser.parse()
    if messages.getvalue() or parser.r.remaining():
        raise ValueError(f"Incomplete EDM parse: {messages.getvalue()}")
    return data, model, parser


def neutral_nodes(nodes):
    from mathutils import Quaternion

    def sample(keys, rotation=False):
        ordered = sorted(keys, key=lambda key: key.frame)
        for key in ordered:
            if abs(key.frame) < 1e-8:
                return key.value
        for first, second in zip(ordered, ordered[1:]):
            if first.frame < 0 < second.frame:
                factor = -first.frame / (second.frame - first.frame)
                if rotation:
                    return tuple(Quaternion(first.value).slerp(Quaternion(second.value), factor))
                return tuple(left + factor * (right - left) for left, right in zip(first.value, second.value))
        raise ValueError("Transform track does not contain or bracket zero")

    result = []
    for node in nodes:
        if not hasattr(node, "base"):
            result.append(node)
            continue
        values = {}
        for tracks, property_name in ((node.pos_data, "position"), (node.rot_data, "quat1")):
            if len(tracks) > 1:
                raise ValueError(f"Multiple transform tracks: {node.name}")
            if tracks:
                expected_base = (1, 0, 0, 0) if property_name == "quat1" else (0, 0, 0)
                if any(abs(actual - expected) > 1e-8 for actual, expected in zip(getattr(node.base, property_name), expected_base)):
                    raise ValueError(f"Nonidentity animated base requires explicit composition: {node.name}")
                values[property_name] = sample(tracks[0][1], property_name == "quat1")
        if node.scale_data:
            if len(node.scale_data) != 1:
                raise ValueError(f"Multiple scale tracks: {node.name}")
            for keys, property_name in zip(node.scale_data[0][1], ("quat2", "scale")):
                if not keys:
                    continue
                values[property_name] = sample(keys, property_name == "quat2")
        result.append(dataclasses.replace(node, base=dataclasses.replace(node.base, **values)))
    return result


def geometry_groups(model):
    from dcs_edm_importer.blender.transforms import world_matrix_for_node
    from mathutils import Vector

    nodes = neutral_nodes(model.nodes)
    matrices = [world_matrix_for_node(index, nodes) for index in range(len(nodes))]
    names = []
    for index in range(len(nodes)):
        chain = []
        while index >= 0:
            chain.append(nodes[index].name)
            index = nodes[index].parent_idx
        names.append("/".join(chain))
    result = []
    cells = Counter()
    bounds = {}
    for render in model.render_nodes:
        if render.type != "RenderNode":
            raise ValueError(f"Unsupported geometry: {render.type}")
        material = model.materials[render.material_id]
        if material.vertex_format.size_of(0) != 4:
            raise ValueError("Expected a rigid vertex parent selector")
        if len(render.index_data) % 3:
            raise ValueError("Incomplete triangle")
        groups = defaultdict(list)
        for offset in range(0, len(render.index_data), 3):
            indices = render.index_data[offset:offset + 3]
            selectors = {render.vertex_data[index][3] for index in indices}
            if len(selectors) != 1:
                raise ValueError("A triangle references multiple rigid transforms")
            selector = selectors.pop()
            if selector != int(selector) or not 0 <= selector < len(render.parents):
                raise ValueError(f"Invalid parent selector: {selector}")
            parent = render.parents[int(selector)]
            matrix = matrices[parent.node]
            position = matrix @ (sum((Vector(render.vertex_data[index][:3]) for index in indices), Vector()) / 3)
            name = names[parent.node]
            cell = visual_cell(material.name, name, position)
            groups[(parent.node, parent.index_start, cell)].extend(indices)
            cells[cell] += 1
            if cell not in bounds:
                bounds[cell] = [list(position), list(position)]
            for axis in range(3):
                bounds[cell][0][axis] = min(bounds[cell][0][axis], position[axis])
                bounds[cell][1][axis] = max(bounds[cell][1][axis], position[axis])
        result.append(groups)
    return result, cells, bounds, matrices


def encode_parents(parents):
    output = bytearray(struct.pack("<I", len(parents)))
    for node, start, argument in parents:
        output.extend(struct.pack("<Ii", node, argument) if len(parents) == 1
                      else struct.pack("<Iii", node, start, argument))
    return bytes(output)


def encode_vertices(vertices):
    if not vertices:
        return struct.pack("<II", 0, 0)
    stride = len(vertices[0])
    record = struct.Struct(f"<{stride}f")
    return struct.pack("<II", len(vertices), stride) + b"".join(record.pack(*vertex) for vertex in vertices)


def encode_indices(indices, flag):
    width = 2 if max(indices, default=0) > 65535 else 1
    kind = "I" if width == 2 else "H"
    return struct.pack("<BII", width, len(indices), flag) + struct.pack(f"<{len(indices)}{kind}", *indices)


def regroup_render(render, groups):
    parents, vertices, indices, origins = [], [], [], []
    for (node, start, cell), old_indices in sorted(groups.items()):
        selector = len(parents)
        parents.append((node, start, DAMAGE_ARGUMENTS[cell]))
        remap = {}
        for old_index in old_indices:
            if old_index not in remap:
                vertex = list(render.vertex_data[old_index])
                vertex[3] = float(selector)
                remap[old_index] = len(vertices)
                vertices.append(tuple(vertex))
                origins.append(old_index)
            indices.append(remap[old_index])
    expected = Counter(tuple(render.index_data[offset:offset + 3]) for offset in range(0, len(render.index_data), 3))
    actual = Counter(tuple(origins[index] for index in indices[offset:offset + 3]) for offset in range(0, len(indices), 3))
    if actual != expected:
        raise ValueError("Geometry partition lost or duplicated triangles")
    for vertex, original_index in zip(vertices, origins):
        original = render.vertex_data[original_index]
        if vertex[:3] + vertex[4:] != original[:3] + original[4:]:
            raise ValueError("Vertex position, normal or UV changed")
    return parents, vertices, indices


def node_header(type_index, name):
    encoded = name.encode("utf-8")
    return struct.pack("<II", type_index, len(encoded)) + encoded + struct.pack("<II", 0, 0)


def validate_damage_model(model):
    cells = Counter()
    by_argument = {argument: name for name, argument in DAMAGE_ARGUMENTS.items()}
    for render in model.render_nodes:
        for parent in render.parents:
            control = model.nodes[parent.node]
            if not control.name.startswith(VISIBILITY_PREFIX) or len(control.vis_data) != 1:
                raise ValueError("Missing destruction visibility control")
            argument, ranges = control.vis_data[0]
            if argument not in by_argument or argument != parent.damage_arg or ranges != [(-1.0, VISIBLE_DAMAGE_LIMIT)]:
                raise ValueError("Unmapped visual damage argument")
        for offset in range(0, len(render.index_data), 3):
            selectors = {render.vertex_data[index][3] for index in render.index_data[offset:offset + 3]}
            if len(selectors) != 1:
                raise ValueError("Invalid triangle transform selection")
            parent = render.parents[int(selectors.pop())]
            argument = model.nodes[parent.node].vis_data[0][0]
            cells[by_argument[argument]] += 1
    if set(cells) != set(DAMAGE_IDS):
        raise ValueError("Visual model does not cover all 40 damage cells")
    return cells


def build_visual(data, model, parser, parser_class):
    if any(node.name.startswith(VISIBILITY_PREFIX) for node in model.nodes):
        return data, {"cells": dict(validate_damage_model(model))}
    groups, cells, bounds, _ = geometry_groups(model)
    if set(cells) != set(DAMAGE_IDS):
        raise ValueError(f"Missing visual cells: {sorted(set(DAMAGE_IDS).difference(cells))}")
    patches = []
    controls, added_nodes, added_parents = {}, [], []
    visibility_name = "model::ArgVisibilityNode"
    if visibility_name in parser.r.string_table:
        visibility_type = parser.r.string_table.index(visibility_name)
    else:
        table_size = struct.unpack_from("<I", data, 5)[0]
        table = data[9:9 + table_size]
        if not table.endswith(b"\0"):
            raise ValueError("Expected a terminated EDM string table")
        visibility_type = len(parser.r.string_table)
        expanded = table + b"\0" + visibility_name.encode("ascii") + b"\0"
        patches.append((5, 9 + table_size, struct.pack("<I", len(expanded)) + expanded))
    for render, partition in zip(model.render_nodes, groups):
        parents, vertices, indices = regroup_render(render, partition)
        controlled_parents = []
        for parent, start, argument in parents:
            key = parent, argument
            if key not in controls:
                controls[key] = len(model.nodes) + len(added_nodes)
                name = f"{VISIBILITY_PREFIX}{argument}_{parent}"
                added_nodes.append(node_header(visibility_type, name) + struct.pack("<III2d", 1, argument, 1, -1, VISIBLE_DAMAGE_LIMIT))
                added_parents.append(parent)
            controlled_parents.append((controls[key], start, argument))
        index_start, _ = parser.records[id(render.index_data)]
        flag = struct.unpack_from("<I", data, index_start + 5)[0]
        for original, replacement in (
            (render.parents, encode_parents(controlled_parents)),
            (render.vertex_data, encode_vertices(vertices)),
            (render.index_data, encode_indices(indices, flag)),
        ):
            start, end = parser.records[id(original)]
            patches.append((start, end, replacement))
    root_end = parser.records[id(model.root)][1]
    declared_arguments = struct.unpack_from("<I", data, root_end - 4)[0]
    arguments = set(DAMAGE_ARGUMENTS.values())
    for node in model.nodes:
        for field in ("pos_data", "rot_data", "scale_data", "vis_data"):
            arguments.update(argument for argument, _ in getattr(node, field, []))
    for material in model.materials:
        arguments.update(value.argument for value in material.animated_uniforms.values() if hasattr(value, "argument"))
    argument_count = max(declared_arguments, max(arguments) + 1)
    patches.append((root_end - 4, root_end, struct.pack("<I", argument_count)))
    nodes_end = parser.records[id(model.nodes[-1])][1]
    parents_end = nodes_end + len(model.nodes) * 4
    all_parents = [node.parent_idx for node in model.nodes] + added_parents
    patches.extend([
        (root_end, root_end + 4, struct.pack("<I", len(all_parents))),
        (nodes_end, parents_end, b"".join(added_nodes) + struct.pack(f"<{len(all_parents)}i", *all_parents)),
    ])
    output = bytearray(data)
    for start, end, replacement in sorted(patches, reverse=True):
        output[start:end] = replacement
    _, updated, _ = read_model(bytes(output), parser_class)
    if updated.root != model.root or updated.nodes[:len(model.nodes)] != model.nodes or updated.connectors != model.connectors:
        raise ValueError("Materials, transforms, animations or connectors changed")
    if updated.shell_nodes != model.shell_nodes or updated.light_nodes != model.light_nodes:
        raise ValueError("Unrelated render categories changed")
    if len(updated.render_nodes) != len(model.render_nodes):
        raise ValueError("Material groups changed")
    if validate_damage_model(updated) != cells:
        raise ValueError("Damage coverage changed during serialization")
    return bytes(output), {"cells": dict(cells), "bounds": bounds, "visibility_controls": len(controls), "draw_calls": len(updated.render_nodes), "argument_count_before": declared_arguments, "argument_count": argument_count}


def build_fragments(data, model, parser, parser_class):
    from dcs_edm_importer.blender.transforms import local_matrix_for_node
    from mathutils import Vector

    if any(node.name.startswith(VISIBILITY_PREFIX) for node in model.nodes):
        raise ValueError("Fragments must be generated from the intact source snapshot")
    partitions, _, _, matrices = geometry_groups(model)
    transform_type = parser.r.string_table.index("model::TransformNode")
    frozen_nodes = []
    for node in neutral_nodes(model.nodes):
        matrix = local_matrix_for_node(node)
        frozen_nodes.append(node_header(transform_type, node.name) + struct.pack("<16d", *(value for row in matrix.transposed() for value in row)))
    parents = struct.pack(f"<{len(model.nodes)}i", *(node.parent_idx for node in model.nodes))
    root_start, root_end = parser.records[id(model.root)]
    bbox_offset = parser.headers[root_start] - root_start
    results = []
    for filename, selected in FRAGMENTS.items():
        render_records, points = [], []
        triangle_count = 0
        for render, partition in zip(model.render_nodes, partitions):
            subset = {key: indices for key, indices in partition.items() if key[2] in selected}
            if not subset:
                continue
            fragment_parents, vertices, indices = [], [], []
            for (node, start, _), original_indices in sorted(subset.items()):
                selector = len(fragment_parents)
                fragment_parents.append((node, start, -1))
                remap = {}
                for original_index in original_indices:
                    if original_index not in remap:
                        vertex = list(render.vertex_data[original_index])
                        vertex[3] = float(selector)
                        remap[original_index] = len(vertices)
                        vertices.append(tuple(vertex))
                        points.append(matrices[node] @ Vector(vertex[:3]))
                    indices.append(remap[original_index])
            start, _ = parser.records[id(render)]
            parent_start, _ = parser.records[id(render.parents)]
            index_start, _ = parser.records[id(render.index_data)]
            flag = struct.unpack_from("<I", data, index_start + 5)[0]
            render_records.append(data[start:parent_start] + encode_parents(fragment_parents)
                                  + encode_vertices(vertices) + encode_indices(indices, flag))
            triangle_count += len(indices) // 3
        if triangle_count < 100:
            raise ValueError(f"Empty or incomplete fragment: {filename}")
        minimum = [min(point[axis] for point in points) for axis in range(3)]
        maximum = [max(point[axis] for point in points) for axis in range(3)]
        if filename == "KC-390_CargoDoor.edm" and maximum[0] > -5.7:
            raise ValueError("Cargo door fragment includes forward fuselage geometry")
        root_record = bytearray(data[root_start:root_end])
        struct.pack_into("<6d", root_record, bbox_offset, *(minimum + maximum))
        render_category = parser.r.string_table.index("RENDER_NODES")
        output = (data[:root_start] + root_record + struct.pack("<I", len(frozen_nodes))
                  + b"".join(frozen_nodes) + parents
                  + struct.pack("<III", 1, render_category, len(render_records)) + b"".join(render_records))
        _, verified, _ = read_model(output, parser_class)
        if verified.materials != model.materials or verified.connectors or verified.shell_nodes:
            raise ValueError(f"Invalid fragment materials or attachments: {filename}")
        if sum(len(render.index_data) // 3 for render in verified.render_nodes) != triangle_count:
            raise ValueError(f"Fragment triangles changed: {filename}")
        if any(node.type != "TransformNode" for node in verified.nodes):
            raise ValueError(f"Fragment contains aircraft animation controls: {filename}")
        results.append((filename, output, {"triangles": triangle_count, "minimum": minimum, "maximum": maximum,
                                         "sha256": hashlib.sha256(output).hexdigest(), "bytes": len(output)}))
    return results


def inspect_model(path, parser_class):
    data, model, parser = read_model(path, parser_class)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "root_fields": [field.name for field in dataclasses.fields(model.root)],
        "render_fields": [field.name for field in dataclasses.fields(model.render_nodes[0])],
        "nodes": [
            {"name": node.name, "type": type(node).__name__, "parent": node.parent_idx,
             "span": parser.records[id(node)]}
            for node in model.nodes
        ],
        "render_nodes": [
            {"type": type(node).__name__, "span": parser.records[id(node)],
             **{field.name: getattr(node, field.name)
                for field in dataclasses.fields(node)
                if isinstance(getattr(node, field.name), (str, int, float, bool))}}
            for node in model.render_nodes
        ],
        "connectors": len(model.connectors),
        "shells": len(model.shell_nodes),
    }


def main():
    parser = argparse.ArgumentParser(description="Inspect and prepare KC-390 component damage models.")
    parser.add_argument("--importer", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    options = parser.parse_args(arguments)
    sys.path.insert(0, str(options.importer.parent))
    from dcs_edm_importer.edm.parser import EDMFileParser

    if options.output:
        if options.output.exists():
            raise FileExistsError(f"Refusing to reuse staging directory: {options.output}")
        report = {}
        staged = []
        for name in MODEL_NAMES:
            data, model, parsed = read_model(options.source / name, EDMFileParser)
            if name == MODEL_NAMES[0]:
                for filename, fragment, fragment_report in build_fragments(data, model, parsed, EDMFileParser):
                    staged.append((filename, fragment))
                    report[filename] = fragment_report
                    print(f"PASS: {filename}: {fragment_report['triangles']} original KC-390 triangles; materials preserved; static transforms")
            output, details = build_visual(data, model, parsed, EDMFileParser)
            _, updated, parser_again = read_model(output, EDMFileParser)
            repeated, _ = build_visual(output, updated, parser_again, EDMFileParser)
            if repeated != output:
                raise ValueError(f"Damage mapping is not idempotent: {name}")
            details.update(original_sha256=hashlib.sha256(data).hexdigest(),
                           sha256=hashlib.sha256(output).hexdigest(), bytes=len(output))
            staged.append((name, output))
            report[name] = details
            print(f"PASS: {name}: {len(details['cells'])} visual damage cells; "
                  "all triangles, UVs, materials, animations and connectors preserved; idempotent")
        options.output.mkdir(parents=True)
        for name, data in staged:
            (options.output / name).write_bytes(data)
    else:
        report = {name: inspect_model(options.source / name, EDMFileParser) for name in MODEL_NAMES}
    options.report.parent.mkdir(parents=True, exist_ok=True)
    options.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not options.output:
        for name, model in report.items():
            print(f"PASS: {name}: complete parse; {len(model['nodes'])} controls; "
                  f"{len(model['render_nodes'])} render nodes; {model['connectors']} connectors")


if __name__ == "__main__":
    main()