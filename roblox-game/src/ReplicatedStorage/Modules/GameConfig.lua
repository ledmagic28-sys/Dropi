-- GameConfig.lua
-- Configuración global del juego

local GameConfig = {}

GameConfig.STARTING_MONEY = 0
GameConfig.STARTING_TOOL = "BasicScythe"

-- Cada cuántos segundos los Brainrots generan dinero
GameConfig.BRAINROT_TICK_RATE = 1

-- Tiempo en segundos para que el pasto vuelva a crecer
GameConfig.GRASS_REGROW_TIME = 8

-- Cantidad máxima de Brainrots que un jugador puede tener equipados
GameConfig.MAX_EQUIPPED_BRAINROTS = 3

-- DataStore
GameConfig.DATASTORE_NAME = "CutGrassPlayerData_v1"

return GameConfig
