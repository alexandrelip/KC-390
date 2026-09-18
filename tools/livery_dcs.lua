local mode = ...

if mode == "serialize" then
    local _, value = ...
    local function encode(item)
        if type(item) == "string" then return string.format("%q", item) end
        if type(item) == "number" or type(item) == "boolean" then return tostring(item) end
        assert(type(item) == "table", "Unexpected type in mission/options data")
        local keys, fields = {}, {}
        for key in pairs(item) do keys[#keys+1] = key end
        table.sort(keys, function(left, right)
            if type(left) ~= type(right) then return type(left) < type(right) end
            return left < right
        end)
        for _, key in ipairs(keys) do fields[#fields+1] = "[" .. encode(key) .. "]=" .. encode(item[key]) end
        return "{" .. table.concat(fields, ",") .. "}"
    end
    return encode(value)
end

if mode == "mission" then
    local names = {"FAB 2852 - Refinada", "Embraer Millennium - Cinza"}
    local template
    for _, coalition in pairs(mission.coalition) do
        for _, country in pairs(coalition.country or {}) do
            for _, group in pairs(country.plane and country.plane.group or {}) do
                if group.units[1].type == "KC-390" then template = group end
            end
        end
    end
    assert(template, "The existing KC-390 test mission has no KC-390 template")
    local function clone(value)
        if type(value) ~= "table" then return value end
        local result = {}
        for key, item in pairs(value) do result[key] = clone(item) end
        return result
    end
    local groups = {}
    for index, name in ipairs(names) do
        local group = clone(template)
        group.groupId = index
        group.name = "Livery Test " .. name
        group.task = "Transport"
        group.lateActivation = false
        group.uncontrolled = false
        group.units = {clone(template.units[1])}
        local unit = group.units[1]
        unit.unitId = index
        unit.name = name
        unit.livery_id = name
        unit.skill = "Excellent"
        unit.x = template.units[1].x + (index - 1) * 500
        unit.y = template.units[1].y
        unit.alt = 2500
        unit.heading = 0
        unit.psi = 0
        unit.speed = 150
        group.x, group.y = unit.x, unit.y
        group.route.points = {
            {x=unit.x, y=unit.y, alt=unit.alt, alt_type="BARO", speed=150, action="Turning Point", type="Turning Point", ETA=0, ETA_locked=true, speed_locked=true, task={id="ComboTask", params={tasks={}}}},
            {x=unit.x+30000, y=unit.y, alt=unit.alt, alt_type="BARO", speed=150, action="Turning Point", type="Turning Point", ETA=200, ETA_locked=false, speed_locked=true, task={id="ComboTask", params={tasks={}}}},
        }
        groups[index] = group
    end
    mission.coalition.red.country = {}
    mission.coalition.blue.country = {{id=11, name="Brazil", plane={group=groups}}}
    mission.coalition.neutrals.country = {}
    mission.trig = {actions={}, conditions={}, func={}, flag={}, custom={}}
    mission.trigrules = {}
    mission.start_time = 43200
    mission.forcedOptions = {externalViews=true, easyFlight=false, labels=0, unrestrictedSATNAV=false, optionsView="optview_all"}
    print("PASS mission: " .. mission.theatre .. ", two KC-390 units with distinct liveries")
    return
end

if mode == "options" then
    options.VR.enable = false
    options.miscellaneous.launcher = false
    options.miscellaneous.autologin = true
    options.difficulty.externalViews = true
    options.difficulty.spectatorExternalViews = true
    options.difficulty.labels = 0
    options.graphics.width = 1600
    options.graphics.height = 900
    options.graphics.aspect = 1600/900
    options.graphics.fullScreen = false
    options.graphics.Upscaling = "OFF"
    options.graphics.AA = "OFF"
    options.graphics.MSAA = 0
    options.graphics.textures = 2
    options.graphics.maxFPS = 30
    options.graphics.preloadRadius = 15000
    options.graphics.ScreenshotExt = "png"
    print("PASS options: isolated non-VR profile, 1600x900, native texture resolution")
    return
end

if mode == "hook" then
    local simulation = DCS or Sim
    local callbacks = {}
    function callbacks.onSimulationStart()
        if simulation.isServer() then simulation.setPause(false) end
        log.write("KC390_LIVERY_TEST", log.INFO, "SIMULATION_STARTED")
    end
    function callbacks.onSimulationFrame()
        if simulation.getModelTime() < 2 and simulation.getPause() then simulation.setPause(false) end
    end
    function callbacks.onMissionLoadEnd()
        log.write("KC390_LIVERY_TEST", log.INFO, "MISSION_LOADED")
    end
    simulation.setUserCallbacks(callbacks)
    return
end

local trace
local last_recorded = -1
local start_time

function LuaExportStart()
    trace = assert(io.open(lfs.writedir() .. "Logs/livery-camera.csv", "w"))
    trace:write("time,variant,object_id,object_name,camera_x,camera_y,camera_z,observed_x,observed_y,observed_z\n")
    LoSetCommand(114)
end

function LuaExportAfterNextFrame()
    local time = LoGetModelTime()
    start_time = start_time or time
    local elapsed = time - start_time
    local objects = LoGetWorldObjects()
    local targets = {}
    for identifier, object in pairs(objects or {}) do
        if object.Name == "KC-390" then targets[#targets+1] = {id=identifier, data=object} end
    end
    table.sort(targets, function(left, right) return left.id < right.id end)
    if #targets ~= 2 then return end
    local index = math.floor(elapsed / 12) % 2 + 1
    local object = targets[index].data
    local side = math.floor(elapsed / 24) % 2 == 0 and 1 or -1
    local heading = object.Heading
    local target = object.Position
    local position = {
        x=target.x + math.cos(heading)*12 - math.sin(heading)*60*side,
        y=target.y + 9,
        z=target.z + math.sin(heading)*12 + math.cos(heading)*60*side,
    }
    local distance = math.sqrt((target.x-position.x)^2 + (target.y-position.y)^2 + (target.z-position.z)^2)
    local forward = {x=(target.x-position.x)/distance, y=(target.y-position.y)/distance, z=(target.z-position.z)/distance}
    local horizontal = math.sqrt(forward.x^2 + forward.z^2)
    local right = {x=-forward.z/horizontal, y=0, z=forward.x/horizontal}
    local up = {x=-forward.y*right.z, y=forward.x*right.z-forward.z*right.x, z=forward.y*right.x}
    LoSetCameraPosition({p=position, x=forward, y=up, z=right})
    if trace and math.floor(elapsed) ~= last_recorded then
        last_recorded = math.floor(elapsed)
        local actual = LoGetCameraPosition().p
        trace:write(string.format("%.2f,%s,%s,%s,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f\n",elapsed,index==1 and "fab" or "embraer",targets[index].id,object.Name,position.x,position.y,position.z,actual.x,actual.y,actual.z))
        trace:flush()
    end
end

function LuaExportStop()
    if trace then trace:close(); trace=nil end
end