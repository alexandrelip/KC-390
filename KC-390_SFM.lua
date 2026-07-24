-- =====================================================================
--  KC-390_SFM.lua  -  Simplified Flight Model (SFM) do KC-390 Millennium
-- ---------------------------------------------------------------------
--  Modelo de voo em Lua usado pela IA do DCS (nao precisa de DLL).
--  Dados reais (Wikipedia / Embraer):
--    - 2 x IAE V2500-E5 ........ 139,4 kN (~14.215 kgf) cada
--    - Empuxo total estatico .... ~28.430 kgf
--    - Peso vazio ............... 35.000 kg
--    - MTOW ..................... 86.999 kg
--    - Combustivel interno ...... ~23.000 kg
--    - Vel. max ................. Mach 0,93 (988 km/h)
--    - Cruzeiro ................. Mach 0,80 (470 kn)
--    - Stall (flap 40) .......... 104 kn IAS
--    - Teto ..................... 11.000 m
--  OBS: a aerodinamica e a curva de empuxo abaixo sao uma aproximacao
--  coerente para um cargueiro a jato; ajuste fino deve ser feito no DCS
--  depois que o modelo 3D (.edm) estiver carregado.
-- =====================================================================

KC390_SFM =
{
    -----------------------------------------------------------------
    -- AERODINAMICA
    -----------------------------------------------------------------
    aerodynamics =
    {
        Cy0       =  0.18,    -- sustentacao com AoA zero (asa alta)
        Mzo       =  0.0,     -- momento de arfagem com AoA zero
        Mzalpha   =  4.50,    -- estabilidade longitudinal
        Mzalphadt =  0.40,    -- amortecimento de arfagem
        kjx       =  0.0030,  -- inercia rolagem
        kjz       =  0.0017,  -- inercia guinada
        Czbe      = -0.012,   -- forca lateral por derrapagem
        cx_gear   =  0.020,   -- arrasto do trem de pouso
        cy_flap   =  0.640,   -- ganho de sustentacao com flap
        cx_flap   =  0.040,   -- arrasto com flap
        cx_brk    =  0.000,   -- freio aerodinamico (n/a)

        -- table_data: { Mach , Cx0(arrasto) , Cya(curva de sust.) , B(arrasto induzido) , Bm , Cymax }
        table_data =
        {
            { 0.00, 0.0200, 0.0850, 0.1800, 0.30, 1.45 },
            { 0.20, 0.0200, 0.0850, 0.1800, 0.30, 1.45 },
            { 0.40, 0.0205, 0.0880, 0.1850, 0.31, 1.42 },
            { 0.60, 0.0220, 0.0950, 0.1950, 0.34, 1.30 },
            { 0.75, 0.0260, 0.1050, 0.2300, 0.45, 1.10 },
            { 0.80, 0.0320, 0.1080, 0.2700, 0.60, 1.00 },
            { 0.85, 0.0460, 0.1000, 0.3600, 0.90, 0.85 },
            { 0.93, 0.0900, 0.0850, 0.6000, 1.40, 0.70 },
        },
    },

    -----------------------------------------------------------------
    -- MOTOR (2 x IAE V2500-E5, turbofan, sem pos-combustao)
    -----------------------------------------------------------------
    engine =
    {
        Nmg          = 70.0,     -- rotacao marcha lenta (%)
        MaxThrust0   = 28430.0,  -- empuxo total estatico ao nivel do mar (kgf)
        MaxThrustH   = 7600.0,   -- empuxo total em altitude/alta velocidade (kgf) aprox.
        Nmax         = 100.0,    -- rotacao maxima (%)
        Ndop         = 100.0,    -- rotacao continua maxima (%)
        Cefmg        = 0.620,    -- consumo especifico em marcha lenta
        Cefmax       = 0.580,    -- consumo especifico (TSFC) maximo continuo
        dcx_eng      = 0.0120,   -- arrasto de motor inoperante
        hMaxEng      = 11.0,     -- altitude de teto do motor (km)
        dpdh_m       = 3600.0,   -- variacao de empuxo com altitude (continuo)
        dpdh_f       = 3600.0,   -- variacao de empuxo com altitude (maximo)
        typeng       = 0,        -- 0 = turbofan/turbojato
        MinRUD       = 0.0,      -- manete minima
        MaxRUD       = 1.0,      -- manete maxima (sem AB)
        MaksRUD      = 1.0,      -- manete militar
        ForsRUD      = 1.0,      -- manete pos-combustao (= militar, nao tem AB)

        -- table_data: { Mach , empuxo_relativo_maximo , empuxo_relativo_militar }
        -- (fator multiplicado por MaxThrust0; queda tipica de turbofan com Mach)
        table_data =
        {
            { 0.00, 1.000, 1.000 },
            { 0.20, 0.880, 0.880 },
            { 0.40, 0.760, 0.760 },
            { 0.60, 0.660, 0.660 },
            { 0.80, 0.560, 0.560 },
            { 0.93, 0.470, 0.470 },
        },
    },
}
