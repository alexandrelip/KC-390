import argparse
import contextlib
import hashlib
import io
import json
import math
import struct
import sys
from pathlib import Path


FAN_ARGUMENTS = {
    "ar_iae_le_still_emp": (21, 407),
    "ar_iae_le_blur_emp": (21, 407),
    "ar_iae_ld_still_emp": (22, 408),
    "ar_iae_ld_blur_emp": (22, 408),
}
MODEL_NAMES = ("KC-390.edm", "KC-390_lod01.edm", "KC-390_lod02.edm", "KC-390_lod03.edm")


def inspect_model(data, parser_class):
    class FanParser(parser_class):
        def __init__(self, stream):
            super().__init__(stream)
            self.rotation_entries = []
            self.fans = []

        def _read_index_map(self):
            index = super()._read_index_map()
            if index:
                raise ValueError("This remapper requires the empty indices emitted by the KC-390 exporter")
            return index

        def _read_rot_arg_entry(self):
            offset = self.r.tell()
            argument, keys = super()._read_rot_arg_entry()
            self.rotation_entries.append((offset, self.r.tell(), argument, keys))
            return argument, keys

        def _arg_anim_node(self, node_type):
            first = len(self.rotation_entries)
            node = super()._arg_anim_node(node_type)
            if node.name not in FAN_ARGUMENTS:
                return node
            entries = self.rotation_entries[first:]
            if len(entries) != 1 or node.pos_data or node.scale_data:
                raise ValueError(f"Unexpected fan controller layout: {node.name}")
            offset, end, argument, keys = entries[0]
            old_argument, new_argument = FAN_ARGUMENTS[node.name]
            if argument not in (old_argument, new_argument):
                raise ValueError(f"Unexpected fan argument {argument}: {node.name}")
            if len(keys) < 4 or keys[0].frame not in (-1, 0) or keys[-1].frame != 1:
                raise ValueError(f"Incomplete fan rotation: {node.name}")
            self.fans.append({
                "name": node.name, "offset": offset, "end": end,
                "argument": argument, "target_argument": new_argument,
                "keys": len(keys), "minimum": keys[0].frame,
            })
            return node

    parser = FanParser(io.BytesIO(data))
    messages = io.StringIO()
    with contextlib.redirect_stdout(messages):
        model = parser.parse()
    if messages.getvalue() or parser.r.remaining():
        raise ValueError(f"EDM was not parsed completely: {messages.getvalue()}")
    if len(parser.fans) != 4 or {fan["name"] for fan in parser.fans} != set(FAN_ARGUMENTS):
        raise ValueError("Expected exactly four KC-390 fan controllers")
    return parser.fans, model


def remap_model(data, parser_class):
    fans, original = inspect_model(data, parser_class)
    result = bytearray(data)
    for fan in reversed(fans):
        offset = fan["offset"]
        if struct.unpack_from("<I", data, offset)[0] != fan["argument"]:
            raise ValueError("Parser offset does not match the original argument")
        original_keys = data[offset + 8:fan["end"]]
        key_format = struct.Struct("<5d")
        if len(original_keys) != fan["keys"] * key_format.size:
            raise ValueError("Unexpected quaternion key layout")
        extra_keys = bytearray()
        if fan["minimum"] == 0:
            for key_index in range(fan["keys"] - 1):
                record = key_format.unpack_from(original_keys, key_index * key_format.size)
                extra_keys.extend(key_format.pack(record[0] - 1, *(-value for value in record[1:])))
        key_count = fan["keys"] + len(extra_keys) // key_format.size
        result[offset:fan["end"]] = struct.pack("<II", fan["target_argument"], key_count) + extra_keys + original_keys
    updated, parsed = inspect_model(result, parser_class)
    if any(fan["argument"] != fan["target_argument"] for fan in updated):
        raise ValueError("Fan argument remapping failed")
    for node in parsed.nodes:
        if node.name not in FAN_ARGUMENTS:
            continue
        keys = node.rot_data[0][1]
        for lower, upper in ((-1, 0), (0, 1)):
            cycle = [key for key in keys if lower <= key.frame <= upper]
            if len(cycle) < 4 or cycle[0].frame != lower or cycle[-1].frame != upper:
                raise ValueError(f"Missing rotation phase: {node.name} {lower}:{upper}")
            quaternions = []
            for key in cycle:
                length = math.sqrt(sum(value * value for value in key.value))
                if abs(length - 1) > 0.00001:
                    raise ValueError("Invalid fan quaternion")
                quaternions.append(tuple(value / length for value in key.value))
            angle = 0
            for first, second in zip(quaternions, quaternions[1:]):
                dot = sum(left * right for left, right in zip(first, second))
                angle += 2 * math.acos(min(1, abs(dot)))
            closure = abs(sum(left * right for left, right in zip(quaternions[0], quaternions[-1])))
            if abs(angle - 2 * math.pi) > 0.001 or closure < 0.99999:
                raise ValueError(f"Fan phase is not a closed full turn: {node.name}")
    restored = bytearray(result)
    originals = {fan["name"]: fan for fan in fans}
    for fan in reversed(updated):
        old = originals[fan["name"]]
        restored[fan["offset"]:fan["end"]] = data[old["offset"]:old["end"]]
    if restored != data:
        raise ValueError("Data outside the four fan rotation records changed")
    if original.root != parsed.root or original.render_nodes != parsed.render_nodes:
        raise ValueError("Materials or visual geometry changed")
    if original.connectors != parsed.connectors or original.shell_nodes != parsed.shell_nodes:
        raise ValueError("Connectors or collision geometry changed")
    return bytes(result), fans


def main():
    parser = argparse.ArgumentParser(description="Configure only KC-390 fan rotations for native DCS two-phase arguments 407/408.")
    parser.add_argument("--importer", type=Path, required=True, help="Directory containing the dcs_edm_importer edm package")
    parser.add_argument("--source", type=Path, required=True, help="Original Shapes directory")
    parser.add_argument("--output", type=Path, required=True, help="New staging directory; source files are never overwritten")
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    options = parser.parse_args(arguments)
    sys.path.insert(0, str(options.importer))
    from edm.parser import EDMFileParser

    if options.output.exists():
        raise FileExistsError(f"Refusing to reuse staging directory: {options.output}")
    models = []
    for name in MODEL_NAMES:
        source = options.source / name
        original = source.read_bytes()
        updated, fans = remap_model(original, EDMFileParser)
        repeated, _ = remap_model(updated, EDMFileParser)
        if repeated != updated:
            raise ValueError(f"Fan remapping is not idempotent: {name}")
        if source.read_bytes() != original:
            raise ValueError(f"Source changed during validation: {source}")
        models.append((name, updated, {
            "source": str(source.resolve()),
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "updated_sha256": hashlib.sha256(updated).hexdigest(),
            "added_bytes": len(updated) - len(original),
            "original_bytes": len(original), "updated_bytes": len(updated),
            "fans": fans,
        }))
    options.output.mkdir(parents=True)
    for name, data, _ in models:
        (options.output / name).write_bytes(data)
    report = {"models": {name: details for name, _, details in models}}
    (options.output / "fan-remap.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, _, details in models:
        print(f"PASS: {name}: 4 fans use 407/408; full turns in both phases; +{details['added_bytes']} bytes; all other data preserved; idempotent")
    print(f"Staged models and manifest: {options.output}")


if __name__ == "__main__":
    main()