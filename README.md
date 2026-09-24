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
