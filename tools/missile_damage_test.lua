-- Runtime injected only into the isolated DCS missile test mission.
-- Uses native AI weapons: no scripted explosions, forced damage or argument writes.
if KC390_AI_RUNNING then return end
KC390_AI_RUNNING = true
local started = timer.getTime()
local targetName, controlName = "MISSILE_KC390", "CONTROL_KC390"
local target = assert(Unit.getByName(targetName), "Missile target missing")
local control = assert(Unit.getByName(controlName), "Unattacked control missing")
local initialLife, controlLife = target:getLife(), control:getLife()
assert(initialLife == 20 and controlLife == 20, "Unexpected initial KC-390 life")
local controlStart, controlFuel = control:getPoint(), control:getFuel()
local reference = assert(Airbase.getByName("Batumi")):getPoint()
local launcherType = KC390_TEST_MISSILE == "Strela10" and "Strela-10M3" or "Tor 9A331"
local group = assert(coalition.addGroup(country.id.RUSSIA, Group.Category.GROUND, {
    name = "MISSILE_LAUNCHER_GROUP", groupId = 601, task = "Ground Nothing",
    units = {{ name = "MISSILE_LAUNCHER", unitId = 601, type = launcherType,
        skill = "Excellent", x = reference.x, y = reference.z + 150, heading = math.pi }},
}))
local launcher = assert(group:getUnit(1))
local controller = group:getController()
controller:setOption(AI.Option.Ground.id.ROE, AI.Option.Ground.val.ROE.WEAPON_HOLD)
controller:setOption(AI.Option.Ground.id.ALARM_STATE, AI.Option.Ground.val.ALARM_STATE.RED)
target:getController():setOption(AI.Option.Air.id.REACTION_ON_THREAT, AI.Option.Air.val.REACTION_ON_THREAT.NO_REACTION)
local function ammunition()
    local total = 0
    for _, item in ipairs(launcher:getAmmo() or {}) do total = total + item.count end
    return total
end
local ammoStart = ammunition()
assert(ammoStart > 0, "Native launcher has no ammunition")
local shots, hits, hitAt, lostAt, armed = 0, 0, nil, nil, false
local minimumLife, peakDamage, sample = initialLife, 0, 0
local shotTypes, lastArguments = {}, {}
env.info(string.format("KC390_AI_START missile system=%s targetLife=%.1f controlLife=%.1f ammo=%d noCountermeasures=true", launcherType, initialLife, controlLife, ammoStart))
for _, item in ipairs(launcher:getAmmo() or {}) do
    local desc = item.desc or {}
    env.info(string.format("KC390_AI_MISSILE_AMMO type=%s category=%s count=%d", tostring(desc.displayName), tostring(desc.category), item.count))
end
local function objectName(object)
    if not object then return nil end
    local ok, name = pcall(object.getName, object)
    if ok then return name end
    return nil
end
local function weaponType(event)
    if event.weapon_name and event.weapon_name ~= "" then return event.weapon_name end
    if event.weapon and event.weapon:isExist() then
        local ok, name = pcall(event.weapon.getTypeName, event.weapon)
        if ok then return name end
    end
    return "unavailable"
end
world.addEventHandler({ onEvent = function(_, event)
    if event.id == world.event.S_EVENT_SHOT and objectName(event.initiator) == "MISSILE_LAUNCHER" then
        local name = weaponType(event)
        local desc = event.weapon and event.weapon:isExist() and event.weapon:getDesc() or {}
        env.info(string.format("KC390_AI_MISSILE_SHOT time=%.3f type=%s category=%s", event.time - started, name, tostring(desc.category)))
        if desc.category == Weapon.Category.MISSILE then
            shots = shots + 1
            shotTypes[name] = true
        end
    elseif event.id == world.event.S_EVENT_HIT and objectName(event.target) == targetName then
        local name = weaponType(event)
        local shooter = objectName(event.initiator)
        env.info(string.format("KC390_AI_MISSILE_HIT time=%.3f weapon=%s shooter=%s", event.time - started, name, tostring(shooter)))
        -- An unavailable weapon object at detonation is not itself missile proof;
        -- require the identified native launcher plus an earlier missile shot.
        if shots > 0 and shooter == "MISSILE_LAUNCHER" and (shotTypes[name] or name == "unavailable") then
            hits = hits + 1
            hitAt = hitAt or event.time
            controller:setOption(AI.Option.Ground.id.ROE, AI.Option.Ground.val.ROE.WEAPON_HOLD)
        end
    elseif event.id == world.event.S_EVENT_DEAD or event.id == world.event.S_EVENT_CRASH
        or event.id == world.event.S_EVENT_UNIT_LOST then
        if objectName(event.initiator) == targetName then
            env.info(string.format("KC390_AI_MISSILE_EVENT time=%.3f event=%s", event.time - started, tostring(event.id)))
        end
    end
end })

timer.scheduleFunction(function(_, currentTime)
    local ok, finished = pcall(function()
        local elapsed = currentTime - started
        sample = sample + 1
        if not armed and elapsed >= 25 then
            controller:setOption(AI.Option.Ground.id.ROE, AI.Option.Ground.val.ROE.OPEN_FIRE)
            armed = true
            env.info("KC390_AI_MISSILE_ARMED time=" .. elapsed)
        end
        -- Never retain a dead Unit userdata for getLife/getDrawArgumentValue.
        local live = Unit.getByName(targetName)
        if live and live:isExist() then
            local life = live:getLife()
            minimumLife = math.min(minimumLife, life)
            local changed = {}
            for argument = 140, 179 do
                local value = live:getDrawArgumentValue(argument)
                assert(type(value) == "number" and value == value, "Invalid damage argument")
                peakDamage = math.max(peakDamage, value)
                if math.abs(value - (lastArguments[argument] or 0)) > 0.0001 then
                    changed[#changed + 1] = string.format("%d=%.6f", argument, value)
                    lastArguments[argument] = value
                end
            end
            if #changed > 0 or sample % 50 == 1 then
                env.info(string.format("KC390_AI_MISSILE_STATE time=%.2f life=%.3f args=%s", elapsed, life, table.concat(changed, ",")))
            end
        elseif not lostAt then
            lostAt = currentTime
            env.info("KC390_AI_MISSILE_REMOVED time=" .. elapsed)
        end
        if (hitAt and currentTime - hitAt >= 30) or elapsed >= 170 then
            local intact = assert(Unit.getByName(controlName), "Unattacked control disappeared")
            assert(intact:isExist(), "Unattacked control no longer exists")
            local point = intact:getPoint()
            local distance = math.sqrt((point.x - controlStart.x)^2 + (point.z - controlStart.z)^2)
            local controlPass = intact:getLife() == controlLife and intact:inAir() and distance > 2000 and intact:getFuel() < controlFuel
            for argument = 140, 179 do
                if intact:getDrawArgumentValue(argument) ~= 0 then controlPass = false end
            end
            local ammoEnd = ammunition()
            local damaged = minimumLife < initialLife or (lostAt ~= nil and hitAt ~= nil and lostAt >= hitAt)
            local passed = shots > 0 and hits > 0 and ammoEnd < ammoStart and damaged and controlPass
            env.info(string.format("KC390_AI_MISSILE_RESULT system=%s shots=%d hits=%d ammo=%d->%d minLife=%.3f removed=%s peak=%.6f controlLife=%.1f controlDistance=%.1f control=%s", launcherType, shots, hits, ammoStart, ammoEnd, minimumLife, tostring(lostAt ~= nil), peakDamage, intact:getLife(), distance, tostring(controlPass)))
            env.info("KC390_AI_RESULT " .. (passed and "PASS" or "FAIL"))
            trigger.action.setUserFlag("KC390_AI_DONE", 1)
            return true
        end
    end)
    if not ok then
        env.error("KC390_AI_RESULT ERROR " .. tostring(finished))
        trigger.action.setUserFlag("KC390_AI_DONE", 1)
        return
    end
    if not finished then return currentTime + 0.1 end
end, nil, timer.getTime() + 0.1)