local root = (arg[1] or "."):gsub("\\", "/"):gsub("/$", "") .. "/"
local shapes = (arg[2] or root .. "Shapes"):gsub("\\", "/"):gsub("/$", "") .. "/"
local environment = {
    _ = function(value) return value end,
    aircraft_task = function(value) return value end,
    verbose_to_dmg_properties = function(value) return value end,
    WSTYPE_PLACEHOLDER = 0, wsType_Air = 1, wsType_Airplane = 1,
    wsType_Cruiser = 1, FIXED_WING = 0, MODULATION_AM = 0,
    Transport = 1, Refueling = 2,
}
environment.add_aircraft = function(value) environment.registered = value end
local function load_config(path)
    local chunk
    if setfenv then
        chunk = assert(loadfile(root .. path))
        setfenv(chunk, environment)
    else
        chunk = assert(loadfile(root .. path, "t", environment))
    end
    chunk()
end
local function read_binary(path)
    local resolved = path:sub(1, 7) == "Shapes/" and shapes .. path:sub(8) or root .. path
    local file = assert(io.open(resolved, "rb"))
    local bytes = assert(file:read("*a"))
    assert(file:close())
    return bytes
end
local function finite(value)
    return type(value) == "number" and value == value and math.abs(value) < math.huge
end
load_config("Entry/KC-390_SFM.lua")
load_config("Entry/KC-390.lua")
load_config("Shapes/KC-390.lods")
local aircraft = assert(environment.registered)
assert(aircraft == environment.KC_390 and aircraft.Name == "KC-390")
assert(aircraft.shape_table_data[1].life == 20, "Expected Hercules-equivalent baseline: 20 HP")
assert(aircraft.shape_table_data[1].desrt == aircraft.shape_table_data[2].name)
assert(aircraft.shape_table_data[2].file == "C-130-oblomok", "Expected native C-130 wreck")
assert(aircraft.M_nominal == aircraft.M_empty + aircraft.M_fuel_max)
assert(aircraft.M_max > aircraft.M_nominal and aircraft.engines_count == 2)
assert(aircraft.SFM_Data == environment.KC390_SFM)
assert(aircraft.propellorShapeType == "1ARG_2PHASE", "Native fan controller must be enabled")
assert(aircraft.SFM_Data.engine.type == "TurboFan" and aircraft.SFM_Data.engine.Nominal_Fan_RPM > 0, "Fan RPM must be defined")
for _, row in ipairs(aircraft.SFM_Data.aerodynamics.table_data) do
    assert(#row == 8, "SFM aerodynamics schema")
end
assert(#aircraft.Tasks == 2 and aircraft.Tasks[1] == environment.Transport and aircraft.Tasks[2] == environment.Refueling)
assert(aircraft.is_tanker and aircraft.refueling_points_count == 2 and #aircraft.refueling_points == 2)
assert(aircraft.DefaultTask == environment.Refueling)
assert(aircraft.Sensors.RWR == "Abstract RWR" and not aircraft.Sensors.OPTIC and not aircraft.Sensors.IRST)
local countermeasures = aircraft.passivCounterm
assert(countermeasures.CMDS_Edit and countermeasures.SingleChargeTotal == 120)
assert(countermeasures.chaff.default * countermeasures.chaff.chargeSz + countermeasures.flare.default * countermeasures.flare.chargeSz == countermeasures.SingleChargeTotal)
assert(#aircraft.chaff_flare_dispenser == 4 and #aircraft.fires_pos == 11)
for _, dispenser in ipairs(aircraft.chaff_flare_dispenser) do
    assert(#dispenser.pos == 3 and #dispenser.dir == 3)
    local direction_length = 0
    for _, coordinate in ipairs(dispenser.dir) do
        assert(finite(coordinate))
        direction_length = direction_length + coordinate * coordinate
    end
    assert(math.abs(direction_length - 1) < 0.00001)
end
local animated = {}
assert(#aircraft.net_animation == 24 and #aircraft.net_animation <= 32)
for _, argument in ipairs(aircraft.net_animation) do
    assert(not animated[argument], "Duplicate network argument")
    animated[argument] = true
end
assert(animated[42] and animated[71], "Refueling hoses must replicate")
assert(animated[407] and animated[408], "Native engine fan rotation arguments must replicate")
local model = assert(environment.model)
assert(#model.lods == 4 and model.collision_shell == "KC-390_collision.edm")
local collision = read_binary("Shapes/" .. model.collision_shell)
assert(collision:find("model::ShellNode", 1, true), "Missing physical collision nodes")
local damage = assert(aircraft.Damage)
local count = 0
local damage_arguments, fragments = {}, {}
local fragment_ids = { NOSE_CENTER = 0, WING_L_IN = 35, WING_R_IN = 36, TAIL_BOTTOM = 58 }
local function visit(name, visiting)
    assert(not visiting[name], "Damage dependency cycle: " .. name)
    local cell = assert(damage[name], "Undefined damage cell: " .. name)
    visiting[name] = true
    for _, dependency in ipairs(cell.deps_cells or {}) do visit(dependency, visiting) end
    visiting[name] = nil
end
for name, cell in pairs(damage) do
    count = count + 1
    assert(finite(cell.critical_damage) and cell.critical_damage > 0, name)
    assert(collision:find(name, 1, true), "Missing physical damage cell: " .. name)
    assert(type(cell.args) == "table" and #cell.args == 1, "Missing damage argument: " .. name)
    local argument = cell.args[1]
    assert(argument >= 140 and argument <= 179 and argument % 1 == 0, "Invalid damage argument: " .. name)
    assert(not damage_arguments[argument] and not animated[argument], "Conflicting damage argument: " .. name)
    damage_arguments[argument] = name
    if cell.droppable then
        assert(fragment_ids[name] and aircraft.DamageParts[1000 + fragment_ids[name]] == cell.droppable_shape, "Fragment ID mismatch: " .. name)
        assert(#read_binary("Shapes/" .. cell.droppable_shape .. ".edm") > 0, "Missing damage fragment: " .. name)
        fragments[name] = true
    else
        assert(not cell.droppable_shape, "Unreachable fragment: " .. name)
    end
    visit(name, {})
    local right = name:gsub("_L_", "_R_"):gsub("_L$", "_R"):gsub("LEFT_", "RIGHT_")
    if right ~= name then
        assert(damage[right] and damage[right].critical_damage == cell.critical_damage, "Asymmetric damage: " .. name)
        local dependencies = {}
        for _, dependency in ipairs(damage[right].deps_cells or {}) do dependencies[dependency] = true end
        for _, dependency in ipairs(cell.deps_cells or {}) do
            local mirrored = dependency:gsub("_L_", "_R_"):gsub("_L$", "_R"):gsub("LEFT_", "RIGHT_")
            assert(dependencies[mirrored], "Asymmetric dependency: " .. name)
        end
    end
end
assert(count == 40, "Expected 40 damage cells")
for name in pairs(fragment_ids) do assert(fragments[name], "Missing droppable cell: " .. name) end
for _, lod in ipairs(model.lods) do
    local visual = read_binary("Shapes/" .. lod[1])
    for argument, name in pairs(damage_arguments) do
        assert(visual:find("KC390_DAMAGE_" .. argument .. "_", 1, true), "Missing visual damage control: " .. lod[1] .. " " .. name)
    end
end
print("PASS: 20 HP, 40 physical/visual damage cells, four fragments, native wreck, SFM, transport/tanker tasks and network arguments (" .. _VERSION .. ")")