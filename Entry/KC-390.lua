-- =====================================================================
--  KC-390.lua  -  Definicao da aeronave (banco de dados do DCS)
-- ---------------------------------------------------------------------
--  Embraer KC-390 Millennium  -  APENAS IA  (add_aircraft)
--  Usa o flight model SFM definido em KC-390_SFM.lua (global KC390_SFM).
--
--  Modelo 3D (.edm) + animacoes convertidos do FSX (FABv KC-390 v1.5)
--  via ModelConverterX + 3ds Max + exportador EDM da ED.
--  Args reais no EDM: 0,2,3,5,9,10,11,12,13,15,18,19,20,21,22,28,29,30,31,42,71,101,102,103
-- =====================================================================

KC_390 =
{
    Name            = "KC-390",
    DisplayName     = _("KC-390 Millennium"),
    Picture         = "KC-390.png",          -- icone no Editor de Missao (opcional)
    Rate            = 70,
    Shape           = "KC-390",              -- resolve para Shapes/KC-390_lod0.edm (via .lods)
    WorldID         = WSTYPE_PLACEHOLDER,
    defFuelRatio    = 0.65,

    shape_table_data =
    {
        {
            file        = "KC-390",
            life        = 25,                -- resistencia (barra de vida)
            vis         = 3,
            fire        = { 360, 3 },        -- fogo no solo apos destruicao: 360s, 3m
            username    = "KC-390",
            index       = WSTYPE_PLACEHOLDER,
            classname   = "lLandPlane",
            positioning = "BYNORMAL",
        },
    },

    -- Tipo de operacao de pista (CTOL = decolagem/pouso convencional)
    takeoff_and_landing_type = "CTOL",

    mapclasskey = "P0091000064",
    attribute   = { wsType_Air, wsType_Airplane, wsType_Cruiser, WSTYPE_PLACEHOLDER,
                    "Transports", "Tankers", "Refuelable",
                  },
    Categories  = { "{8A302789-A55D-4897-B647-66493FA6826F}", "Tanker" },

    -------------------------------------------------------------------
    -- MASSAS (kg) - dados reais Embraer
    -------------------------------------------------------------------
    M_empty     = 35000,    -- peso vazio operacional
    M_nominal   = 58000,    -- vazio + combustivel interno cheio
    M_max       = 87000,    -- MTOW (86.999 kg)
    M_fuel_max  = 23000,    -- combustivel interno total

    -------------------------------------------------------------------
    -- DIMENSOES (m) - dados reais
    -------------------------------------------------------------------
    length      = 35.20,
    height      = 11.84,
    wing_area   = 130.0,    -- estimado (nao publicado oficialmente)
    wing_span   = 35.05,
    wing_type   = FIXED_WING,
    wing_tip_pos = { -15.5, 1.20, 17.52 },   -- estimado (calibrar no .edm)

    H_max       = 11000,    -- teto de servico (m)
    average_fuel_consumption = 0.70,         -- kg/s (cruzeiro, 2 motores)

    has_afteburner = false,
    has_speedbrake = true,

    -- Empuxo (kgf): 2 x IAE V2500-E5
    thrust_sum_max = 28430,
    thrust_sum_ab  = 28430,
    engines_count  = 2,

    RCS                  = 90,
    IR_emission_coeff    = 1.0,
    IR_emission_coeff_ab = 0.0,
    Ny_min  = -1.0,
    Ny_max  =  3.0,        -- KC-390 e certificado para 3 g
    Ny_max_e = 2.5,

    -------------------------------------------------------------------
    -- PARAMETROS DE VOO DA IA (m/s salvo indicado)
    -------------------------------------------------------------------
    CAS_min         = 54,       -- velocidade minima (~104 kn / stall)
    V_opt           = 230,      -- cruzeiro economico (~Mach 0,80)
    V_take_off      = 67,       -- velocidade de rotacao (~130 kn)
    V_land          = 64,       -- velocidade de pouso (~125 kn)
    V_max_sea_level = 180,      -- max ao nivel do mar (~Vmo)
    V_max_h         = 274,      -- max em altitude (Mach 0,93 / 988 km/h)
    Vy_max          = 25,       -- razao de subida maxima (~4900 ft/min)
    Mach_max        = 0.93,
    AOA_take_off    = 0.12,
    bank_angle_max  = 45,
    flaps_maneuver  = 0.5,
    range           = 5000,     -- alcance aprox. com carga (km)

    -------------------------------------------------------------------
    -- TREM DE POUSO (pontos de contato e diametros medidos no EDM)
    -------------------------------------------------------------------
    undercarriage_transmission = "Hydraulic",
    undercarriage_movement     = 2,
    tand_gear_max = 1.5,
    nose_gear_pos = { 9.13, -4.36, 0.0 },
    nose_gear_amortizer_direct_stroke        =  0.0,
    nose_gear_amortizer_reversal_stroke      = -0.40,
    nose_gear_amortizer_normal_weight_stroke =  0.0,
    nose_gear_wheel_diameter                 =  0.98,

    main_gear_pos = { -3.57, -4.44, 2.66 },
    main_gear_amortizer_direct_stroke        =  0.0,
    main_gear_amortizer_reversal_stroke      = -0.40,
    main_gear_amortizer_normal_weight_stroke =  0.0,
    main_gear_wheel_diameter                 =  1.62,

    mechanimations =
    {
        CentralStrut =
        {
            { Transition = { "Retract", "Extend" }, Sequence = { { C = { { "Arg", 0, "to", 1.0, "in", 9.0 } } } }, Flags = { "Reversible" } },
            { Transition = { "Extend", "Retract" }, Sequence = { { C = { { "Arg", 0, "to", 0.0, "in", 9.0 } } } }, Flags = { "Reversible", "StepsBackwards" } },
            { Transition = { "Any", "Collapse" },   Sequence = { { C = { { "Arg", 0, "to", 0.5, "in", 2.0 } } } } },
        },
        RightStrut =
        {
            { Transition = { "Retract", "Extend" }, Sequence = { { C = { { "Arg", 3, "to", 1.0, "in", 10.0 } } } }, Flags = { "Reversible" } },
            { Transition = { "Extend", "Retract" }, Sequence = { { C = { { "Arg", 3, "to", 0.0, "in", 10.0 } } } }, Flags = { "Reversible", "StepsBackwards" } },
            { Transition = { "Any", "Collapse" },   Sequence = { { C = { { "Arg", 3, "to", 0.5, "in", 2.0 } } } } },
        },
        LeftStrut =
        {
            { Transition = { "Retract", "Extend" }, Sequence = { { C = { { "Arg", 5, "to", 1.0, "in", 10.0 } } } }, Flags = { "Reversible" } },
            { Transition = { "Extend", "Retract" }, Sequence = { { C = { { "Arg", 5, "to", 0.0, "in", 10.0 } } } }, Flags = { "Reversible", "StepsBackwards" } },
            { Transition = { "Any", "Collapse" },   Sequence = { { C = { { "Arg", 5, "to", 0.5, "in", 2.0 } } } } },
        },
    },

    -------------------------------------------------------------------
    -- BOCAIS DOS MOTORES (efeito de exaustao) - estimado
    -------------------------------------------------------------------
    engines_nozzles =
    {
        [1] = -- motor esquerdo
        {
            pos               = { 3.0, 0.30, -6.20 },
            elevation         = 0,
            diameter          = 1.60,
            exhaust_length_ab = 0.0,
            exhaust_length_ab_K = 0.0,
            smokiness_level   = 0.05,
        },
        [2] = -- motor direito
        {
            pos               = { 3.0, 0.30, 6.20 },
            elevation         = 0,
            diameter          = 1.60,
            exhaust_length_ab = 0.0,
            exhaust_length_ab_K = 0.0,
            smokiness_level   = 0.05,
        },
    },

    -------------------------------------------------------------------
    -- TRIPULACAO
    -------------------------------------------------------------------
    crew_size = 3,
    crew_stations = "HumanOrchestra",
    crew_members =
    {
        [1] = { ejection_seat_name = 0, drop_canopy_name = 0, pos = { 11.5, 1.2, -0.65 }, bailout_arg = -1, role = "pilot",   role_display_name = _("Pilot") },
        [2] = { ejection_seat_name = 0, drop_canopy_name = 0, pos = { 11.5, 1.2,  0.65 }, bailout_arg = -1, role = "copilot", role_display_name = _("Copilot") },
        [3] = { ejection_seat_name = 0, drop_canopy_name = 0, pos = { -8.0, 0.5,  0.00 }, bailout_arg = -1, role = "gunner",  role_display_name = _("Loadmaster") },
    },

    -------------------------------------------------------------------
    -- SENSORES / DEFESA (o que a IA "enxerga")
    -------------------------------------------------------------------
    detection_range_max  = 0,
    radar_can_see_ground = false,
    CanopyGeometry =
    {
        azimuth   = { -160.0, 160.0 },
        elevation = {  -50.0,  50.0 },
    },
    Sensors =
    {
        OPTIC = { "TADS DVO" },
        RWR   = "Abstract RWR",
    },
    HumanRadio = { frequency = 251.0, editable = true,
                   minFrequency = 225.0, maxFrequency = 399.975,
                   modulation = MODULATION_AM },

    -------------------------------------------------------------------
    -- REABASTECIMENTO EM VOO (2 mangueiras/cestas sob as asas)
    -------------------------------------------------------------------
    singleInFlight          = true,
    stores_number           = 0,
    tanker_type             = 0,
    is_tanker               = true,
    refueling_points_count  = 2,
    refueling_points =
    {
        [1] = { pos = { -31.64, -7.11, -14.04 }, clientType = 3 },
        [2] = { pos = { -31.64, -7.11,  13.95 }, clientType = 3 },
    },
    Pylons = {},
    Tasks =
    {
        aircraft_task(Transport),
        aircraft_task(Refueling),
    },
    DefaultTask = aircraft_task(Refueling),
    --[[Countries   =
    {
        "Brazil",
        "Portugal",
        "Hungary",
        "Czech Republic",
        "The Netherlands",
        "Austria",
        "South Korea",
        "Sweden",
        "Slovakia",
        "Lithuania",
    },]]--

    -------------------------------------------------------------------
    -- FLIGHT MODEL (SFM definido em KC-390_SFM.lua)
    -------------------------------------------------------------------
    SFM_Data = KC390_SFM,
}

add_aircraft(KC_390)

-- =====================================================================
--  ARGUMENTOS DE ANIMACAO QUE O MODELO 3D (.edm) DEVE IMPLEMENTAR
--  (padrao DCS - o modelador deve nomear estes args no Blender/3ds Max)
-- ---------------------------------------------------------------------
--   0  : trem do nariz - retracao
--   2  : esterçamento da roda do nariz
--   3  : trem principal direito - retracao
--   5  : trem principal esquerdo - retracao
--   9  : aileron esquerdo
--  10  : aileron direito
--  11  : profundor (elevator)
--  12  : leme (rudder)
--  13  : flaps
--  15  : spoilers / freios de voo
--  18  : rampa de carga traseira (aberta/fechada)
--  19  : porta lateral 1
--  20  : porta lateral 2
--  21  : N1 / rotacao do fan - motor 1
--  22  : N1 / rotacao do fan - motor 2
--  28  : reversor de empuxo - motor 1
--  29  : reversor de empuxo - motor 2
--  30  : defletor esquerdo
--  31  : defletor direito
--  42  : extensao da mangueira/cesta esquerda
--  71  : extensao da mangueira/cesta direita
-- 101  : rotacao roda do nariz
-- 102  : rotacao roda principal direita
-- 103  : rotacao roda principal esquerda
-- =====================================================================
