# SESSION — Cut Grass for Brainrots (Roblox)

> **Última actualización:** Respuesta #1 — Plan + esqueleto + módulos de configuración
> **Branch git:** `claude/roblox-grass-game-XIwVO`
> **Repo:** `ledmagic28-sys/dropi`

---

## 🔁 PROMPT PARA PEGAR EN UN NUEVO CLAUDE

Si pierdes esta sesión, copia TODO el bloque de abajo (incluyendo este SESSION.md adjunto) en un nuevo Claude:

```
Estoy creando un juego de Roblox tipo "Cut Grass for Brainrots"
(https://www.roblox.com/games/97365843755210/Cut-Grass-for-Brainrots).
Lenguaje: Lua. Herramienta: Roblox Studio (con Rojo opcional).

Estado actual del proyecto está en el archivo SESSION.md de la rama
`claude/roblox-grass-game-XIwVO` del repo `ledmagic28-sys/dropi`,
dentro de la carpeta `roblox-game/`.

Lee SESSION.md y continúa desde el "PRÓXIMO PASO" indicado allí.
En CADA respuesta que me des:
1. Implementa el siguiente paso del checklist.
2. Actualiza SESSION.md (marca lo completado, mueve "PRÓXIMO PASO").
3. Haz commit y push a la rama claude/roblox-grass-game-XIwVO.
4. Dame al final un resumen breve de qué cambió y el comando
   para clonar/pegar en mi Roblox Studio.

Idioma de respuesta: español.
```

---

## 🧱 Arquitectura

```
roblox-game/
├── default.project.json                   # Config Rojo
├── SESSION.md                             # Este archivo
└── src/
    ├── ReplicatedStorage/
    │   ├── Modules/
    │   │   ├── GameConfig.lua             ✅
    │   │   ├── Tools.lua                  ✅
    │   │   └── Brainrots.lua              ✅
    │   └── Remotes/                       (pendiente)
    ├── ServerScriptService/
    │   ├── DataManager.server.lua         (pendiente)
    │   ├── GrassSpawner.server.lua        (pendiente)
    │   ├── BrainrotIncome.server.lua      (pendiente)
    │   ├── ToolHandler.server.lua         (pendiente)
    │   └── ShopHandler.server.lua         (pendiente)
    ├── StarterPlayer/StarterPlayerScripts/
    │   └── ClientMain.client.lua          (pendiente)
    └── StarterGui/
        ├── HUD.lua                        (pendiente)
        ├── ShopGui.lua                    (pendiente)
        └── BrainrotsGui.lua               (pendiente)
```

---

## ✅ Checklist global

- [x] **Paso 1** — Estructura de carpetas + `default.project.json`
- [x] **Paso 2** — `GameConfig.lua` (constantes globales)
- [x] **Paso 3** — `Tools.lua` (6 herramientas: Hoz Básica → Cosechadora Neón)
- [x] **Paso 4** — `Brainrots.lua` (7 brainrots: Tung Tung → Ballerina Cappuccina)
- [ ] **Paso 5** — Crear RemoteEvents en `ReplicatedStorage/Remotes`
- [ ] **Paso 6** — `DataManager.server.lua` (DataStore: dinero, herramientas, brainrots)
- [ ] **Paso 7** — `GrassSpawner.server.lua` (genera/regenera el pasto)
- [ ] **Paso 8** — `ToolHandler.server.lua` (cortar pasto, dar dinero)
- [ ] **Paso 9** — `BrainrotIncome.server.lua` (dinero pasivo cada tick)
- [ ] **Paso 10** — `ShopHandler.server.lua` (comprar tools y brainrots)
- [ ] **Paso 11** — `ClientMain.client.lua` (input + equipar herramienta)
- [ ] **Paso 12** — `HUD.lua` (mostrar dinero, herramienta equipada)
- [ ] **Paso 13** — `ShopGui.lua` (UI tienda de tools)
- [ ] **Paso 14** — `BrainrotsGui.lua` (UI tienda + inventario brainrots)
- [ ] **Paso 15** — Plot/parcela del jugador donde aparecen brainrots
- [ ] **Paso 16** — Sistema de rebirth (opcional)
- [ ] **Paso 17** — Probar en Roblox Studio y ajustar balance

---

## 🎯 PRÓXIMO PASO

**Paso 5:** Crear los RemoteEvents en `src/ReplicatedStorage/Remotes/`:
- `CutGrass` (cliente → servidor: avisa que cortó pasto)
- `BuyTool` (cliente → servidor: comprar herramienta)
- `EquipTool` (cliente → servidor: equipar herramienta)
- `BuyBrainrot` (cliente → servidor: comprar brainrot)
- `EquipBrainrot` (cliente → servidor: equipar brainrot)
- `UpdateData` (servidor → cliente: enviar datos del jugador)

Implementación: usar un único script `init.server.lua` o un módulo que cree todos los RemoteEvents al iniciar el servidor.

---

## 📦 Cómo instalar en Roblox Studio

### Opción A — Rojo (recomendado, sincroniza automáticamente)
1. Instala Rojo: https://rojo.space/docs/v7/getting-started/installation/
2. En Studio, instala el plugin Rojo.
3. Clona este repo: `git clone -b claude/roblox-grass-game-XIwVO https://github.com/ledmagic28-sys/dropi.git`
4. Entra a `roblox-game/` y corre: `rojo serve`
5. En Studio, abre el plugin Rojo → Connect.

### Opción B — Pegar manualmente
1. Abre Roblox Studio.
2. Por cada archivo `.lua`, crea un `Script` o `ModuleScript` en la ubicación que indica la ruta en `src/`.
3. Copia y pega el contenido.

---

## 📝 Notas de diseño

- **Económia:** la primera herramienta es gratis (BasicScythe) y da 1$/corte.
  El primer brainrot cuesta 100$ y da 1$/seg → ROI de 100s.
- **Brainrots:** sigue la línea de los "Italian Brainrots" virales para coherencia
  con el juego original.
- **Filtering Enabled:** activado por defecto, todo el dinero se valida en servidor.
- **Anti-cheat:** el cliente NUNCA decide cuánto dinero ganar; manda solo
  "corté pasto en la posición X" y el servidor valida cooldown + radio.
