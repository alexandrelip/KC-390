livery = {
	{"kc-390_wing_spoiler B-C",	DIFFUSE			,	"kc-390_wing_spoiler_b-c_c", false};
	{"kc-390_wing_spoiler A-D",	DIFFUSE			,	"kc-390_wing_spoiler_a-d_c", false};
	{"kc-390_wing_slat",	DIFFUSE			,	"kc-390_wing_slat_c", false};
	{"kc-390_wing_flap_a",	DIFFUSE			,	"kc-390_wing_flap_a_c", false};
	{"kc-390_wing_flap_b",	DIFFUSE			,	"kc-390_wing_flap_b_c", false};
	{"kc-390_wing",	DIFFUSE			,	"kc-390_wing_c", false};
	{"kc-390_wing_aileron",	DIFFUSE			,	"kc-390_wing_aileron_c", false};
	{"revo_tanque_1",	DIFFUSE			,	"revo_tanque_1_c", false};
	{"revo_pod_1",	DIFFUSE			,	"revo_pod_1_c", false};
	{"kc-390_ramp_estrut",	DIFFUSE			,	"kc-390_ramp_estrut_c", false};
	{"oculos_vidro",	DIFFUSE			,	"sunscreenb", false};
	{"crew",	DIFFUSE			,	"soutear", false};
	{"iae_metal",	DIFFUSE			,	"kc-390_iae_turbinmetal_c", false};
	{"iae",	DIFFUSE			,	"kc-390_iae_turbine_c", false};
	{"kc-390_HUD_glass",	DIFFUSE			,	"ppehud390", false};
	{"kc-390_HUD_glass",	SELF_ILLUMINATION	,	"ppehud390_n", false};
	{"kc-390_elevator",	DIFFUSE			,	"kc-390_elevator_c", false};
	{"kc-390_horiz_stabiliser",	DIFFUSE			,	"kc-390_horiz_stabiliser_c", false};
	{"kc-390_gear_ld",	DIFFUSE			,	"kc-390_gear_ld_c", false};
	{"kc-390_gear_nose",	DIFFUSE			,	"kc-390_gear_nose_c", false};
	{"kc-390_gear_le",	DIFFUSE			,	"kc-390_gear_le_c", false};
	{"kc-390_fuselage g",	DIFFUSE			,	"kc-390_fuselage_g_c", false};
	{"kc-390_fuselage f2",	DIFFUSE			,	"kc-390_fuselage_f2_c", false};
	{"kc390_light_form",	DIFFUSE			,	"form", false};
	{"kc390_light_form",	SELF_ILLUMINATION	,	"form", false};
	{"kc-390_fuselage a5",	DIFFUSE			,	"kc-390_fuselage_a5_c", false};
	{"kc-390_fuselage a4",	DIFFUSE			,	"kc-390_fuselage_a4_c", false};
	{"kc-390_fuselage a3",	DIFFUSE			,	"kc-390_fuselage_a3_c", false};
	{"kc-390_fuselage a2",	DIFFUSE			,	"kc-390_fuselage_a2_c", false};
	{"kc-390_IAE novo",	DIFFUSE			,	"airbus_ex_baremetalgloss_iae_c", false};
	{"kc-390_flightdeck_3",	DIFFUSE			,	"kc-390_flightdeck_3_c", false};
	{"kc-390_flightdeck_2",	DIFFUSE			,	"kc-390_flightdeck_2_c", false};
	{"iae_suporte",	DIFFUSE			,	"kc-390_iae_suporte_c", false};
	{"kc-390_fusel_estrut2",	DIFFUSE			,	"kc-390_ramp_estrut_c", false};
	{"kc-390_fuselage f",	DIFFUSE			,	"kc-390_fuselage_f_c", false};
	{"kc-390_glass",	DIFFUSE			,	"glass_s", false};
	{"kc-390_flightdeck_1",	DIFFUSE			,	"kc-390_flightdeck_1_c", false};
	{"kc-390_cargo_1",	DIFFUSE			,	"kc-390_cargo_1_c", false};
	{"kc-390_cargo_2",	DIFFUSE			,	"kc-390_cargo_2_c", false};
	{"kc-390_blast deflector",	DIFFUSE			,	"kc-390_blast_deflector_c", false};
	{"kc-390_fusel_estrut",	DIFFUSE			,	"kc-390_fusel_estrut_c", false};
	{"kc-390_fuselage a1",	DIFFUSE			,	"kc-390_fuselage_a1_c", false};
	{"kc-390_glass_gold",	DIFFUSE			,	"gold_t", false};
	{"kc-390_fuselage b",	DIFFUSE			,	"kc-390_fuselage_b_c", false};
}

name = _("FAB 2852 - Forca Aerea Brasileira")
countries = { "BRA" }
custom_args = {
}

--[[
	{ "AT27_PARTS",   DIFFUSE,               "at-27_parts",                 true },
	{ "AT27_PARTS",   NORMAL_MAP,            "at-27_parts_nm",              true },
	{ "AT27_PARTS",   ROUGHNESS_METALLIC,    "at-27_parts_RoughMet",        true },
}

name = "T-27 Air Demonstration Squadron (EDA) 1987"
countries = {}
custom_args =
{
	[810] = 0, -- Pilot helmet
	[811] = 0, -- Helmet visor 0-close, 1-open
	[812] = 0, -- Front helmet visor 0-close, 1-open
	[813] = 1, -- 0: colete, 1: no colete

	[814] = 0, -- Pilot helmet
	[815] = 0, -- Helmet visor 0-close, 1-open
	[816] = 0, -- Front helmet visor 0-close, 1-open
	[817] = 1, -- 0: colete, 1: no colete
	
	[1000] = 0, -- Hud: 1, Base HUD: 0.5, No Hud: 0

	[820] = 0, -- Antennas
	[821] = 1, -- Down antenna
	[822] = 0, -- Down antenna
	[823] = 0, -- Top canopy antenna
	[824] = 1, -- Small antenna
	[825] = 0, -- Internal canopy support
	[826] = 0, -- 0: Tucano, 1: Tucano shorts
	[827] = 0, -- Air brake
}
]]--
