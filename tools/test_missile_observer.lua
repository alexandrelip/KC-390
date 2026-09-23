local root = (arg[1] or "."):gsub("\\", "/"):gsub("/$", "")
local function test(case)
    local logs, handler, tick = {}, nil, nil
    local state = { ammo = 8, targetPresent = true, controlLife = 20, time = 0 }
    local controller = { setOption = function() end }
    local target = {
        getName = function() return "MISSILE_KC390" end,
        isExist = function() return state.targetPresent end,
        getLife = function() assert(state.targetPresent, "Dead userdata queried"); return 20 end,
        getDrawArgumentValue = function() assert(state.targetPresent, "Dead userdata queried"); return 0 end,
        getController = function() return controller end,
    }
    local control = {
        isExist = function() return true end,
        getLife = function() return state.controlLife end,
        getPoint = function() return { x = state.time * 140, y = 1000, z = 0 } end,
        getFuel = function() return 1 - state.time / 10000 end,
        inAir = function() return true end,
        getDrawArgumentValue = function() return 0 end,
    }
    local launcher = {
        getName = function() return "MISSILE_LAUNCHER" end,
        getAmmo = function() return {{count = state.ammo, desc = { category = 1, displayName = "mock missile" }}} end,
    }
    local environment = setmetatable({
        KC390_TEST_MISSILE = "Tor",
        env = {info = function(text) logs[#logs + 1] = text end, error = function(text) error(text) end},
        timer = { getTime = function() return state.time end, scheduleFunction = function(callback) tick = callback end },
        Unit = { getByName = function(name) if name == "CONTROL_KC390" then return control end; return state.targetPresent and target or nil end },
        Airbase = { getByName = function() return {getPoint = function() return {x = 0, y = 0, z = 0} end} end },
        coalition = { addGroup = function() return {getUnit = function() return launcher end, getController = function() return controller end} end },
        country = {id = {RUSSIA = 0}}, Group = {Category = {GROUND = 0}},
        AI = {Option = {Ground = {id = {ROE = 0, ALARM_STATE = 1}, val = {ROE = {WEAPON_HOLD = 0, OPEN_FIRE = 1}, ALARM_STATE = {RED = 1}}}, Air = {id = {REACTION_ON_THREAT = 0}, val = {REACTION_ON_THREAT = {NO_REACTION = 0}}}}},
        Weapon = {Category = {MISSILE = 1}},
        world = {event = {S_EVENT_SHOT = 1, S_EVENT_HIT = 2, S_EVENT_DEAD = 3, S_EVENT_CRASH = 4, S_EVENT_UNIT_LOST = 5}, addEventHandler = function(value) handler = value end},
        trigger = {action = {setUserFlag = function() end}},
    }, {__index = _G})
    local chunk = assert(loadfile(root .. "/tools/missile_damage_test.lua"))
    setfenv(chunk, environment)
    chunk()
    state.time = 25
    tick(nil, state.time)
    if case.shot then
        local weapon = { isExist = function() return true end, getTypeName = function() return "test_weapon" end, getDesc = function() return {category = case.gun and 0 or 1} end }
        handler:onEvent({id = 1, time = 26, initiator = launcher, weapon = weapon})
        state.ammo = 7
    end
    if case.hit then
        handler:onEvent({id = 2, time = 28, initiator = case.other and {getName = function() return "OTHER" end} or launcher, target = target, weapon_name = "test_weapon"})
        state.targetPresent = false
    end
    state.time = 29
    tick(nil, state.time)
    if case.controlDamaged then state.controlLife = 19 end
    state.time = 171
    tick(nil, state.time)
    local result
    for _, message in ipairs(logs) do if message:match("^KC390_AI_RESULT ") then result = message end end
    assert(result == "KC390_AI_RESULT " .. (case.pass and "PASS" or "FAIL"), case.name .. ": " .. tostring(result))
    print("PASS observer: " .. case.name)
end
for _, case in ipairs({
    {name = "no launch fails"},
    {name = "missed missile fails", shot = true},
    {name = "gun hit fails", shot = true, gun = true, hit = true},
    {name = "unrelated shooter fails", shot = true, hit = true, other = true},
    {name = "damaged control fails", shot = true, hit = true, controlDamaged = true},
    {name = "identified missile impact passes without dead userdata reads", shot = true, hit = true, pass = true},
}) do test(case) end