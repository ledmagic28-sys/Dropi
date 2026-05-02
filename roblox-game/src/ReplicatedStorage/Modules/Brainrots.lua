-- Brainrots.lua
-- Catálogo de Brainrots (mascotas que generan dinero pasivo).
-- Income es dinero por tick (ver GameConfig.BRAINROT_TICK_RATE).

local Brainrots = {
    TungTungSahur = {
        DisplayName = "Tung Tung Sahur",
        Price = 100,
        Income = 1,
        Rarity = "Common",
    },
    BombardiroCrocodilo = {
        DisplayName = "Bombardiro Crocodilo",
        Price = 800,
        Income = 5,
        Rarity = "Uncommon",
    },
    TralaleroTralala = {
        DisplayName = "Tralalero Tralala",
        Price = 4500,
        Income = 22,
        Rarity = "Rare",
    },
    LiriliLarila = {
        DisplayName = "Lirili Larila",
        Price = 20000,
        Income = 90,
        Rarity = "Epic",
    },
    BrrBrrPatapim = {
        DisplayName = "Brr Brr Patapim",
        Price = 90000,
        Income = 350,
        Rarity = "Legendary",
    },
    ChimpanziniBananini = {
        DisplayName = "Chimpanzini Bananini",
        Price = 400000,
        Income = 1400,
        Rarity = "Mythic",
    },
    BallerinaCappuccina = {
        DisplayName = "Ballerina Cappuccina",
        Price = 2000000,
        Income = 6500,
        Rarity = "Secret",
    },
}

return Brainrots
