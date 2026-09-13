from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK = Path(os.environ.get("LOCALAPPDATA", str(ROOT))) / "KC390-Liveries"
LIVERY_NAMES = {"fab": "FAB 2852 - Refinada", "embraer": "Embraer Millennium - Cinza"}
MAX_TEXTURE_SIZE = 1024
TAIL_MARK_QUADS = (
    ((397.557, 327.951), (697.629, 971.269), (598.692, 1053.919), (282.897, 348.014)),
    ((1610.322, 1452.047), (1767.293, 759.854), (1883.199, 755.498), (1724.669, 1511.916)),
)

MARKINGS = {
    "kc-390_fuselage_a1_c": [
        [(668, 410), (1405, 350), (1410, 425), (674, 488)],
        [(125, 1366), (875, 1445), (868, 1517), (118, 1440)],
        [(800, 485), (864, 485), (864, 640), (800, 640)],
        [(288, 652), (365, 652), (365, 718), (288, 718)],
        [(1170, 1674), (1245, 1674), (1245, 1742), (1170, 1742)],
        [(1005, 630), (1118, 630), (1118, 659), (1005, 659)],
        [(392, 1646), (509, 1646), (509, 1678), (392, 1678)],
    ],
    "kc-390_fuselage_a4_c": [
        [(1480, 382), (1545, 382), (1545, 582), (1480, 582)],
        [(580, 1460), (646, 1460), (646, 1660), (580, 1660)],
        [(1400, 246), (1538, 246), (1538, 374), (1400, 374)],
        [(494, 1664), (628, 1664), (628, 1796), (494, 1796)],
    ],
    "kc-390_fuselage_a5_c": [
        [(637, 881), (785, 881), (785, 1020), (637, 1020)],
        [(1508, 1390), (1644, 1358), (1685, 1485), (1540, 1530)],
    ],
    "kc-390_wing_c": [
        [(637, 660), (741, 660), (741, 899), (637, 899)],
        [(1532, 1199), (1625, 1199), (1625, 1445), (1532, 1445)],
        [(642, 1440), (756, 1440), (756, 1550), (642, 1550)],
        [(1528, 497), (1648, 497), (1648, 615), (1528, 615)],
    ],
}


def marking_mask(name: str, size: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", (2048, 2048))
    draw = ImageDraw.Draw(mask)
    for polygon in MARKINGS.get(name, []):
        draw.polygon(polygon, fill=255)
    return mask.resize(size, Image.Resampling.NEAREST)


def remove_markings(pixels, mask, valid=None):
    import numpy as np
    from scipy import ndimage

    if not np.any(mask):
        return pixels.copy()
    excluded = mask if valid is None else mask | (~valid)
    if excluded.all():
        raise ValueError("No unmarked paint is available for restoration")
    indices = ndimage.distance_transform_edt(excluded, return_distances=False, return_indices=True)
    extended = pixels[indices[0], indices[1]]
    softened = ndimage.gaussian_filter(extended, sigma=(4, 4, 0))
    feather = ndimage.gaussian_filter(mask.astype(np.float32), 0.8)[..., None]
    return pixels * (1 - feather) + softened * feather


def paint_maps(source: Image.Image, name: str, variant: str, clean_identity: bool = False):
    import numpy as np
    from scipy import ndimage

    pixels = np.asarray(source.convert("RGB"), dtype=np.float32)
    red, green, blue = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    green_mask = np.clip((np.minimum(green - red, green - blue) - 3) / 8, 0, 1)
    grey_mask = np.clip((np.minimum(green - red, blue - red) - 6) / 10, 0, 1) * (1 - green_mask)
    paint = green_mask + grey_mask
    luminance = pixels @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    palette = ([83, 96, 79], [148, 152, 150]) if variant == "fab" else ([132, 136, 139], [132, 136, 139])
    references = []
    for pigment, fallback in zip((green_mask, grey_mask), ([110, 151, 117], [180, 205, 215])):
        selected = pixels[pigment > 0.9]
        references.append(np.median(selected, axis=0) if selected.size else fallback)
    coefficients = np.clip(pixels @ np.linalg.pinv(np.asarray(references, dtype=np.float32)), 0, 2)
    total = coefficients.sum(axis=-1, keepdims=True)
    shading = 0.4 + 0.6 * np.clip(total, 0, 1.65)
    weights = coefficients / np.maximum(total, 0.001)
    recoloured = pixels * (1 - paint[..., None]) + (weights @ np.asarray(palette, dtype=np.float32)) * shading * paint[..., None]
    local_pigments = []
    for pigment in (green_mask, grey_mask):
        selected = (pigment > 0.9).astype(np.float32)
        coverage = ndimage.gaussian_filter(selected, 32)
        accumulated = ndimage.gaussian_filter(total[..., 0] * selected, 32)
        local_pigments.append(np.divide(accumulated, coverage, out=np.ones_like(coverage), where=coverage > 0.001))
    illumination = (weights * np.stack(local_pigments, axis=-1)).sum(axis=-1, keepdims=True)
    unlit_shading = np.clip(total / np.maximum(illumination, 0.05), 0.45, 1.3)
    unlit_shading = 0.35 + unlit_shading * 0.65
    if variant == "embraer":
        recoloured = pixels * (1 - paint[..., None]) + np.asarray(palette[0], dtype=np.float32) * unlit_shading * paint[..., None]
    neutral = pixels * (1 - paint[..., None]) + 134 * unlit_shading * paint[..., None]
    markings = np.asarray(marking_mask(name, source.size)) > 0
    background = (np.ptp(pixels, axis=-1) < 1) & (luminance > 180) & (luminance < 210)
    markings &= ~background
    valid_paint = (paint > 0.9) & (~markings)
    neutral = remove_markings(neutral, markings, valid_paint)
    if variant == "embraer" or clean_identity:
        colour_mask = markings.copy()
        if variant == "fab" and name in ("kc-390_fuselage_a4_c", "kc-390_wing_c"):
            insignia = Image.new("L", (2048, 2048))
            for polygon in MARKINGS[name][2:]:
                ImageDraw.Draw(insignia).polygon(polygon, fill=255)
            colour_mask &= np.asarray(insignia.resize(source.size, Image.Resampling.NEAREST)) == 0
        recoloured = remove_markings(recoloured, colour_mask, valid_paint)
    geometry = neutral @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32) / 255
    detail = geometry - ndimage.gaussian_filter(geometry, 2.0)
    boundary = ndimage.maximum_filter(green_mask, 9) - ndimage.minimum_filter(green_mask, 9)
    boundary = np.maximum(boundary, ndimage.maximum_filter(grey_mask, 9) - ndimage.minimum_filter(grey_mask, 9))
    safe_detail = (1 - np.clip(boundary * 2, 0, 1)) * (paint > 0.85) * (~markings)
    height = ndimage.gaussian_filter(np.clip(detail, -0.08, 0.08) * safe_detail, 0.7)
    slope_y, slope_x = np.gradient(height)
    normal_x = np.tanh(-slope_x * 2.6 / 0.12) * 0.12
    normal_y = np.tanh(slope_y * 2.6 / 0.12) * 0.12
    normal = np.stack((normal_x, normal_y, np.ones_like(height)), axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    roughness = (0.73 if variant == "fab" else 0.65) + np.clip(detail, -0.05, 0.05) * 0.25
    metallic = np.zeros_like(height)
    if any(token in name for token in ("gear_", "iae_", "fusel_estrut", "ramp_estrut", "baremetal")):
        exposed = np.clip((luminance - 80) / 110, 0, 1) * np.clip(1 - np.ptp(pixels, axis=-1) / 35, 0, 1) * (1 - paint)
        metallic = exposed * 0.9
        roughness = roughness * (1 - exposed) + 0.32 * exposed
        rubber = np.clip((28 - luminance) / 20, 0, 1) * (1 - paint)
        roughness = roughness * (1 - rubber) + 0.88 * rubber
    roughmet = np.stack((1 - np.clip(-detail * 0.3, 0, 0.035), roughness, metallic), axis=-1)
    albedo = Image.fromarray(np.uint8(np.clip(recoloured, 0, 255))).convert("RGBA")
    albedo.putalpha(source.convert("RGBA").getchannel("A"))
    maps = {
        "colour": albedo,
        "normal": Image.fromarray(np.uint8(np.clip((normal * 0.5 + 0.5) * 255, 0, 255))),
        "roughmet": Image.fromarray(np.uint8(np.clip(roughmet * 255, 0, 255))),
        "paint-mask": Image.fromarray(np.uint8(np.clip(paint * 255, 0, 255))),
        "marking-mask": marking_mask(name, source.size),
    }
    if not np.isfinite(normal).all() or not np.isfinite(roughmet).all():
        raise ValueError(f"Non-finite material values: {name}")
    if not np.array_equal(np.asarray(albedo.getchannel("A")), np.asarray(source.convert("RGBA").getchannel("A"))):
        raise ValueError(f"Alpha changed: {name}")
    if np.max(np.abs(normal[..., :2])) > 0.15:
        raise ValueError(f"Excessive normal relief: {name}")
    return maps


def load_livery(path: Path, interpreter: str = "lua") -> list[dict]:
    code = '''local environment = {DIFFUSE=0, NORMAL_MAP=1, N_MAP=1, ROUGHNESS_METALLIC=13, SELF_ILLUMINATION="SELF_ILLUMINATION", _=function(value) return value end}
local loader
if setfenv then loader=assert(loadfile(%s)); setfenv(loader,environment)
else loader=assert(loadfile(%s,"t",environment)) end
loader()
assert(type(environment.livery)=="table")
for _, binding in ipairs(environment.livery) do
    io.write(string.format("%%s\\t%%s\\t%%s\\t%%s\\n",binding[1],tostring(binding[2]),binding[3],tostring(binding[4])))
end''' % (json.dumps(path.as_posix()), json.dumps(path.as_posix()))
    result = subprocess.run([interpreter, "-e", code], capture_output=True, text=True, check=True)
    return [{"material": row[0], "slot": int(row[1]) if row[1].isdigit() else row[1], "texture": row[2], "shared": row[3] == "true"} for row in csv.reader(io.StringIO(result.stdout), delimiter="\t")]


def brandmarks(work: Path) -> dict[str, Image.Image]:
    import numpy as np
    import pymupdf

    with pymupdf.open(work / "brochure-2026.pdf") as document:
        page = document[0]
        crop = pymupdf.Rect(page.rect.width * 0.62, 0, page.rect.width, page.rect.height * 0.19)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(8, 8), clip=crop, alpha=False)
        pixels = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
        mask = Image.fromarray(np.uint8(np.clip((125 - pixels.max(axis=-1).astype(np.float32)) * 2.8, 0, 255)))
        bounds = mask.getbbox()
        if bounds is None:
            raise ValueError("The brochure wordmark could not be isolated")
        mask = mask.crop(bounds)
        millennium = Image.new("RGBA", mask.size, (220, 224, 225, 255))
        millennium.putalpha(mask)
    with pymupdf.open(work / "embraer-logo-reference.svg") as document:
        pixmap = document[0].get_pixmap(matrix=pymupdf.Matrix(6, 6), alpha=True)
        logo = Image.frombytes("RGBA", (pixmap.width, pixmap.height), pixmap.samples)
        alpha = logo.getchannel("A")
        bounds = alpha.getbbox()
        if bounds is None:
            raise ValueError("The Embraer reference mark is empty")
        alpha = alpha.crop(bounds)
        embraer = Image.new("RGBA", alpha.size, (220, 224, 225, 255))
        embraer.putalpha(alpha)
    return {"millennium": millennium, "embraer": embraer}


def text_mark(text: str, width: int, colour=(26, 29, 29, 255)) -> Image.Image:
    font = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", 180)
    bounds = font.getbbox(text)
    mark = Image.new("RGBA", (bounds[2] - bounds[0] + 8, bounds[3] - bounds[1] + 8))
    ImageDraw.Draw(mark).text((4 - bounds[0], 4 - bounds[1]), text, font=font, fill=colour)
    return mark.resize((width, max(1, round(width * mark.height / mark.width))), Image.Resampling.LANCZOS)


def stamp(layer: Image.Image, mark: Image.Image, centre: tuple[float, float], width: int, angle: float = 0) -> None:
    scale = layer.width / 2048
    resized = mark.resize((round(width * scale), max(1, round(width * scale * mark.height / mark.width))), Image.Resampling.LANCZOS)
    rotated = resized.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    location = (round(centre[0] * scale - rotated.width / 2), round(centre[1] * scale - rotated.height / 2))
    layer.alpha_composite(rotated, location)


def projected_stamp(layer: Image.Image, mark: Image.Image, corners) -> None:
    import numpy as np

    destination = np.asarray(corners) * (layer.width / 2048)
    source = ((0, 0), (mark.width - 1, 0), (mark.width - 1, mark.height - 1), (0, mark.height - 1))
    equations = []
    values = []
    for (pixel_x, pixel_y), (source_x, source_y) in zip(destination, source):
        equations.append([pixel_x, pixel_y, 1, 0, 0, 0, -source_x * pixel_x, -source_x * pixel_y])
        equations.append([0, 0, 0, pixel_x, pixel_y, 1, -source_y * pixel_x, -source_y * pixel_y])
        values.extend((source_x, source_y))
    transform = np.linalg.solve(np.asarray(equations), np.asarray(values))
    warped = mark.transform(layer.size, Image.Transform.PERSPECTIVE, transform.tolist(), Image.Resampling.BICUBIC)
    layer.alpha_composite(warped)


def identity_layer(name: str, size: tuple[int, int], variant: str, marks: dict[str, Image.Image]) -> Image.Image:
    layer = Image.new("RGBA", size)
    if variant == "fab":
        if name == "kc-390_fuselage_a1_c":
            title = text_mark("FOR\u00c7A A\u00c9REA BRASILEIRA", 1600)
            stamp(layer, title, (1035, 421), 717, 5)
            stamp(layer, title, (501, 1448), 741, -6)
            stamp(layer, text_mark("52", 300), (327, 686), 57, 7)
            stamp(layer, text_mark("52", 300), (1204, 1709), 57, -7)
        elif name == "kc-390_fuselage_a4_c":
            label = text_mark("FAB 2852", 600)
            stamp(layer, label, (1515, 484), 176, -90)
            stamp(layer, label, (614, 1561), 176, -90)
        elif name == "kc-390_fuselage_a5_c":
            for text, centre, width, angle in (
                ("KC-390", (711, 909), 127, -5), ("FAB", (702, 951), 78, -5), ("2852", (700, 989), 104, -5),
                ("KC-390", (1582, 1404), 127, 18), ("FAB", (1594, 1444), 78, 18), ("2852", (1606, 1481), 104, 18),
            ):
                stamp(layer, text_mark(text, 400), centre, width, angle)
        elif name == "kc-390_wing_c":
            stamp(layer, text_mark("FAB", 600), (690, 782), 226, 90)
            stamp(layer, text_mark("2852", 700), (1580, 1319), 243, 90)
    elif name == "kc-390_fuselage_a1_c":
        stamp(layer, marks["embraer"], (939, 436), 134, 5)
        stamp(layer, marks["embraer"], (411, 1466), 134, -6)
    elif name == "kc-390_fuselage_a5_c":
        for corners in TAIL_MARK_QUADS:
            projected_stamp(layer, marks["millennium"], corners)
    return layer


def save_source(path: Path, original: Image.Image, base: Image.Image, markings: Image.Image, merged: Image.Image) -> None:
    root = ET.Element("image", {"version": "0.0.3", "w": str(merged.width), "h": str(merged.height), "name": path.stem})
    stack = ET.SubElement(root, "stack")
    layers = [("Markings", markings, True), ("Surface colour", base, True), ("Original reference", original.resize(merged.size, Image.Resampling.LANCZOS), False)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "image/openraster", compress_type=zipfile.ZIP_STORED)
        for index, (label, image, visible) in enumerate(layers):
            member = f"data/layer{index}.png"
            ET.SubElement(stack, "layer", {"name": label, "src": member, "x": "0", "y": "0", "opacity": "1.0", "visibility": "visible" if visible else "hidden", "composite-op": "svg:src-over"})
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            archive.writestr(member, buffer.getvalue())
        archive.writestr("stack.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))
        for member, image in (("mergedimage.png", merged), ("Thumbnails/thumbnail.png", ImageOps.contain(merged, (256, 256)))):
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            archive.writestr(member, buffer.getvalue())


def verify_originals(work: Path) -> None:
    baseline = json.loads((work / "baseline.json").read_text(encoding="utf-8"))
    concurrent_changes = {}
    for relative, record in baseline["textures"].items():
        if digest(ROOT / relative) != record["sha256"]:
            raise ValueError(f"Original texture changed: {relative}")
    for relative, expected in baseline["protected"].items():
        actual = digest(ROOT / relative)
        if relative.startswith("Shapes/") and actual != expected:
            concurrent_changes[relative] = {"baseline_sha256": expected, "current_sha256": actual, "action": "preserved; not part of texture deployment"}
        elif relative.startswith("Liveries/") and actual != expected:
            raise ValueError(f"Original livery changed: {relative}")
    (work / "concurrent-source-changes.json").write_text(json.dumps(concurrent_changes, indent=2) + "\n", encoding="utf-8")


def write_livery(path: Path, bindings: list[dict], name: str) -> None:
    rows = ["livery = {"]
    for binding in bindings:
        material = json.dumps(binding["material"])
        texture = json.dumps(binding["texture"])
        shared = "true" if binding["shared"] else "false"
        rows.append(f"    {{{material}, {binding['slot']}, {texture}, {shared}}},")
    rows += ["}", "", f"name = {json.dumps(name)}", "countries = {}", ""]
    path.write_text("\n".join(rows), encoding="ascii")


def limit_shared_textures(work: Path, variant: str, folder: Path, bindings: list[dict], manifest: dict) -> list[dict]:
    overrides = manifest.setdefault("shared_overrides", {})
    result = []
    for binding in bindings:
        if not binding["shared"]:
            result.append(binding)
            continue
        name = binding["texture"]
        source = ROOT / "Textures" / (name + ".dds")
        metadata = dds_info(source)
        if max(metadata["width"], metadata["height"]) <= MAX_TEXTURE_SIZE:
            result.append(binding)
            continue
        if binding["slot"] not in (0, "SELF_ILLUMINATION"):
            raise ValueError(f"Unsupported shared texture role: {binding}")
        if name not in overrides:
            filename = f"kc390_{variant}_{name}_shared_colour"
            if (folder / (filename + ".dds")).exists():
                raise ValueError(f"Refusing to replace an unowned texture: {filename}")
            with tempfile.TemporaryDirectory(prefix="shared-1k-", dir=work) as temporary:
                png = Path(temporary) / (filename + ".png")
                with Image.open(source) as image:
                    image.convert("RGBA").save(png)
                destination = export_dds(png, folder, "colour", work / "texconv.exe")
            overrides[name] = {"source_sha256": metadata["sha256"], "texture": filename, **dds_info(destination)}
        override = overrides[name]
        if override["source_sha256"] != metadata["sha256"] or digest(folder / (override["texture"] + ".dds")) != override["sha256"]:
            raise ValueError(f"Shared texture override changed outside the build: {name}")
        result.append({**binding, "texture": override["texture"], "shared": False})
    return result


def resize_liveries(work: Path) -> None:
    verify_originals(work)
    prepared = []
    report = {"max_texture_size": MAX_TEXTURE_SIZE, "liveries": {}}
    with tempfile.TemporaryDirectory(prefix=".resize-1k-", dir=ROOT / "Liveries") as temporary:
        staging = Path(temporary)
        for variant, name in LIVERY_NAMES.items():
            directory = ROOT / "Liveries" / "KC-390" / name
            manifest = json.loads((directory / "build.json").read_text(encoding="utf-8"))
            original_hashes = {path.name: digest(path) for path in directory.iterdir() if path.is_file()}
            before_bytes = sum(path.stat().st_size for path in directory.glob("*.dds"))
            for record in manifest["parts"].values():
                for metadata in record["maps"].values():
                    if original_hashes.get(metadata["texture"] + ".dds") != metadata["sha256"]:
                        raise ValueError(f"Generated texture has external edits: {metadata['texture']}")
            for metadata in manifest.get("shared_overrides", {}).values():
                if original_hashes.get(metadata["texture"] + ".dds") != metadata["sha256"]:
                    raise ValueError(f"Shared texture has external edits: {metadata['texture']}")
            destination = staging / name
            shutil.copytree(directory, destination)
            resized = 0
            for part, record in manifest["parts"].items():
                for role, metadata in record["maps"].items():
                    if max(metadata["width"], metadata["height"]) <= MAX_TEXTURE_SIZE:
                        continue
                    source = work / "sources" / variant / part / (metadata["texture"] + ".png")
                    source_hash = digest(source)
                    dds = export_dds(source, destination, role, work / "texconv.exe")
                    if digest(source) != source_hash:
                        raise ValueError(f"Source PNG changed during conversion: {source}")
                    record["maps"][role] = {"texture": metadata["texture"], **dds_info(dds)}
                    resized += 1
            bindings = limit_shared_textures(work, variant, destination, load_livery(directory / "description.lua"), manifest)
            manifest["max_texture_size"] = MAX_TEXTURE_SIZE
            (destination / "build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            write_livery(destination / "description.lua", bindings, name)
            if load_livery(destination / "description.lua") != bindings:
                raise ValueError(f"Resized livery descriptor did not round-trip: {name}")
            for binding in bindings:
                path = (ROOT / "Textures" if binding["shared"] else destination) / (binding["texture"] + ".dds")
                metadata = dds_info(path)
                if max(metadata["width"], metadata["height"]) > MAX_TEXTURE_SIZE:
                    raise ValueError(f"Livery still references a texture above 1K: {path}")
                with Image.open(path) as image:
                    image.load()
            after_bytes = sum(path.stat().st_size for path in destination.glob("*.dds"))
            report["liveries"][variant] = {"before_bytes": before_bytes, "after_bytes": after_bytes, "resized_dds": resized, "shared_overrides": len(manifest["shared_overrides"]), "dds_count": len(list(destination.glob("*.dds")))}
            prepared.append((directory, destination, original_hashes))
            print(f"PASS staged {name}: {resized} resized maps; all livery references <= {MAX_TEXTURE_SIZE}; {before_bytes / 1024**2:.2f} -> {after_bytes / 1024**2:.2f} MiB", flush=True)
        verify_originals(work)
        for directory, _, original_hashes in prepared:
            if {path.name: digest(path) for path in directory.iterdir() if path.is_file()} != original_hashes:
                raise ValueError(f"Livery changed while 1K files were staged: {directory}")
        committed = []
        try:
            for directory, destination, _ in prepared:
                backup = staging / (directory.name + ".original")
                directory.rename(backup)
                committed.append((directory, backup))
                destination.rename(directory)
        except BaseException:
            for directory, backup in reversed(committed):
                if directory.exists():
                    shutil.rmtree(directory)
                backup.rename(directory)
            raise
    (work / "resize-1024.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS 1K livery files published; high-resolution sources and original textures preserved")


def build(work: Path, parts: list[str] | None) -> None:
    verify_originals(work)
    for name in LIVERY_NAMES.values():
        directory = ROOT / "Liveries" / "KC-390" / name
        manifest = directory / "build.json"
        if directory.exists() and not manifest.exists():
            raise ValueError(f"Refusing to overwrite an unowned livery: {directory}")
        if manifest.exists():
            for part in json.loads(manifest.read_text(encoding="utf-8"))["parts"].values():
                for metadata in part["maps"].values():
                    path = directory / (metadata["texture"] + ".dds")
                    if not path.is_file() or digest(path) != metadata["sha256"]:
                        raise ValueError(f"Generated texture has external edits; preserve it before rebuilding: {path}")
    original = load_livery(ROOT / "Liveries" / "KC-390" / "FAB Standard" / "description.lua")
    selected = sorted({binding["texture"] for binding in original if binding["slot"] == 0 and (
        (binding["texture"].endswith("_c") and not any(token in binding["texture"] for token in ("flightdeck", "cargo")))
        or binding["texture"] in ("gold_t", "glass_s")
    )})
    if parts:
        if not set(parts).issubset(selected):
            raise ValueError(f"Unknown parts: {set(parts) - set(selected)}")
        selected = [name for name in selected if name in parts]
    marks = brandmarks(work)
    for label, image in marks.items():
        image.save(work / f"reference-{label}-mark.png")
    for variant in LIVERY_NAMES:
        folder = ROOT / "Liveries" / "KC-390" / LIVERY_NAMES[variant]
        ownership = folder / "build.json"
        if folder.exists() and not ownership.is_file():
            raise ValueError(f"Refusing to overwrite an unowned livery: {folder}")
        folder.mkdir(parents=True, exist_ok=True)
        previous = json.loads(ownership.read_text(encoding="utf-8")) if ownership.exists() else {"parts": {}}
        ownership.write_text(json.dumps(previous, indent=2), encoding="utf-8")
        for name in selected:
            source_path = ROOT / "Textures" / f"{name}.dds"
            with Image.open(source_path) as original_image:
                original_image.load()
                source = original_image.convert("RGBA")
            if name in ("gold_t", "glass_s"):
                colour = Image.new("RGBA", source.size, (43, 57, 61, 255))
                colour.putalpha(source.getchannel("A"))
                maps = {"colour": colour, "normal": Image.new("RGB", (4, 4), (128, 128, 255)), "roughmet": Image.new("RGB", (128, 128), (255, 28, 0))}
            else:
                maps = paint_maps(source, name, variant, clean_identity=True)
            colour_size = (4096, 4096) if name in MARKINGS else source.size
            base = maps["colour"].resize(colour_size, Image.Resampling.LANCZOS)
            decals = identity_layer(name, colour_size, variant, marks)
            merged = Image.alpha_composite(base, decals)
            merged.putalpha(base.getchannel("A"))
            maps["colour"] = merged
            maps["roughmet"] = ImageOps.contain(maps["roughmet"], (1024, 1024), Image.Resampling.BOX)
            directory = work / "sources" / variant / name
            directory.mkdir(parents=True, exist_ok=True)
            save_source(directory / f"{name}.ora", source, base, decals, merged)
            outputs = {}
            for role in ("colour", "normal", "roughmet"):
                filename = f"kc390_{variant}_{name}_{role}"
                png = directory / f"{filename}.png"
                maps[role].save(png)
                dds = export_dds(png, folder, role, work / "texconv.exe")
                outputs[role] = {"texture": filename, **dds_info(dds)}
            previous["parts"][name] = {"source_sha256": digest(source_path), "maps": outputs}
            ownership.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")
            print(f"PASS {variant} {name}: colour {merged.width}x{merged.height}, 3 DDS maps, editable layers", flush=True)
        bindings = []
        for binding in original:
            replacement = previous["parts"].get(binding["texture"]) if binding["slot"] == 0 else None
            if replacement:
                for slot, role in ((0, "colour"), (1, "normal"), (13, "roughmet")):
                    bindings.append({"material": binding["material"], "slot": slot, "texture": replacement["maps"][role]["texture"], "shared": False})
            else:
                bindings.append(binding)
        bindings = limit_shared_textures(work, variant, folder, bindings, previous)
        previous["max_texture_size"] = MAX_TEXTURE_SIZE
        ownership.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")
        write_livery(folder / "description.lua", bindings, LIVERY_NAMES[variant])
        if load_livery(folder / "description.lua") != bindings:
            raise ValueError("Generated Lua bindings did not round-trip")
    verify_originals(work)
    print("PASS original textures and FAB livery unchanged; model changes tracked separately", flush=True)


def validate_liveries(work: Path) -> dict:
    verify_originals(work)
    report = {}
    for variant, name in LIVERY_NAMES.items():
        directory = ROOT / "Liveries" / "KC-390" / name
        manifest = json.loads((directory / "build.json").read_text(encoding="utf-8"))
        bindings = load_livery(directory / "description.lua")
        dcs_lua = Path(os.environ.get("DCS_INSTALL", "D:/Program Files/DCS World")) / "bin" / "luae.exe"
        if dcs_lua.is_file() and load_livery(directory / "description.lua", str(dcs_lua)) != bindings:
            raise ValueError(f"Livery bindings differ in DCS Lua 5.1: {name}")
        seen = set()
        for binding in bindings:
            key = (binding["material"], binding["slot"])
            if key in seen:
                raise ValueError(f"Duplicate material binding: {name} {key}")
            seen.add(key)
            texture = (ROOT / "Textures" if binding["shared"] else directory) / (binding["texture"] + ".dds")
            if not texture.is_file():
                raise ValueError(f"Missing texture: {texture}")
            dimensions = dds_info(texture)
            if max(dimensions["width"], dimensions["height"]) > MAX_TEXTURE_SIZE:
                raise ValueError(f"Livery references a texture above {MAX_TEXTURE_SIZE}: {texture}")
        total = 0
        for part, record in manifest["parts"].items():
            if digest(ROOT / "Textures" / (part + ".dds")) != record["source_sha256"]:
                raise ValueError(f"Source texture changed: {part}")
            for role, metadata in record["maps"].items():
                path = directory / (metadata["texture"] + ".dds")
                actual = dds_info(path)
                if any(actual[field] != metadata[field] for field in actual):
                    raise ValueError(f"Generated texture changed: {path}")
                with Image.open(path) as image:
                    image.load()
                total += actual["bytes"]
            source = work / "sources" / variant / part / (part + ".ora")
            with zipfile.ZipFile(source) as archive:
                if archive.testzip() is not None:
                    raise ValueError(f"Invalid layered source: {source}")
                tree = ET.fromstring(archive.read("stack.xml"))
                if len(tree.findall("./stack/layer")) != 3:
                    raise ValueError(f"Missing source layers: {source}")
        for part, metadata in manifest.get("shared_overrides", {}).items():
            if digest(ROOT / "Textures" / (part + ".dds")) != metadata["source_sha256"]:
                raise ValueError(f"Shared source texture changed: {part}")
            path = directory / (metadata["texture"] + ".dds")
            actual = dds_info(path)
            if any(actual[field] != metadata[field] for field in actual):
                raise ValueError(f"Shared texture override changed: {path}")
            with Image.open(path) as image:
                image.load()
            total += actual["bytes"]
        report[variant] = {"name": name, "parts": len(manifest["parts"]), "shared_overrides": len(manifest.get("shared_overrides", {})), "dds_count": len(list(directory.glob("*.dds"))), "bindings": len(bindings), "texture_mib": round(total / 1024 ** 2, 2), "max_texture_size": MAX_TEXTURE_SIZE, "dcs_lua_checked": dcs_lua.is_file(), "dcs_visual_validation": "pending"}
    (work / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def deploy(work: Path) -> None:
    validate_liveries(work)
    target = Path.home() / "Saved Games" / "DCS" / "Mods" / "aircraft" / "KC-390"
    if not (target / "entry.lua").is_file():
        raise ValueError("The installed KC-390 was not found")
    baseline = json.loads((work / "baseline.json").read_text(encoding="utf-8"))
    for relative in baseline["protected"]:
        if not relative.endswith(".edm"):
            continue
        path = ROOT / relative
        if digest(path) != digest(target / "Shapes" / path.name):
            raise ValueError("The installed model differs from the tested model")
    state_path = work / "deployment.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"target": str(target), "files": {}}
    if Path(state["target"]) != target:
        raise ValueError("Deployment target differs from the recorded installation")
    planned = []
    for name in LIVERY_NAMES.values():
        relative_directory = Path("Liveries") / "KC-390" / name
        source_directory = ROOT / relative_directory
        destination_directory = target / relative_directory
        if destination_directory.exists() and not any(Path(relative).parent == relative_directory for relative in state["files"]):
            raise ValueError(f"Refusing to overwrite a pre-existing livery: {destination_directory}")
        for source in source_directory.iterdir():
            if not source.is_file() or source.suffix not in (".dds", ".lua", ".json"):
                continue
            relative = source.relative_to(ROOT).as_posix()
            destination = target / relative
            if destination.exists() and (relative not in state["files"] or digest(destination) != state["files"][relative]):
                raise ValueError(f"Installed file has unowned changes: {destination}")
            planned.append((source, destination, relative))
    for source, destination, relative in planned:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        expected = digest(source)
        if digest(destination) != expected:
            raise ValueError(f"Deployment copy failed verification: {destination}")
        state["files"][relative] = expected
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"PASS deployed {len(planned)} files to two separate livery folders; originals untouched")


def prepare_dcs(work: Path) -> None:
    profile = Path.home() / "Saved Games" / "KC390_LiveryValidation"
    owner = profile / "kc390-livery-test.json"
    if profile.exists() and not owner.exists():
        raise ValueError("Refusing to reuse an unowned DCS test profile")
    for relative in ("Config", "Scripts/Hooks", "Logs", "Missions", "Mods/aircraft"):
        (profile / relative).mkdir(parents=True, exist_ok=True)
    normal = Path.home() / "Saved Games" / "DCS" / "Config" / "options.lua"
    backup = work / "normal-options-before-test.lua"
    if backup.exists() and digest(backup) != digest(normal):
        raise ValueError("The normal profile changed after the recorded pre-test snapshot")
    shutil.copy2(normal, backup)
    helper = (ROOT / "tools" / "livery_dcs.lua").as_posix()
    lua = "D:/Program Files/DCS World/bin/luae.exe"

    def serialize(path: Path, variable: str) -> bytes:
        code = f'print=function() end; assert(loadfile("{path.as_posix()}"))(); io.write("{variable} = " .. assert(loadfile("{helper}"))("serialize", {variable}) .. "\\n")'
        return subprocess.run([lua, "-e", code], check=True, capture_output=True).stdout

    options = normal.read_text(encoding="utf-8") + f'\nassert(loadfile("{helper}"))("options")\n'
    staged_options = work / "livery-test-options.lua"
    staged_options.write_text(options, encoding="utf-8")
    (profile / "Config" / "options.lua").write_bytes(serialize(staged_options, "options"))
    (profile / "Scripts" / "Export.lua").write_text(f'assert(loadfile("{helper}"))("export")\n', encoding="ascii")
    (profile / "Scripts" / "Hooks" / "livery-test.lua").write_text(f'assert(loadfile("{helper}"))("hook")\n', encoding="ascii")
    mission_path = profile / "Missions" / "KC390-Livery-Test.miz"
    with zipfile.ZipFile(ROOT / "Missions" / "QuickStart" / "KC-390 AI Test.miz") as original:
        mission = original.read("mission").decode("utf-8") + f'\nassert(loadfile("{helper}"))("mission")\n'
        staged = work / "livery-test-mission.lua"
        staged.write_text(mission, encoding="utf-8")
        baked_mission = serialize(staged, "mission")
        for path in (staged, staged_options, profile / "Config" / "options.lua"):
            result = subprocess.run([lua, str(path)], check=True, capture_output=True, text=True)
            print(result.stdout.strip())
        with zipfile.ZipFile(mission_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for member in original.infolist():
                archive.writestr(member, baked_mission if member.filename == "mission" else original.read(member))
    state = {"profile": str(profile), "mission": str(mission_path), "normal_options_sha256": digest(normal), "helper_sha256": digest(ROOT / "tools" / "livery_dcs.lua")}
    owner.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2))


def texture_dimensions(size: tuple[int, int]) -> tuple[int, int]:
    width, height = size
    scale = min(1.0, MAX_TEXTURE_SIZE / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def export_dds(source: Path, output: Path, role: str, converter: Path) -> Path:
    formats = {"colour": "BC7_UNORM_SRGB", "normal": "BC5_UNORM", "roughmet": "BC7_UNORM"}
    with Image.open(source) as image:
        width, height = texture_dimensions(image.size)
    output.mkdir(parents=True, exist_ok=True)
    command = [str(converter), "-nologo", "-f", formats[role], "-dx10", "-w", str(width), "-h", str(height), "-if", "FANT", "-m", "0", "-y", "-o", str(output)]
    if role == "colour":
        command += ["-srgb", "-sepalpha"]
    command.append(str(source))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    destination = output / (source.stem + ".dds")
    metadata = dds_info(destination)
    expected = {"colour": 99, "normal": 83, "roughmet": 98}[role]
    if metadata["width"] != width or metadata["height"] != height or metadata["dxgi"] != expected or metadata["mipmaps"] != math.floor(math.log2(max(width, height))) + 1:
        raise ValueError(f"Incorrect DDS dimensions, encoding or mipmaps: {destination}")
    with Image.open(destination) as decoded:
        decoded.load()
    return destination


def sample(work: Path, dds: bool = False) -> None:
    name = "kc-390_fuselage_a1_c"
    path = ROOT / "Textures" / f"{name}.dds"
    baseline = json.loads((work / "baseline.json").read_text(encoding="utf-8"))
    if digest(path) != baseline["textures"][path.relative_to(ROOT).as_posix()]["sha256"]:
        raise ValueError("The original texture changed after audit")
    with Image.open(path) as source:
        source.load()
        previews = []
        for variant in ("fab", "embraer"):
            output = work / "sample" / variant
            output.mkdir(parents=True, exist_ok=True)
            maps = paint_maps(source, name, variant)
            for role, image in maps.items():
                image.save(output / f"{name}_{role}.png")
            if dds:
                livery = work / "preview-liveries" / "KC-390" / variant
                for role in ("colour", "normal", "roughmet"):
                    export_dds(output / f"{name}_{role}.png", livery, role, work / "texconv.exe")
                description = "livery = {\n"
                for slot, role in ((0, "colour"), (1, "normal"), (13, "roughmet")):
                    description += f'    {{"kc-390_fuselage a1", {slot}, "{name}_{role}", false}},\n'
                description += f'}}\nname = "KC390 Material Test {variant}"\ncountries = {{}}\n'
                (livery / "description.lua").write_text(description, encoding="ascii")
                print(f"PASS {variant}: colour BC7 sRGB, normal BC5 linear, RoughMet BC7 linear, maximum {MAX_TEXTURE_SIZE}px, full mipmaps")
            previews.append(output / f"{name}_colour.png")
            print(f"PASS {variant}: {source.width}x{source.height}, original alpha preserved, bounded normal, linear RoughMet")
        contact_sheet([path] + previews, work / "sample" / "comparison.png", 3)
    if digest(path) != baseline["textures"][path.relative_to(ROOT).as_posix()]["sha256"]:
        raise ValueError("Original texture was modified")


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def dds_info(path: Path) -> dict:
    with path.open("rb") as source:
        header = source.read(148)
    if header[:4] != b"DDS " or len(header) < 128:
        raise ValueError(f"Invalid DDS header: {path}")
    height, width = struct.unpack_from("<II", header, 12)
    mipmaps = struct.unpack_from("<I", header, 28)[0]
    fourcc = header[84:88].decode("ascii").rstrip("\0")
    return {
        "width": width,
        "height": height,
        "mipmaps": max(1, mipmaps),
        "fourcc": fourcc,
        "dxgi": struct.unpack_from("<I", header, 128)[0] if fourcc == "DX10" else None,
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def contact_sheet(paths: list[Path], output: Path, columns: int = 4) -> None:
    width, height = 400, 340
    sheet = Image.new("RGB", (columns * width, math.ceil(len(paths) / columns) * height), "#303236")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        with Image.open(path) as source:
            tile = ImageOps.contain(source.convert("RGB"), (width - 16, height - 50))
        left, top = index % columns * width, index // columns * height
        sheet.paste(tile, (left + (width - tile.width) // 2, top + 28))
        draw.text((left + 8, top + 7), path.stem, fill="white")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def audit(work: Path, reference: Path | None) -> None:
    work.mkdir(parents=True, exist_ok=True)
    inputs = sorted((ROOT / "Textures").glob("*.dds"))
    textures = {}
    for path in inputs:
        record = dds_info(path)
        with Image.open(path) as source:
            source.load()
            if source.size != (record["width"], record["height"]):
                raise ValueError(f"DDS dimensions disagree: {path.name}")
            record["mode"] = source.mode
        textures[path.relative_to(ROOT).as_posix()] = record
    protected = [ROOT / "Shapes" / name for name in ("KC-390.edm", "KC-390_lod01.edm", "KC-390_lod02.edm", "KC-390_lod03.edm", "KC-390.lods")]
    protected.append(ROOT / "Liveries" / "KC-390" / "FAB Standard" / "description.lua")
    protected += [ROOT / "Entry" / "KC-390.lua", ROOT / "entry.lua"]
    baseline = {
        "textures": textures,
        "protected": {path.relative_to(ROOT).as_posix(): digest(path) for path in protected if path.is_file()},
    }
    baseline_path = work / "baseline.json"
    if baseline_path.exists():
        previous = json.loads(baseline_path.read_text(encoding="utf-8"))
        verify_originals(work)
        if previous["textures"] != baseline["textures"]:
            raise ValueError("Source changed since baseline. Use a new work directory; do not overwrite the baseline.")
    else:
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    exterior = [path for path in inputs if path.stem.endswith("_c") and "flightdeck" not in path.stem and "cargo" not in path.stem]
    contact_sheet(exterior, work / "original-exterior.png")
    for name in ("kc-390_fuselage_a1_c", "kc-390_fuselage_a2_c", "kc-390_fuselage_b_c", "kc-390_fuselage_a1_croughmet"):
        with Image.open(ROOT / "Textures" / f"{name}.dds") as source:
            ImageOps.contain(source.convert("RGB"), (2048, 2048)).save(work / f"{name}.png")
    if reference is not None:
        import pymupdf

        with pymupdf.open(reference) as document:
            for index, page in enumerate(document):
                page.get_pixmap(matrix=pymupdf.Matrix(1.2, 1.2), alpha=False).save(work / f"brochure-{index + 1:02d}.png")
            print(f"PDF: {len(document)} pages rendered")
    sizes = {}
    for record in textures.values():
        key = f"{record['width']}x{record['height']} {record['fourcc'] or 'RGB'}"
        sizes[key] = sizes.get(key, 0) + 1
    print(json.dumps({"textures_decoded": len(textures), "formats": sizes, "baseline": str(baseline_path), "preview": str(work / "original-exterior.png")}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproducible KC-390 livery production and validation.")
    parser.add_argument("command", choices=("audit", "sample", "build", "resize", "validate", "deploy", "prepare-dcs"))
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--dds", action="store_true")
    parser.add_argument("--part", nargs="+")
    arguments = parser.parse_args()
    if arguments.command == "audit":
        audit(arguments.work, arguments.reference)
    elif arguments.command == "sample":
        sample(arguments.work, arguments.dds)
    elif arguments.command == "build":
        build(arguments.work, arguments.part)
    elif arguments.command == "resize":
        resize_liveries(arguments.work)
    elif arguments.command == "validate":
        validate_liveries(arguments.work)
    elif arguments.command == "deploy":
        deploy(arguments.work)
    elif arguments.command == "prepare-dcs":
        prepare_dcs(arguments.work)


if __name__ == "__main__":
    main()