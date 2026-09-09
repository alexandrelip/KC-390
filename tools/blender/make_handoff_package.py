"""Gera o pacote de entrega do KC-390 (Blender + FBX) para abrir em outra maquina.

Uso (Blender 5.1):
    blender.exe --background "D:\\Desenvolvimento\\KC-390\\kc-390\\kc-390.blend" ^
            --python make_handoff_package.py

O script:
    * copia as 83 texturas DCS autoritativas para <saida>\\Blender\\textures
    * reaponta as imagens para caminhos relativos (//textures/...)
    * salva a fonte portatil antes das conversoes DCS
    * aplica a mesma orientacao e os mesmos bindings de animacao do exportador EDM
    * marca a timeline DCS (0 / 100 / 200) e salva KC-390_animado.blend
  * exporta KC-390_animado.fbx com as animacoes bakeadas (para 3ds Max)
  * grava animacoes.json com o mapa argumento DCS -> objetos
"""

from __future__ import annotations

import bpy
import json
import os
import re
import shutil
import sys
import traceback
from pathlib import Path

OUT_ROOT = Path(r"D:\down\kc390tudo")
BLENDER_DIR = OUT_ROOT / "Blender"
TEX_DIR = BLENDER_DIR / "textures"
FBX_DIR = OUT_ROOT / "FBX"
FBX_TEXTURE_DIR = FBX_DIR / "KC-390_animado.fbm"
OUT_SOURCE_BLEND = BLENDER_DIR / "KC-390_fonte_editavel.blend"
OUT_BLEND = BLENDER_DIR / "KC-390_animado.blend"
OUT_FBX = FBX_DIR / "KC-390_animado.fbx"
REPORT = OUT_ROOT / "animacoes.json"
SOURCE_TEXTURE_DIR = Path(r"D:\Desenvolvimento\KC-390\Textures")
PIPELINE_ROOT = Path(r"D:\Desenvolvimento\MIGRACAOMSFSTODCS")
CONFIG_PATH = PIPELINE_ROOT / "config" / "models" / "kc390.json"
DEFAULTS_PATH = PIPELINE_ROOT / "config" / "defaults.json"

FRAME_START = 0
FRAME_END = 200
FRAME_NEUTRAL = 100


def log(msg: str) -> None:
    print(f"KC390_HANDOFF: {msg}")


def used_material_images() -> set[str]:
    used: set[str] = set()
    for material in bpy.data.materials:
        if not material.use_nodes or not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                used.add(node.image.name)
    return used


def relocate_textures() -> dict:
    if not SOURCE_TEXTURE_DIR.is_dir():
        raise FileNotFoundError(f"pasta de texturas ausente: {SOURCE_TEXTURE_DIR}")

    if TEX_DIR.exists():
        shutil.rmtree(TEX_DIR)
    TEX_DIR.mkdir(parents=True)
    source_textures = {
        path.name.lower(): path
        for path in SOURCE_TEXTURE_DIR.iterdir()
        if path.is_file()
    }
    textures_by_stem: dict[str, list[Path]] = {}
    for source in source_textures.values():
        textures_by_stem.setdefault(source.stem.lower(), []).append(source)
    for source in source_textures.values():
        shutil.copy2(source, TEX_DIR / source.name)

    used = used_material_images()
    relinked = 0
    missing_used: list[str] = []
    unresolved_unused: list[str] = []
    for image in bpy.data.images:
        if image.source not in {"FILE", "SEQUENCE"} or not image.filepath:
            continue

        raw_source = Path(bpy.path.abspath(image.filepath))
        source = source_textures.get(Path(image.filepath).name.lower())
        source = source or source_textures.get(image.name.lower())
        stem_matches = textures_by_stem.get(Path(image.filepath).stem.lower(), [])
        if source is None and len(stem_matches) == 1:
            source = stem_matches[0]
        if source is None and raw_source.is_file():
            source = raw_source
            shutil.copy2(source, TEX_DIR / source.name)

        if source is None:
            detail = f"{image.name} ({image.filepath})"
            if image.name in used:
                missing_used.append(detail)
            else:
                unresolved_unused.append(detail)
            continue

        image.filepath = f"//textures/{source.name}"
        try:
            image.reload()
        except RuntimeError as exc:  # imagem invalida no disco
            if image.name in used:
                missing_used.append(f"{image.name}: {exc}")
                continue
        relinked += 1

    if missing_used:
        raise RuntimeError(f"texturas usadas sem arquivo: {missing_used}")
    return {
        "copied": len(source_textures),
        "relinked": relinked,
        "unresolved_unused": unresolved_unused,
    }


def prepare_dcs_scene():
    sys.path.insert(0, str(PIPELINE_ROOT))
    from lib.manifest import load_config
    from lib import edm_common as edm

    cfg = load_config(str(CONFIG_PATH), str(DEFAULTS_PATH))
    export_cfg = cfg.get("export", {})

    # Register the EDM add-on because connector custom properties use its schema.
    edm.import_edm_descs()
    edm.anonymize(log, cfg.get("anon", []))
    edm.deskin(log)
    edm.remove_fx(log, export_cfg.get("fx_billboard_remove", []))
    edm.apply_world_rotation(log, export_cfg.get("world_rotation_deg_z", 0.0))
    edm.apply_object_offsets(log, cfg.get("object_offsets", []))
    edm.create_connectors(log, cfg.get("connectors", []))
    edm.normalize_weights(log)
    edm.cleanup_node_groups(log)
    edm.setup_lod_collection(
        log,
        f"{cfg.get('dcs', {}).get('type_name', 'KC-390')}_LOD_0_"
        f"{export_cfg.get('lod_collection_distance', 50000)}",
    )
    edm.rebind_external_anims(
        log,
        cfg.get("args", []),
        cfg.get("animation_bindings", []),
        export_cfg.get("static_frame", 0),
        export_cfg.get("neutral_frame", FRAME_NEUTRAL),
    )
    return cfg, edm


def prepare_fbx_materials(cfg: dict, edm) -> int:
    roles = cfg.get("textures", {}).get("roles", {})
    converted = 0
    for material in bpy.data.materials:
        textures = edm._collect_textures(material, roles)
        if not textures:
            continue

        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        output = nodes.new(type="ShaderNodeOutputMaterial")
        output.location = (700, 0)
        principled = nodes.new(type="ShaderNodeBsdfPrincipled")
        principled.location = (400, 0)
        material.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        def image_node(role: str, y: int):
            image = textures.get(role)
            if image is None:
                return None
            node = nodes.new(type="ShaderNodeTexImage")
            node.image = image
            node.label = role.upper()
            node.location = (-400, y)
            return node

        base = image_node("base", 300)
        if base:
            material.node_tree.links.new(base.outputs["Color"], principled.inputs["Base Color"])

        emissive = image_node("emissive", 100)
        emission_input = principled.inputs.get("Emission Color") or principled.inputs.get("Emission")
        if emissive and emission_input:
            material.node_tree.links.new(emissive.outputs["Color"], emission_input)

        normal = image_node("normal", -100)
        if normal:
            normal_map = nodes.new(type="ShaderNodeNormalMap")
            normal_map.location = (100, -100)
            material.node_tree.links.new(normal.outputs["Color"], normal_map.inputs["Color"])
            material.node_tree.links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])

        image_node("rmo", -300)
        converted += 1

    log(f"materiais preparados para FBX={converted}")
    return converted


def collect_animation_map(cfg: dict) -> dict:
    args: dict[int, list[str]] = {}
    invalid_actions: list[str] = []
    for obj in bpy.data.objects:
        action = obj.animation_data.action if obj.animation_data else None
        if not action:
            continue
        match = re.match(r"^(\d+)_", action.name)
        if not match:
            invalid_actions.append(f"{obj.name}: {action.name}")
            continue
        arg = int(match.group(1))
        args.setdefault(arg, []).append(obj.name)

    required_args = sorted({
        int(rule["arg"])
        for section in (cfg.get("args", []), cfg.get("animation_bindings", []))
        for rule in section
        if "arg" in rule
    })
    missing_args = sorted(set(required_args) - set(args))
    if invalid_actions:
        raise RuntimeError(f"acoes ativas sem argumento DCS: {invalid_actions[:10]}")
    if missing_args:
        raise RuntimeError(f"argumentos DCS obrigatorios ausentes: {missing_args}")

    return {
        "convencao_timeline": {
            "frame_0": "valor -1 do argumento DCS",
            "frame_100": "valor 0 (neutro)",
            "frame_200": "valor +1 do argumento DCS",
        },
        "total_objetos_animados": sum(len(v) for v in args.values()),
        "argumentos_obrigatorios": required_args,
        "argumentos": {str(k): sorted(v) for k, v in sorted(args.items())},
    }


def setup_timeline() -> None:
    scene = bpy.context.scene
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = 100
    scene.timeline_markers.clear()
    scene.timeline_markers.new("MIN (-1)", frame=FRAME_START)
    scene.timeline_markers.new("NEUTRO (0)", frame=FRAME_NEUTRAL)
    scene.timeline_markers.new("MAX (+1)", frame=FRAME_END)
    scene.frame_set(FRAME_NEUTRAL)


def main() -> None:
    for folder in (BLENDER_DIR, TEX_DIR, FBX_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    for stale_backup in BLENDER_DIR.glob("*.blend1"):
        stale_backup.unlink()

    texture_result = relocate_textures()
    log(
        f"texturas copiadas={texture_result['copied']} "
        f"imagens religadas={texture_result['relinked']} "
        f"nao usadas sem fonte={len(texture_result['unresolved_unused'])}"
    )

    setup_timeline()
    bpy.ops.wm.save_as_mainfile(
        filepath=str(OUT_SOURCE_BLEND),
        compress=True,
        relative_remap=False,
    )
    log(
        f"fonte editavel salva: {OUT_SOURCE_BLEND} "
        f"({OUT_SOURCE_BLEND.stat().st_size / 1024 / 1024:.1f} MB)"
    )

    cfg, edm = prepare_dcs_scene()
    setup_timeline()
    anim_map = collect_animation_map(cfg)
    log(f"objetos animados={anim_map['total_objetos_animados']} args={list(anim_map['argumentos'])}")

    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True, relative_remap=False)
    log(f"blend salvo: {OUT_BLEND} ({OUT_BLEND.stat().st_size / 1024 / 1024:.1f} MB)")

    if FBX_TEXTURE_DIR.exists():
        shutil.rmtree(FBX_TEXTURE_DIR)
    prepare_fbx_materials(cfg, edm)
    bpy.ops.export_scene.fbx(
        filepath=str(OUT_FBX),
        use_selection=False,
        apply_unit_scale=True,
        global_scale=1.0,
        apply_scale_options="FBX_SCALE_NONE",
        object_types={"EMPTY", "MESH"},
        mesh_smooth_type="FACE",
        use_mesh_modifiers=True,
        path_mode="COPY",
        embed_textures=False,
        bake_anim=True,
        bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        axis_forward="-Z",
        axis_up="Y",
    )
    FBX_TEXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for source in SOURCE_TEXTURE_DIR.iterdir():
        if source.is_file():
            shutil.copy2(source, FBX_TEXTURE_DIR / source.name)
    log(f"fbx exportado: {OUT_FBX} ({OUT_FBX.stat().st_size / 1024 / 1024:.1f} MB)")

    anim_map["fonte"] = str(Path(r"D:\Desenvolvimento\KC-390\kc-390\kc-390.blend"))
    anim_map["texturas_copiadas"] = texture_result["copied"]
    anim_map["imagens_religadas"] = texture_result["relinked"]
    anim_map["imagens_nao_usadas_sem_fonte"] = texture_result["unresolved_unused"]
    REPORT.write_text(json.dumps(anim_map, indent=2, ensure_ascii=False), encoding="utf-8")
    edm.cleanup_edm_registration()
    log("concluido")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
