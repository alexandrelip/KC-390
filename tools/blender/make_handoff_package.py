"""Gera o pacote de entrega do KC-390 (Blender + FBX) para abrir em outra maquina.

Uso (Blender 4.2):
  blender.exe --background "D:\\Desenvolvimento\\FSPARADCS\\DCS KC-390\\KC-390-blender.blend" ^
      --python make_handoff_package.py

O script:
  * copia todas as texturas usadas para <saida>\\Blender\\textures
  * reaponta as imagens para caminhos RELATIVOS (//textures/...)
  * marca a timeline DCS (0 / 100 / 200) e salva KC-390_animado.blend
  * exporta KC-390_animado.fbx com as animacoes bakeadas (para 3ds Max)
  * grava animacoes.json com o mapa argumento DCS -> objetos
"""

from __future__ import annotations

import bpy
import json
import shutil
from pathlib import Path

OUT_ROOT = Path(r"D:\down\kc390tudo")
BLENDER_DIR = OUT_ROOT / "Blender"
TEX_DIR = BLENDER_DIR / "textures"
FBX_DIR = OUT_ROOT / "FBX"
OUT_BLEND = BLENDER_DIR / "KC-390_animado.blend"
OUT_FBX = FBX_DIR / "KC-390_animado.fbx"
REPORT = OUT_ROOT / "animacoes.json"

FRAME_START = 0
FRAME_END = 200
FRAME_NEUTRAL = 100


def log(msg: str) -> None:
    print(f"KC390_HANDOFF: {msg}")


def relocate_textures() -> tuple[int, list[str]]:
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    missing: list[str] = []
    for image in bpy.data.images:
        if image.source not in {"FILE", "SEQUENCE"} or not image.filepath:
            continue
        src = Path(bpy.path.abspath(image.filepath))
        name = src.name or image.name
        dst = TEX_DIR / name
        if src.is_file():
            if not dst.exists() or src.stat().st_size != dst.stat().st_size:
                shutil.copy2(src, dst)
            copied += 1
        elif not dst.exists():
            missing.append(image.name)
            continue
        image.filepath = f"//textures/{name}"
        try:
            image.reload()
        except RuntimeError as exc:  # imagem invalida no disco
            missing.append(f"{image.name}: {exc}")
    return copied, missing


def collect_animation_map() -> dict:
    args: dict[str, list[str]] = {}
    for obj in bpy.data.objects:
        action = obj.animation_data.action if obj.animation_data else None
        if not action:
            continue
        arg = action.name.split("_", 1)[0]
        args.setdefault(arg, []).append(obj.name)
    return {
        "convencao_timeline": {
            "frame_0": "valor -1 do argumento DCS",
            "frame_100": "valor 0 (neutro)",
            "frame_200": "valor +1 do argumento DCS",
        },
        "total_objetos_animados": sum(len(v) for v in args.values()),
        "argumentos": {k: sorted(v) for k, v in sorted(args.items(), key=lambda kv: int(kv[0]))},
    }


def main() -> None:
    for folder in (BLENDER_DIR, TEX_DIR, FBX_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    copied, missing = relocate_textures()
    log(f"texturas copiadas={copied} problemas={len(missing)}")
    if missing:
        log(f"texturas com problema: {missing[:10]}")

    scene = bpy.context.scene
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = 100
    scene.timeline_markers.clear()
    scene.timeline_markers.new("MIN (-1)", frame=FRAME_START)
    scene.timeline_markers.new("NEUTRO (0)", frame=FRAME_NEUTRAL)
    scene.timeline_markers.new("MAX (+1)", frame=FRAME_END)
    scene.frame_set(FRAME_NEUTRAL)

    anim_map = collect_animation_map()
    log(f"objetos animados={anim_map['total_objetos_animados']} args={list(anim_map['argumentos'])}")

    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True, relative_remap=True)
    log(f"blend salvo: {OUT_BLEND} ({OUT_BLEND.stat().st_size / 1024 / 1024:.1f} MB)")

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
    log(f"fbx exportado: {OUT_FBX} ({OUT_FBX.stat().st_size / 1024 / 1024:.1f} MB)")

    anim_map["texturas_copiadas"] = copied
    anim_map["texturas_com_problema"] = missing
    REPORT.write_text(json.dumps(anim_map, indent=2, ensure_ascii=False), encoding="utf-8")
    log("concluido")


if __name__ == "__main__":
    main()
