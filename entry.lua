-- =====================================================================
--  Embraer KC-390 Millennium  -  MOD DE IA para DCS World
--  entry.lua  -  registro do plugin
-- ---------------------------------------------------------------------
--  Aeronave de transporte/reabastecimento APENAS IA (nao pilotavel).
--  Flight Model: SFM (Lua) - nao precisa de DLL.
--  Modelo 3D e animacoes convertidos com ModelConverterX + 3ds Max.
-- =====================================================================

local self_ID = "KC-390"

declare_plugin(self_ID,
{
    installed     = true,
    dirName       = current_mod_path,
    displayName   = _("KC-390 Millennium"),
    shortName     = "KC-390",
    fileMenuName  = _("KC-390 Millennium"),
    version       = "1.0.0",
    state         = "installed",
    developerName = "FABv / VS Mod",
    info          = _("Embraer KC-390 Millennium - cargueiro/tanker a jato (IA), convertido com permissao do autor."),

    Skins =
    {
        {
            name = _("KC-390 Millennium"),
            dir  = "Liveries",
        },
    },
})

-- Monta os caminhos virtuais do mod ------------------------------------
mount_vfs_liveries_path (current_mod_path .. "/Liveries")
mount_vfs_texture_path  (current_mod_path .. "/Textures")
mount_vfs_model_path    (current_mod_path .. "/Shapes")

-- Carrega o flight model (SFM) e depois a definicao da aeronave --------
dofile(current_mod_path .. "/KC-390_SFM.lua")
dofile(current_mod_path .. "/KC-390.lua")

plugin_done()
