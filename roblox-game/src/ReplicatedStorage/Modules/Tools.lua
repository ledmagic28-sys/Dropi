-- Tools.lua
-- Catálogo de herramientas para cortar pasto.
-- Cada herramienta define: precio, dinero por corte, radio de corte y velocidad.

local Tools = {
    BasicScythe = {
        DisplayName = "Hoz Básica",
        Price = 0,
        MoneyPerCut = 1,
        CutRadius = 4,
        CutCooldown = 0.6,
        Rarity = "Common",
    },
    SteelScythe = {
        DisplayName = "Hoz de Acero",
        Price = 250,
        MoneyPerCut = 3,
        CutRadius = 5,
        CutCooldown = 0.5,
        Rarity = "Common",
    },
    GoldScythe = {
        DisplayName = "Hoz Dorada",
        Price = 1500,
        MoneyPerCut = 8,
        CutRadius = 6,
        CutCooldown = 0.45,
        Rarity = "Rare",
    },
    DiamondScythe = {
        DisplayName = "Hoz de Diamante",
        Price = 8000,
        MoneyPerCut = 20,
        CutRadius = 7,
        CutCooldown = 0.4,
        Rarity = "Epic",
    },
    LawnMower = {
        DisplayName = "Cortacésped",
        Price = 35000,
        MoneyPerCut = 55,
        CutRadius = 10,
        CutCooldown = 0.3,
        Rarity = "Legendary",
    },
    NeonHarvester = {
        DisplayName = "Cosechadora Neón",
        Price = 150000,
        MoneyPerCut = 180,
        CutRadius = 14,
        CutCooldown = 0.25,
        Rarity = "Mythic",
    },
}

return Tools
