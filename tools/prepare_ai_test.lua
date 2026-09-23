local work = assert(arg[1])
local profile = assert(arg[2])
local scenario = arg[3] or "Damage"
local rendered = arg[4] == "Render"
local wingSide = arg[5] == "Right" and 1 or -1
local missileSystem = arg[6] or "Tor"
local scriptRoot = (arg[0]:gsub("\\", "/")):match("^(.*)/")
local cameraTarget
local function serialize(value)
    if type(value) == "table" then
        local fields = {}
        for key, item in pairs(value) do fields[#fields + 1] = "[" .. serialize(key) .. "]=" .. serialize(item) end
        return "{" .. table.concat(fields, ",") .. "}"
    elseif type(value) == "string" then
        return string.format("%q", value)
    elseif type(value) == "number" or type(value) == "boolean" then
        return tostring(value)
    end
    error("Unsupported serialized type: " .. type(value))
end
local function write(path, text)
    assert(loadstring(text), path)
    local file = assert(io.open(path, "wb"))
    assert(file:write(text))
    assert(file:close())
end
assert(loadfile(work .. "/staged/mission"))()
local prototype, prototypeGroup
for _, coalitionData in pairs(mission.coalition) do
    for _, countryData in pairs(coalitionData.country or {}) do
        for _, groupData in pairs((countryData.plane or {}).group or {}) do
            for _, unitData in ipairs(groupData.units or {}) do
                if unitData.type == "KC-390" then prototype, prototypeGroup = unitData, groupData end
            end
        end
    end
end
assert(prototype, "Source mission has no KC-390")
local function makeGroup(typeName, name, identifier, offset)
    local unit = assert(loadstring("return " .. serialize(prototype)))()
    unit.type, unit.name, unit.unitId = typeName, name, identifier
    unit.skill, unit.alt, unit.alt_type = "Excellent", 6000, "BARO"
    unit.x, unit.y = prototype.x, prototype.y + offset
    unit.heading, unit.psi, unit.speed = 0, 0, 170
    unit.parking, unit.parking_id, unit.livery_id = nil, nil, nil
    unit.payload = { fuel = 10000, flare = 60, chaff = 60, gun = 0, pylons = {} }
    local points = {}
    for index = 1, 2 do
        points[index] = {
            type = "Turning Point", action = "Turning Point", alt = 6000,
            alt_type = "BARO", x = unit.x + (index - 1) * 60000, y = unit.y,
            speed = 170, speed_locked = true, ETA = 0, ETA_locked = index == 1,
            task = { id = "ComboTask", params = { tasks = {} } },
        }
    end
    return {
        name = name .. "_GROUP", groupId = identifier, units = { unit },
        x = unit.x, y = unit.y, task = "Transport", start_time = 0,
        lateActivation = false, uncontrolled = false, communication = false,
        route = { points = points },
    }
end
if scenario == "Missile" then
    for _, coalitionData in pairs(mission.coalition) do coalitionData.country = {} end
    -- Batumi runway coordinates from the existing takeoff template are not
    -- required: runtime resolves the native Airbase position for the launcher.
    local group = makeGroup("KC-390", "MISSILE_KC390", 101, 0)
    local control = makeGroup("KC-390", "CONTROL_KC390", 103, 40000)
    -- Batumi parking reference verified in KC-390 Takeoff Test.miz (airbase 22).
    assert(mission.theatre == "Caucasus", "Missile scenario requires Caucasus")
    for _, aircraftGroup in ipairs({ group, control }) do
        local unit = aircraftGroup.units[1]
        local offset = aircraftGroup == control and 40000 or 0
        unit.x, unit.y, unit.alt, unit.speed = -355990.9375 - 6500, 618136.9375 + offset, 1000, 140
        unit.payload.flare, unit.payload.chaff = 0, 0
        unit.livery_id = "FAB Standard"
        aircraftGroup.x, aircraftGroup.y = unit.x, unit.y
        for index, point in ipairs(aircraftGroup.route.points) do
            point.x, point.y, point.alt, point.speed = unit.x + (index - 1) * 60000, unit.y, unit.alt, unit.speed
        end
    end
    cameraTarget = group.units[1]
    mission.coalition.blue.country = { { id = 2, name = "USA", plane = { group = { group, control } } } }
    mission.start_time = 43200
    for _, wind in pairs(mission.weather.wind) do wind.speed = 0 end
elseif scenario == "Wings" then
    for _, coalitionData in pairs(mission.coalition) do coalitionData.country = {} end
    local group = makeGroup("KC-390", "WING_KC390", 101, 0)
    group.units[1].alt = 1500
    for _, point in ipairs(group.route.points) do point.alt = 1500 end
    mission.coalition.blue.country = { { id = 2, name = "USA", plane = { group = { group } } } }
    mission.start_time = 43200
    for _, wind in pairs(mission.weather.wind) do wind.speed = 0 end
elseif scenario == "Damage" then
    for _, coalitionData in pairs(mission.coalition) do coalitionData.country = {} end
    mission.coalition.blue.country = {
        { id = 2, name = "USA", plane = { group = {
            makeGroup("KC-390", "HP_KC390", 101, 0),
            makeGroup("C-130", "HP_C130", 102, 2000),
            makeGroup("KC-390", "AI_KC390", 103, 4000),
        } } },
    }
elseif scenario == "Fans" then
    local parked = assert(loadstring("return " .. serialize(prototypeGroup)))()
    parked.name, parked.groupId, parked.uncontrolled = "FAN_COLD_GROUP", 201, true
    parked.units = { assert(loadstring("return " .. serialize(prototype)))() }
    parked.units[1].name, parked.units[1].unitId = "FAN_COLD", 201
    assert(parked.route.points[1].type == "TakeOffParking", "Fans test requires a cold parking mission")
    for _, coalitionData in pairs(mission.coalition) do coalitionData.country = {} end
    mission.coalition.blue.country = {
        { id = 2, name = "USA", plane = { group = {
            parked, makeGroup("KC-390", "FAN_RUNNING", 202, 4000),
            makeGroup("KC-135", "FAN_NATIVE", 203, 8000),
        } } },
    }
    for _, wind in pairs(mission.weather.wind) do wind.speed = 0 end
end
mission.requiredModules = { ["KC-390"] = "KC-390" }
mission.forcedOptions = { immortal = false, easyFlight = false, birds = 0 }
local runtime = [=[
if KC390_AI_RUNNING then return end
KC390_AI_RUNNING = true
env.info("KC390_AI_START")
local blast_pass = false
local hits = 0
local visual_damage, visual_peak = {}, 0
local flight = assert(Unit.getByName("AI_KC390"))
local flight_start, fuel_start = flight:getPoint(), flight:getFuel()
local function life(name)
    local unit = Unit.getByName(name)
    return unit and unit:isExist() and unit:getLife() or 0
end
timer.scheduleFunction(function(_, currentTime)
    for _, name in ipairs({ "HP_KC390", "GUN_KC390" }) do
        local unit = Unit.getByName(name)
        if unit and unit:isExist() then
            for argument = 140, 179 do
                local value = unit:getDrawArgumentValue(argument)
                if value and value > (visual_damage[name .. argument] or 0) + 0.0001 then
                    visual_damage[name .. argument] = value
                    visual_peak = math.max(visual_peak, value)
                    env.info(string.format("KC390_AI_DAMAGE_ARG name=%s arg=%d value=%.6f", name, argument, value))
                end
            end
        end
    end
    if currentTime < 70 then return currentTime + 0.1 end
end, nil, timer.getTime() + 0.1)
world.addEventHandler({ onEvent = function(_, event)
    if event.id == world.event.S_EVENT_HIT and event.target then
        local valid, name = pcall(event.target.getName, event.target)
        if valid and name == "GUN_KC390" then
            hits = hits + 1
            if hits <= 5 then env.info("KC390_AI_GUN_HIT count=" .. hits) end
        end
    end
end })
local base = assert(Airbase.getByName("Batumi")):getPoint()
local altitude = land.getHeight({ x = base.x, y = base.z }) + 250
local points = {}
for index = 1, 2 do
    points[index] = {
        type = "Turning Point", action = "Turning Point", alt = altitude, alt_type = "BARO",
        x = base.x - 2000 + (index - 1) * 20000, y = base.z,
        speed = 110, speed_locked = true, ETA = 0, ETA_locked = index == 1,
        task = { id = "ComboTask", params = { tasks = {} } },
    }
end
local target = assert(coalition.addGroup(country.id.USA, Group.Category.AIRPLANE, {
    name = "GUN_KC390_GROUP", groupId = 501, task = "Transport", start_time = 0,
    x = points[1].x, y = points[1].y, route = { points = points },
    units = { {
        name = "GUN_KC390", unitId = 501, type = "KC-390", skill = "Excellent",
        x = points[1].x, y = points[1].y, alt = altitude, alt_type = "BARO",
        speed = 110, heading = 0, psi = 0, onboard_num = "501",
        payload = { fuel = 8000, flare = 60, chaff = 60, gun = 0, pylons = {} },
    } },
}))
target:getController():setOption(AI.Option.Air.id.REACTION_ON_THREAT, AI.Option.Air.val.REACTION_ON_THREAT.NO_REACTION)
local guns = {}
for index = 1, 2 do
    local group = assert(coalition.addGroup(country.id.RUSSIA, Group.Category.GROUND, {
        name = "HP_GUN_GROUP_" .. index, groupId = 600 + index, task = "Ground Nothing",
        units = { {
            name = "HP_GUN_" .. index, unitId = 600 + index, type = "Vulcan", skill = "Excellent",
            x = base.x + (index - 1) * 1400, y = base.z + 120, heading = 0,
        } },
    }))
    group:getController():setOption(AI.Option.Ground.id.ALARM_STATE, AI.Option.Ground.val.ALARM_STATE.RED)
    group:getController():setOption(AI.Option.Ground.id.ROE, AI.Option.Ground.val.ROE.OPEN_FIRE)
    guns[index] = group:getUnit(1)
end
local function ammunition()
    local total = 0
    for _, gun in ipairs(guns) do
        for _, item in ipairs(gun:getAmmo() or {}) do total = total + item.count end
    end
    return total
end
local ammo_start = ammunition()
env.info(string.format("KC390_AI_GUN_START life=%.3f ammo=%d altitude=%.1f", life("GUN_KC390"), ammo_start, altitude))
local names, baseline = { "HP_KC390", "HP_C130" }, {}
local powers, stage = { 1, 5, 25, 100 }, 0
timer.scheduleFunction(function(_, currentTime)
    local ok, failure = pcall(function()
        for _, name in ipairs(names) do
            if stage == 0 then
                baseline[name] = life(name)
                assert(baseline[name] == (name == "HP_C130" and 45 or 20), name .. " initial HP")
            end
            env.info(string.format("KC390_AI_HP stage=%d name=%s life=%.6f initial=%.6f", stage, name, life(name), baseline[name]))
        end
        if stage == #powers then
            blast_pass = life("HP_KC390") <= 1 and life("HP_C130") <= 1
            env.info("KC390_AI_BLAST " .. (blast_pass and "PASS" or "FAIL"))
        else
            for _, name in ipairs(names) do
                local unit = Unit.getByName(name)
                if unit and unit:isExist() and unit:getLife() > 1 then
                    local point = unit:getPoint()
                    point.y = point.y + 0.5
                    trigger.action.explosion(point, powers[stage + 1])
                end
            end
        end
    end)
    if not ok then env.error("KC390_AI_RESULT ERROR " .. tostring(failure)); return end
    stage = stage + 1
    if stage <= #powers then return currentTime + 4 end
end, nil, timer.getTime() + 3)
timer.scheduleFunction(function()
    local ok, failure = pcall(function()
        assert(flight:isExist(), "Navigation control aircraft disappeared")
        local current = flight:getPoint()
        local distance = math.sqrt((current.x - flight_start.x)^2 + (current.z - flight_start.z)^2)
        local navigation = flight:inAir() and flight:getLife() == 20 and distance > 3000 and flight:getFuel() < fuel_start
        local gun_pass = hits > 0 and life("GUN_KC390") < 20 and ammunition() < ammo_start
        for argument = 140, 179 do
            assert(flight:getDrawArgumentValue(argument) == 0, "Undamaged aircraft has a damage argument: " .. argument)
        end
        local visual_pass = not require_visual_damage or visual_peak > 0
        env.info(string.format("KC390_AI_FLIGHT distance=%.1f life=%.3f fuel_start=%.6f fuel_end=%.6f result=%s", distance, flight:getLife(), fuel_start, flight:getFuel(), navigation and "PASS" or "FAIL"))
        env.info(string.format("KC390_AI_GUN hits=%d life=%.3f ammo_start=%d ammo_end=%d result=%s", hits, life("GUN_KC390"), ammo_start, ammunition(), gun_pass and "PASS" or "FAIL"))
        env.info(string.format("KC390_AI_VISUAL_ARGUMENTS required=%s peak=%.6f result=%s", tostring(require_visual_damage), visual_peak, visual_pass and "PASS" or "FAIL"))
        env.info("KC390_AI_RESULT " .. (blast_pass and navigation and gun_pass and visual_pass and "PASS" or "FAIL"))
        trigger.action.setUserFlag("KC390_AI_DONE", 1)
    end)
    if not ok then env.error("KC390_AI_RESULT ERROR " .. tostring(failure)) end
end, nil, timer.getTime() + 65)
]=]
if scenario == "Missile" then
    local file = assert(io.open(scriptRoot .. "/missile_damage_test.lua", "rb"))
    runtime = "local KC390_TEST_MISSILE = " .. string.format("%q", missileSystem) .. "\n" .. assert(file:read("*a"))
    file:close()
elseif scenario == "Wings" then
    runtime = "local side = " .. wingSide .. "\n" .. [=[
if KC390_AI_RUNNING then return end
KC390_AI_RUNNING = true
local started, stage, sample = timer.getTime(), 1, 0
local unit = assert(Unit.getByName("WING_KC390"))
local blasts = { {12, 1}, {20, 5}, {28, 25}, {36, 100} }
local arguments = { 150, 151, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165 }
env.info("KC390_AI_START wings side=" .. side .. " id=" .. unit:getID())
timer.scheduleFunction(function(_, currentTime)
    local ok, failure = pcall(function()
        local elapsed = currentTime - started
        sample = sample + 1
        if sample % 10 == 1 and unit:isExist() then
            local values = {}
            for _, argument in ipairs(arguments) do
                local valid, value = pcall(unit.getDrawArgumentValue, unit, argument)
                values[#values + 1] = argument .. "=" .. (valid and tostring(value) or "unavailable")
            end
            local valid, life = pcall(unit.getLife, unit)
            env.info(string.format("KC390_AI_WING_STATE time=%.2f exists=%s life=%s args=%s", elapsed, tostring(unit:isExist()), valid and tostring(life) or "unavailable", table.concat(values, ",")))
        end
        if blasts[stage] and elapsed >= blasts[stage][1] then
            if unit:isExist() then
                local transform = unit:getPosition()
                local point = {}
                for _, axis in ipairs({ "x", "y", "z" }) do
                    point[axis] = transform.p[axis] - 2 * transform.x[axis] + 1.1 * transform.y[axis] + side * 4.5 * transform.z[axis]
                end
                env.info(string.format("KC390_AI_WING_BLAST stage=%d power=%.1f", stage, blasts[stage][2]))
                trigger.action.explosion(point, blasts[stage][2])
            end
            stage = stage + 1
        end
        if elapsed >= 26 then
            env.info("KC390_AI_RESULT OBSERVED")
            trigger.action.setUserFlag("KC390_AI_DONE", 1)
        end
    end)
    if not ok then env.error("KC390_AI_RESULT ERROR " .. tostring(failure)); trigger.action.setUserFlag("KC390_AI_DONE", 1); return end
    if currentTime - started < 26 then return currentTime + 0.1 end
end, nil, timer.getTime() + 0.1)
]=]
elseif scenario == "Takeoff" then
    runtime = "local name = " .. string.format("%q", prototype.name) .. "\n" .. [=[
if KC390_AI_RUNNING then return end
KC390_AI_RUNNING = true
env.info("KC390_AI_START takeoff")
local started = timer.getTime()
local first = assert(Unit.getByName(name)):getPoint()
local sample = 0
timer.scheduleFunction(function(_, currentTime)
    local ok, finished = pcall(function()
        local unit = assert(Unit.getByName(name), "Takeoff aircraft disappeared")
        assert(unit:isExist() and unit:getLife() == 20, "Ground collision or damage during takeoff")
        local point = unit:getPoint()
        local velocity = unit:getVelocity()
        local speed = math.sqrt(velocity.x^2 + velocity.y^2 + velocity.z^2)
        local agl = point.y - land.getHeight({ x = point.x, y = point.z })
        local gear = unit:getDrawArgumentValue(0)
        local distance = math.sqrt((point.x - first.x)^2 + (point.z - first.z)^2)
        sample = sample + 1
        if sample % 5 == 1 then
            env.info(string.format("KC390_AI_TAKEOFF time=%.1f life=%.1f speed=%.2f agl=%.2f gear=%.3f distance=%.1f fan1=%.6f fan2=%.6f", currentTime - started, unit:getLife(), speed, agl, gear, distance, unit:getDrawArgumentValue(407), unit:getDrawArgumentValue(408)))
        end
        if unit:inAir() and agl > 40 and gear < 0.1 and distance > 500 then
            env.info(string.format("KC390_AI_TAKEOFF PASS time=%.1f speed=%.2f agl=%.2f gear=%.3f", currentTime - started, speed, agl, gear))
            env.info("KC390_AI_RESULT PASS")
            trigger.action.setUserFlag("KC390_AI_DONE", 1)
            return true
        end
        if currentTime - started > 290 then error("Takeoff was not completed within 290 simulation seconds") end
    end)
    if not ok then
        env.error("KC390_AI_RESULT ERROR " .. tostring(finished))
        trigger.action.setUserFlag("KC390_AI_DONE", 1)
        return
    end
    if not finished then return currentTime + 2 end
end, nil, timer.getTime() + 2)
]=]
elseif scenario == "Fans" then
    runtime = [=[
if KC390_AI_RUNNING then return end
KC390_AI_RUNNING = true
env.info("KC390_AI_START fans")
local started, samples = timer.getTime(), 0
local names, arguments = { "FAN_COLD", "FAN_RUNNING", "FAN_NATIVE" }, { 21, 22, 407, 408 }
local measurements = { FAN_COLD = {}, FAN_RUNNING = {}, FAN_NATIVE = {} }
timer.scheduleFunction(function(_, currentTime)
    local ok, finished = pcall(function()
        samples = samples + 1
        for _, name in ipairs(names) do
            local unit = assert(Unit.getByName(name), "Fan test aircraft disappeared")
            assert(unit:isExist() and unit:getLife() > 0, "Unexpected fan test aircraft damage")
            if name ~= "FAN_NATIVE" then assert(unit:getLife() == 20, "Unexpected KC-390 damage") end
            assert(unit:inAir() == (name ~= "FAN_COLD"), "Unexpected fan test aircraft state")
            for _, argument in ipairs(arguments) do
                local value = unit:getDrawArgumentValue(argument)
                assert(type(value) == "number" and value == value and math.abs(value) <= 1, "Invalid fan argument")
                local measurement = measurements[name][argument]
                if not measurement then
                    measurement = { minimum = value, maximum = value, previous = value, changes = 0, windows = { 0, 0, 0, 0 } }
                    measurements[name][argument] = measurement
                end
                if math.abs(value - measurement.previous) > 0.00001 then
                    measurement.changes = measurement.changes + 1
                    local window = math.min(4, math.floor((currentTime - started) / 3) + 1)
                    measurement.windows[window] = measurement.windows[window] + 1
                end
                measurement.minimum = math.min(measurement.minimum, value)
                measurement.maximum = math.max(measurement.maximum, value)
                measurement.previous = value
            end
        end
        if currentTime - started < 12 then return false end
        for _, name in ipairs(names) do
            for _, argument in ipairs(arguments) do
                local measurement = measurements[name][argument]
                env.info(string.format("KC390_AI_FANS name=%s arg=%d min=%.6f max=%.6f changes=%d samples=%d windows=%s", name, argument, measurement.minimum, measurement.maximum, measurement.changes, samples, table.concat(measurement.windows, ",")))
            end
        end
        for _, argument in ipairs({ 407, 408 }) do
            local running, cold = measurements.FAN_RUNNING[argument], measurements.FAN_COLD[argument]
            local native = measurements.FAN_NATIVE[argument]
            assert(native.changes >= 12, "Native fan reference did not animate; enable rendering")
            assert(running.changes >= native.changes * 0.8 and running.maximum - running.minimum > 0.5, "Running fan did not follow native rotations: " .. argument)
            for _, changes in ipairs(running.windows) do assert(changes >= 3, "Fan rotation was not sustained: " .. argument) end
            assert(cold.changes == 0, "Fan rotated with engines stopped in zero wind: " .. argument)
        end
        env.info("KC390_AI_RESULT PASS")
        trigger.action.setUserFlag("KC390_AI_DONE", 1)
        return true
    end)
    if not ok then
        env.error("KC390_AI_RESULT ERROR " .. tostring(finished))
        trigger.action.setUserFlag("KC390_AI_DONE", 1)
        return
    end
    if not finished then return currentTime + 0.073 end
end, nil, timer.getTime() + 0.073)
]=]
end
if scenario == "Damage" then runtime = "local require_visual_damage = " .. tostring(rendered) .. "\n" .. runtime end
assert(loadstring(runtime))
mission.trigrules = { {
    comment = "KC390 AI validation", eventlist = "", predicate = "triggerStart", rules = {},
    actions = { { predicate = "a_do_script", text = runtime } },
} }
mission.trig = {
    actions = { [1] = "a_do_script(" .. string.format("%q", runtime) .. ");" },
    conditions = { [1] = "return(true);" },
    funcStartup = { [1] = "if mission.trig.conditions[1]() then mission.trig.actions[1]() end; mission.trig.funcStartup[1] = nil;" },
    events = {}, custom = {}, func = {}, flag = { [1] = true }, customStartup = {},
}
for _, source in pairs(mission.trig.actions) do assert(loadstring(source)) end
for _, source in pairs(mission.trig.conditions) do assert(loadstring(source)) end
for _, source in pairs(mission.trig.funcStartup) do assert(loadstring(source)) end
write(work .. "/staged/mission", "mission = " .. serialize(mission))
assert(loadfile(work .. "/options.before.lua"))()
options.VR.enable = false
options.miscellaneous.launcher = false
options.graphics.fullScreen = false
options.graphics.width, options.graphics.height = 960, 540
options.graphics.preloadRadius = 10000
if rendered then
    options.graphics.Upscaling, options.graphics.AA, options.graphics.MSAA = "OFF", "OFF", 0
    options.graphics.maxFPS, options.graphics.ScreenshotExt = 30, "png"
    options.difficulty.externalViews, options.difficulty.spectatorExternalViews = true, true
    options.difficulty.labels = 0
end
if scenario == "Wings" or scenario == "Missile" then options.graphics.width, options.graphics.height = 1280, 720 end
write(profile .. "/Config/options.lua", "options = " .. serialize(options))
if scenario == "Wings" or scenario == "Missile" then
    local cameraConfig = scenario == "Missile" and ("local reference = { x = " .. cameraTarget.x .. ", z = " .. cameraTarget.y .. " }\nlocal capturePrefix = 'missile-'\n") or "local reference = nil\nlocal capturePrefix = 'wing-'\n"
    write(profile .. "/Scripts/Export.lua", cameraConfig .. [=[
local targetId, lastPosition, started, nextCapture, samples = nil, nil, nil, 5, 0
local function normalize(vector)
    local length = math.sqrt(vector.x^2 + vector.y^2 + vector.z^2)
    return { x = vector.x / length, y = vector.y / length, z = vector.z / length }
end
function LuaExportAfterNextFrame()
    local current = LoGetModelTime()
    if not started then started = current end
    if not targetId then
        local nearest = math.huge
        for identifier, object in pairs(LoGetWorldObjects() or {}) do
            if object.Name == "KC-390" and object.Position then
                local distance = reference and ((object.Position.x - reference.x)^2 + (object.Position.z - reference.z)^2) or 0
                if distance < nearest then targetId, nearest = identifier, distance end
            end
        end
    end
    local target = current - started < 19 and targetId and LoGetObjectById(targetId)
    if target and target.Position then lastPosition = target.Position end
    if not lastPosition then return end
    local position = { x = lastPosition.x - 38, y = lastPosition.y + 30, z = lastPosition.z - 43 }
    local forward = normalize({ x = lastPosition.x - 5 - position.x, y = lastPosition.y - position.y, z = lastPosition.z - position.z })
    local right = normalize({ x = -forward.z, y = 0, z = forward.x })
    local up = { x = right.y * forward.z - right.z * forward.y, y = right.z * forward.x - right.x * forward.z, z = right.x * forward.y - right.y * forward.x }
    if current - started < 19 then LoSetCameraPosition({ p = position, x = forward, y = up, z = right }) end
    samples = samples + 1
    if current - started >= nextCapture then
        local camera = LoGetCameraPosition()
        local error = math.sqrt((camera.p.x - position.x)^2 + (camera.p.y - position.y)^2 + (camera.p.z - position.z)^2)
        log.write("KC390_AI_CAMERA", log.INFO, string.format("time=%.2f target=%s error=%.4f samples=%d", current - started, tostring(targetId), error, samples))
        local request = io.open(lfs.writedir() .. "wing-capture.txt", "w")
        local captureNumber = capturePrefix == 'missile-' and math.floor(nextCapture * 1000 + 0.5) or nextCapture
        if request then request:write(capturePrefix .. captureNumber); request:close() end
        nextCapture = nextCapture + (capturePrefix == 'missile-' and 0.5 or (nextCapture < 17 and 4 or 1))
    end
end
]=])
end
local limit = scenario == "Takeoff" and 300 or scenario == "Fans" and 25 or scenario == "Wings" and 30 or scenario == "Missile" and 175 or 75
write(profile .. "/Scripts/Hooks/kc390_ai_test.lua", "local runtime = " .. string.format("%q", runtime) .. "\nlocal limit = " .. limit .. "\n" .. [=[
local callbacks, startedAt, injected = {}, nil, false
local lastCheck = 0
log.write("KC390_AI_HOOK", log.INFO, "profile=" .. lfs.writedir())
function callbacks.onMissionLoadEnd() DCS.setPause(false) end
function callbacks.onSimulationStart() startedAt = DCS.getModelTime(); DCS.setPause(false) end
function callbacks.onSimulationFrame()
    if DCS.getPause() then DCS.setPause(false) end
    if startedAt and not injected and DCS.getModelTime() - startedAt > 1 then
        local result, success = net.dostring_in("mission", "a_do_script(" .. string.format("%q", runtime) .. ")")
        log.write("KC390_AI_HOOK", log.INFO, "injection=" .. tostring(result) .. "; success=" .. tostring(success))
        injected = true
    end
    if startedAt and DCS.getModelTime() - lastCheck > 1 then
        lastCheck = DCS.getModelTime()
        local result = net.dostring_in("mission", "return tostring(trigger.misc.getUserFlag('KC390_AI_DONE'))")
        if tonumber(result) == 1 then DCS.exitProcess() end
    end
    if startedAt and DCS.getModelTime() - startedAt > limit then DCS.exitProcess() end
end
DCS.setUserCallbacks(callbacks)
]=])
print("PASS: isolated AI mission and all nested scripts compile under " .. _VERSION)