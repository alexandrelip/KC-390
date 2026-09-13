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
        Cy0      =  0.0,
        Mzalfa   =  4.50,
        Mzalfadt =  0.80,
        kjx      =  2.85,
        kjz      =  0.0085,
        Czbe     = -0.012,
        cx_gear  =  0.020,
        cy_flap  =  0.640,
        cx_flap  =  0.040,
        cx_brk   =  0.040,

        -- { Mach, Cx0, Cya, B2, B4, roll-rate, AoA limite, Cy max }
        table_data =
        {
            { 0.00, 0.0210, 0.085, 0.045, 0.00001, 0.45, 16, 1.45 },
            { 0.20, 0.0210, 0.085, 0.045, 0.00001, 0.55, 16, 1.45 },
            { 0.40, 0.0220, 0.088, 0.047, 0.00002, 0.65, 15, 1.40 },
            { 0.60, 0.0240, 0.095, 0.052, 0.00005, 0.75, 13, 1.30 },
            { 0.75, 0.0300, 0.103, 0.065, 0.00050, 0.65, 10, 1.10 },
            { 0.80, 0.0380, 0.105, 0.085, 0.00150, 0.55,  8, 1.00 },
            { 0.85, 0.0550, 0.098, 0.120, 0.00400, 0.45,  7, 0.85 },
            { 0.93, 0.0950, 0.085, 0.180, 0.00800, 0.35,  6, 0.70 },
            { 1.00, 0.1200, 0.070, 0.240, 0.01200, 0.25,  5, 0.55 },
        },
    },

    -----------------------------------------------------------------
    -- MOTOR (2 x IAE V2500-E5, turbofan, sem pos-combustao)
    -----------------------------------------------------------------
    engine =
    {
        Nmg      = 70.0,
        MinRUD   = 0.0,
        MaxRUD   = 1.0,
        MaksRUD  = 1.0,
        ForsRUD  = 1.0,
        type     = "TurboFan",
        Nominal_RPM = 14950,
        Nominal_Fan_RPM = 5650,
        hMaxEng  = 14.0,
        dcx_eng  = 0.0120,
        cemax    = 0.580,
        cefor    = 0.580,
        dpdh_m   = 7000.0,
        dpdh_f   = 7000.0,

        -- { Mach, empuxo maximo total (N), empuxo forcado total (N) }
        table_data =
        {
            { 0.00, 278800, 278800 },
            { 0.20, 245300, 245300 },
            { 0.40, 211900, 211900 },
            { 0.60, 184000, 184000 },
            { 0.80, 156100, 156100 },
            { 0.93, 131000, 131000 },
            { 1.00, 118000, 118000 },
        },
    },
}
