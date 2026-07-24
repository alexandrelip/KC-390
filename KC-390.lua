-- =====================================================================
--  KC-390.lua  -  Definicao da aeronave (banco de dados do DCS)
-- ---------------------------------------------------------------------
--  Embraer KC-390 Millennium  -  APENAS IA  (add_aircraft)
--  Usa o flight model SFM definido em KC-390_SFM.lua (global KC390_SFM).
--
--  IMPORTANTE: as coordenadas de motor, trem de pouso, ponta de asa e
--  os argumentos de animacao (arg_*) precisam BATER com o modelo 3D
--  (.edm). Os valores abaixo sao estimativas com base nas dimensoes
--  reais e devem ser calibrados quando o .edm existir.
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
            desrt       = "KC-390_destr",    -- modelo destruido (opcional)
            fire        = { 360, 3 },        -- fogo no solo apos destruicao: 360s, 3m
            username    = "KC-390",
            index       = WSTYPE_PLACEHOLDER,
            classname   = "lLandPlane",
            positioning = "BYNORMAL",
        },
    },

    -- Tipo de operacao de pista (CTOL = decolagem/pouso convencional)
    takeoff_and_landing_type = 1,

    mapclasskey = "P0091000064",
    attribute   = { wsType_Air, wsType_Airplane, wsType_Cruiser, WSTYPE_PLACEHOLDER,
                    "Transports",
                  },
    Categories  = {},

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
    -- TREM DE POUSO (coordenadas estimadas - calibrar no .edm)
    -------------------------------------------------------------------
    tand_gear_max = 1.5,
    nose_gear_pos = { 13.20, -3.80, 0.0 },
    nose_gear_amortizer_direct_stroke        =  0.0,
    nose_gear_amortizer_reversal_stroke      = -0.40,
    nose_gear_amortizer_normal_weight_stroke = -0.40,
    nose_gear_wheel_diameter                 =  0.90,

    main_gear_pos = { -1.50, -3.90, 1.90 },
    main_gear_amortizer_direct_stroke        =  0.0,
    main_gear_amortizer_reversal_stroke      = -0.40,
    main_gear_amortizer_normal_weight_stroke = -0.40,
    main_gear_wheel_diameter                 =  1.20,

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
    -- REABASTECIMENTO EM VOO (KC-390 e tanker probe-and-drogue)
    -------------------------------------------------------------------
    is_tanker                 = true,
    tanker_type               = 1,          -- PROBE_AND_DROGUE
    air_refuel_receptacle_pos = { 12.0, 1.5, 0.0 },

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
--   1  : amortecedor do nariz
--   2  : esterçamento da roda do nariz
--   3  : trem principal direito - retracao
--   4  : amortecedor principal direito
--   5  : trem principal esquerdo - retracao
--   6  : amortecedor principal esquerdo
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
--  38  : luzes de navegacao
--  39  : luzes de pouso (faroletes)
-- 101  : rotacao roda do nariz
-- 102  : rotacao roda principal direita
-- 103  : rotacao roda principal esquerda
-- =====================================================================
