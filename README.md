# DCS World Embraer KC-390 Millennium

> Free, open-source **AI-only KC-390 Millennium** independent module for DCS World.
>
> **Development note:** Project under development for playable SFM and, in the future, EFM.

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
- Damage configuration: 20 base HP, matching the Hercules 6.8.2 mod, and 40 distinct native component damage cells
- Dedicated animated collision geometry for the fuselage, engines, wings, tail, controls and landing gear
- Forty damage arguments (140-179) in every visual LOD, with component visibility removed at complete damage
- KC-390 nose, left wing, right wing and cargo-ramp fragments, plus the native C-130 final wreck used by Hercules
- RWR, an editable load of 60 chaff / 60 flares, four dispenser positions and component fire positions
- Landing gear, control surfaces, ramp/doors, mirrors and animated refueling hoses/baskets (24 animation args)
- Continuous engine fan rotation driven by native DCS arguments 407/408 in all four visual LODs
- Network replication configured for all 24 animation arguments, including both refueling hoses
- Custom liveries (FAB Standard) and in-game theme (loading screen, ME icon, logo)
- 4 LODs (0/8/20/50 km) with dedicated collision shell

HP, component thresholds, countermeasure capacity and dispenser/fire positions are simulator approximations, not certified real-world specifications. Aircraft tasks and defensive reactions use the native DCS AI and Mission Editor options. There is no custom cockpit, offensive targeting sensor or external flight-model DLL. Existing missions retain the countermeasure quantities saved in their payloads; set a nonzero load in the Mission Editor to equip them.

Damage geometry and fragments come from the KC-390 itself; no Hercules model or texture is copied. The visual builder preserves all original triangles, vertex positions, normals, UVs, materials, flight animations and refueling connectors, changing only damage grouping and adding visibility controls. Each fragment uses the aircraft's original coordinates and a frozen neutral pose. There are no newly painted scorch textures or modeled fracture interiors. The final wreck references the installed DCS asset `C-130-oblomok`, not a custom KC-390 wreck.

The configuration follows the Hercules feature set, not its asymmetric thresholds or alias collisions. Left/right component thresholds remain symmetric, all 40 cells have explicit finite thresholds, and the KC-390 retains two engines and its existing SFM.

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

To update an existing local installation with this damage package, close DCS, its updater and ModelViewer2, then run:

```powershell
.\tools\Install-Damage.ps1 -WhatIf
.\tools\Install-Damage.ps1
```

The installer changes only the aircraft definition, nine damage-related models and the two documentation files. It checks hashes, saves a backup under `%LOCALAPPDATA%\KC390-Damage\Backups`, and never changes textures, liveries, SFM or normal DCS settings. Use `-Destination` for a different existing installation. To restore the backup path printed by the installer, run `.\tools\Install-Damage.ps1 -RestoreBackup '<backup path>'`; restoration refuses to overwrite later modifications.

## Validation

Local configuration check with DCS Lua 5.1, from the mod directory:

```powershell
& 'D:\Program Files\DCS World\bin\luae.exe' .\tools\check_ai.lua .
```

Native simulator checks:

```powershell
.\tools\validate_ai.ps1 -Scenario Damage
.\tools\validate_ai.ps1 -Scenario Damage -Render
.\tools\validate_ai.ps1 -Scenario Takeoff
.\tools\validate_ai.ps1 -Scenario Fans
.\tools\validate_ai.ps1 -Scenario Missile -MissileSystem Tor
.\tools\validate_ai.ps1 -Scenario Missile -MissileSystem Strela10
```

The `Missile` scenario uses native DCS AI missile launches, not scripted explosions. It requires an identified missile shot, an attributed hit on the KC-390, launcher ammunition consumption, subsequent target damage/loss, and an unattacked KC-390 retaining 20 HP and zero damage arguments while flying. The test aircraft alone carries no chaff/flares, so this checks damage rather than countermeasure effectiveness. Radar (`Tor`) and infrared (`Strela10`) cases run separately. Screenshots are observations requiring manual review; a physics PASS does not certify every fragment, all missile types, multiplayer or real-world survivability. The observer's six local positive/negative cases are in [tools/test_missile_observer.lua](tools/test_missile_observer.lua).

The validator defaults to `bin-mt` and rejects native crash records even if DCS returns exit code zero. Camera positioning is limited to the initial interval before the launcher is armed; after that, native camera tracking is used. Only temporary-profile camera/capture scripts are created.

The validator creates a temporary profile, uses local authentication files without displaying their contents, saves logs and a hash manifest under the system temporary directory, and removes the profile and authentication copies in `finally`. Damage and takeoff tests run without rendering unless `-Render` is specified. Rendered damage validation additionally requires a native damage-argument change after an impact and zero damage arguments on the unattacked aircraft. This is not a screenshot or debris-trajectory check. `Fans` always enables rendering: DCS does not update these visual arguments in headless mode. Normal options are checked for changes; only the test process is stopped. Existing DCS sessions block the test unless `-AllowParallelDcs` is explicitly supplied. Use `-DcsRoot` / `-NormalProfile` for non-default installations.

The `Fans` scenario compares a flying aircraft against an uncontrolled cold parking aircraft in zero wind and a stock KC-135 reference. It requires sustained changes across arguments 407/408 in four successive intervals, at least 80% of the reference's update count, and no changes with the engines stopped. It also logs legacy arguments 21/22 to distinguish the original incorrect mapping. This is an argument-level test, not a visual certification.

The [fan remapper](tools/animate_fans.py) updates only the four fan rotation records in each visual EDM: native arguments 407/408, with a complete turn in each phase (-1 to 0 for slow rotation, 0 to 1 for fast rotation). Run it with `--importer` pointing to the installed `dcs_edm_importer` directory, `--source` pointing to `Shapes`, and `--output` pointing to a new staging directory. It checks complete parsing, closed full turns, unchanged geometry/materials/connectors, preservation of every byte outside the four rotation records, and idempotence before writing staged models and a hash manifest. The current correction adds 480 bytes per LOD and never overwrites the original files. Future visual exports must retain 407/408 and both phases. The collision-only builder is unaffected.

Native fan control requires `propellorShapeType = "1ARG_2PHASE"` and the SFM `TurboFan` type with nominal fan/core RPM. The configured 5650/14950 RPM values are visual simulation approximations, not certified V2500-E5 performance data. The aerodynamic and thrust tables are unchanged.

Current package: 20 HP, 40 distinct native IDs, symmetric dependencies and four indexed fragments. The four visual LODs preserve geometry/materials/flight animation records and declare argument capacity through 408, including damage arguments 140-179. The collision export has 40 cells, 278 shells and 24,869 triangles; its source blend was not modified. The current models were installed in Saved Games on 2026-09-22.

On 2026-09-23, two rendered native missile tests passed using the same aircraft files as the installed package: Tor/SA9M330 and Strela-10M3/SA9M333. Both recorded native missile launches, identified impacts, ammunition consumption and target loss, while an unattacked KC-390 retained 20 HP and zero damage arguments. Captures show an explosion and fragments for Tor, and front-section rupture followed by a burning fall and additional separation near ground contact for Strela. No scripted explosions or forced model arguments were used. DCS exited without detected crashes; normal options and source files were preserved, and temporary profiles/authentication copies were removed. See the [report and actual screenshots](tools/DamageValidation/2026-09-23/README.md). These cases do not certify every detachable part, every missile, multiplayer or countermeasure effectiveness.

Historical baseline only: on 2026-09-13, the previous 45-HP/30-cell package passed native explosion, Vulcan, navigation and cold-start takeoff checks in DCS 2.9.29.27468. Those results do not certify the new damage package.

The collision builder is [tools/build_collision.py](tools/build_collision.py). Run it with Blender 5.1 and the official `io_scene_edm` exporter, passing `--source`, `--addon`, `--report` and `--output` after Blender's `--` separator. It verifies that the source blend is unchanged and exports a separate collision EDM; it does not save over the source scene.

The visual/fragment builder is [tools/build_damage.py](tools/build_damage.py). Run with Blender 5.1 and `--importer <dcs_edm_importer> --source <intact Shapes snapshot> --output <new staging directory> --report <new JSON path>`. It shares the cell classifier with the collision builder. Rebuild from the intact pre-damage snapshot, not the already partitioned models, and retain the source hash manifest. The updated files must be deployed together with their matching aircraft definition. The fan remapper remains a pre-damage pipeline step.

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
