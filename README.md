# DCS World Embraer KC-390 Millennium

> Free, open-source **AI-only KC-390 Millennium** independent module for DCS World.

---

## Overview

This is a free, open-source **AI-only KC-390 Millennium** module for DCS World. "AI-only" means the aircraft is not player-flyable — it is added via `add_aircraft` for use as a mission asset (transport / aerial refueling tanker), driven by an SFM (Lua) flight model with no external DLL required.

The 3D model and animations were converted from the freeware MSFS "VS Mod" KC-390 (FABv / Vynicius) using ModelConverterX + 3ds Max, with permission from the original author.

### Licensing
- **Lua systems** — freely usable in other **non-paid** DCS World modules
- The original 3D model/textures are freeware from FABv / Vynicius "VS Mod" (MSFS); used here with the author's permission. Redistribution should preserve original credit.
- ⚠️ **This is a closed/restricted license**: any modification, redistribution, or derivative work (model, textures, code or assets) **requires prior written permission from the group of contributors** listed below. Do not fork, repackage, or alter this mod without asking first.

---

## Features

- AI-only transport aircraft (`add_aircraft`), no DLL required (SFM in Lua)
- AI tasks: `Transport` and `Refueling` (2 tanker points)
- Damage configuration: 45 base HP, matching the stock DCS C-130, and 30 finite component damage cells
- Dedicated animated collision geometry for the fuselage, engines, wings, tail, controls and landing gear
- RWR, an editable load of 60 chaff / 60 flares, four dispenser positions and component fire positions
- Landing gear, control surfaces, ramp/doors, mirrors and animated refueling hoses/baskets (24 animation args)
- Continuous engine fan rotation driven by native DCS arguments 407/408 in all four visual LODs
- Network replication configured for all 24 animation arguments, including both refueling hoses
- Custom liveries (FAB Standard) and in-game theme (loading screen, ME icon, logo)
- 4 LODs (0/8/20/50 km) with dedicated collision shell

HP, component thresholds, countermeasure capacity and dispenser/fire positions are simulator approximations, not certified real-world specifications. Aircraft tasks and defensive reactions use the native DCS AI and Mission Editor options. There is no custom cockpit, offensive targeting sensor or external flight-model DLL. Existing missions retain the countermeasure quantities saved in their payloads; set a nonzero load in the Mission Editor to equip them.

The physical model is generated from the original geometry without replacing the visual LODs or textures. Destruction is functional, but separate broken-wing and wreck models are not included.

---

## Compatibility

| DCS Version | KC-390 Millennium |
|---|---|
| Recent DCS World (2.9.x) | Supported |

---

## Installation

1. Copy this mod folder into your `Saved Games\DCS\Mods\aircraft\KC-390` (or use a junction pointing to wherever you keep the mod files — DCS only scans `Mods\aircraft` and `Mods\tech`).
2. Start DCS World; the KC-390 Millennium will appear in the Encyclopedia / Mission Editor as an AI-only unit.
3. Use it as `Transport` or `Refueling` (tanker) in the Mission Editor.

## Validation

Local configuration check with DCS Lua 5.1, from the mod directory:

```powershell
& 'D:\Program Files\DCS World\bin\luae.exe' .\tools\check_ai.lua .
```

Native simulator checks:

```powershell
.\tools\validate_ai.ps1 -Scenario Damage
.\tools\validate_ai.ps1 -Scenario Takeoff
.\tools\validate_ai.ps1 -Scenario Fans
```

The validator creates a temporary profile, uses local authentication files without displaying their contents, saves logs and a hash manifest under the system temporary directory, and removes the profile and authentication copies in `finally`. Damage and takeoff tests run without rendering unless `-Render` is specified. `Fans` always enables rendering: DCS does not update these visual arguments in headless mode. Normal options are checked for changes; only the test process is stopped. Existing DCS sessions block the test unless `-AllowParallelDcs` is explicitly supplied. Use `-DcsRoot` / `-NormalProfile` for non-default installations.

The `Fans` scenario compares a flying aircraft against an uncontrolled cold parking aircraft in zero wind and a stock KC-135 reference. It requires sustained changes across arguments 407/408 in four successive intervals, at least 80% of the reference's update count, and no changes with the engines stopped. It also logs legacy arguments 21/22 to distinguish the original incorrect mapping. This is an argument-level test, not a visual certification.

The [fan remapper](tools/animate_fans.py) updates only the four fan rotation records in each visual EDM: native arguments 407/408, with a complete turn in each phase (-1 to 0 for slow rotation, 0 to 1 for fast rotation). Run it with `--importer` pointing to the installed `dcs_edm_importer` directory, `--source` pointing to `Shapes`, and `--output` pointing to a new staging directory. It checks complete parsing, closed full turns, unchanged geometry/materials/connectors, preservation of every byte outside the four rotation records, and idempotence before writing staged models and a hash manifest. The current correction adds 480 bytes per LOD and never overwrites the original files. Future visual exports must retain 407/408 and both phases. The collision-only builder is unaffected.

Native fan control requires `propellorShapeType = "1ARG_2PHASE"` and the SFM `TurboFan` type with nominal fan/core RPM. The configured 5650/14950 RPM values are visual simulation approximations, not certified V2500-E5 performance data. The aerodynamic and thrust tables are unchanged.

Verified in DCS 2.9.29.27468 on 2026-09-13: both the KC-390 and stock C-130 started at 45 HP, small explosions reduced HP and subsequent damage destroyed them; native Vulcan rounds registered hits and destroyed the KC-390. An unattacked aircraft flew 11 km, consumed fuel and retained full HP. A separate cold parking start completed taxi and takeoff with 45 HP and retracted gear. These were headless physics tests, not visual or multiplayer certifications; flare effectiveness, new fire visuals and multiplayer replication have not been separately verified.

The collision builder is [tools/build_collision.py](tools/build_collision.py). Run it with Blender 5.1 and the official `io_scene_edm` exporter, passing `--source`, `--addon`, `--report` and `--output` after Blender's `--` separator. It verifies that the source blend is unchanged and exports a separate collision EDM; it does not save over the source scene.

---

## 🤝 Contributors

**Core development & DCS conversion**: alexandrelip

**Original 3D model / textures (MSFS "VS Mod", freeware)**: vynicius (FABv)

**Support, testing & feedback**: suak007, carlos, denis, Filipe, Giovanny

And everyone in the community who reported bugs, provided feedback, and helped shape this project. ❤️

---

## 📜 License

This project is shared with the DCS World modding community under the following terms:

- **Lua-based aircraft systems** — freely usable in other **non-paid** DCS World modules
- The original 3D model and textures are based on the freeware MSFS **KC-390 "VS Mod"** by FABv / Vynicius, converted and adapted with the author's permission. Livery and texture contributions belong to their respective authors.
- 🔒 **Permission required for changes**: this is a restricted license. **Any change, modification, or redistribution of this mod requires explicit prior permission from the contributor group** (see [Contributors](#-contributors)). Unauthorized forks/reuploads/edits are not permitted.

---

**Português (resumo)**: Mod de IA (não pilotável) gratuito e open-source do Embraer KC-390 Millennium para DCS World. Modelo 3D convertido do mod freeware de MSFS "VS Mod" (FABv/Vynicius), com permissão do autor original. Flight Model em SFM (Lua), sem necessidade de DLL. Tarefas de IA: `Transport` e `Refueling` (reabastecedor com 2 pontos).

⚠️ **Licença restrita**: qualquer alteração, modificação ou redistribuição deste mod (modelo, texturas, código ou demais assets) **exige permissão prévia do grupo de colaboradores** listado abaixo. Não é permitido fork, republicação ou edição sem autorização.

### 🤝 Colaboradores

**Desenvolvimento principal & conversão para DCS**: alexandrelip

**Modelo 3D / texturas originais (MSFS "VS Mod", freeware)**: vynicius (FABv)

**Suporte, testes e feedback**: suak007, carlos, denis, Filipe, Giovanny

E todos na comunidade que reportaram bugs, deram feedback e ajudaram a moldar este projeto. ❤️
