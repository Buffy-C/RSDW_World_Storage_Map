# RSDW Storage Map

An interactive storage-container map for **RuneScape: Dragonwilds**, built from live save files.

Click any marker on the map to see exactly what's inside that chest, rack, or lumber storage — item names, counts, and durability — refreshed directly from your save files.

![RSDW Storage Map screenshot](screenshot.png)

---

## Features

- **Full world map** background rendered with Leaflet.js CRS.Simple — hand-stitched from wiki map tiles in Figma
- **All storage types**: Iron/Oak/Ash/Personal Chests, Crates, Weapon Racks, Armour Mannequins, Cape Racks, Cape Hooks, Lumber Storages, Fishing Barrels, Tackle Boxes, Lodestones
- **Multi-world support**: switch between any of your save slots — the parser auto-detects all worlds in your `Saved/SaveGames/` folder
- **Lodestone markers**: all teleportation lodestones shown as gold diamond markers for quick navigation reference
- **Live item names**: resolved from `guid_map.json` and an optional Master Checklist spreadsheet
- **Filter by type or zone**, search by item name or chest ID
- **↻ Refresh from save** button — re-parses your `.sav` files and reloads the map without leaving the browser
- **⚙ Calibration tool** — align the map to your own world image by entering known world coordinates; adjusts the entire coordinate system without touching any code
- **Accurate item assignment**: binary analysis of the save format; items assigned to the nearest preceding container in file space (handles multi-stack lumber correctly)

---

## Requirements

- **Python 3.9+**
- `pandas` and `openpyxl` (only needed if you use a Master Checklist for extra item name resolution)

```
pip install pandas openpyxl
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/rsdw-storage-map.git
cd rsdw-storage-map
```

### 2. Add your save files

Copy your RuneScape: Dragonwilds save files into the `Saved/SaveGames/` folder:

```
rsdw-storage-map/
└── Saved/
    └── SaveGames/
        ├── MyWorld.sav
        ├── AnotherWorld.sav
        └── ...
```

Your saves are typically found at:
```
%LOCALAPPDATA%\Jagex\RuneScape Dragonwilds\Saved\SaveGames\
```

### 3. Add a Master Checklist (optional)

If you maintain a `Master_Checklist_RSDW_v2.xlsx` with an **Item ID Directory** sheet (columns: GUID | Display Name), place it in the root folder. The parser will use it to resolve any item GUIDs not covered by `guid_map.json`.

### 4. Run the map

Double-click **`Start_Map.bat`** (Windows), or run:

```bash
python server.py
```

Then open **http://localhost:8765/RSDW_Tile_Map.html** in your browser.

---

## Refreshing after playing

Click the **↻ Refresh from save** button in the toolbar. The server re-runs `parse_worlds.py` against your `.sav` files (~10–30 seconds) and reloads the map automatically.

You can also run the parser standalone at any time:

```bash
python parse_worlds.py
```

This writes a `world_<WorldName>.json` file for each detected save into the root folder.

---

## File structure

```
rsdw-storage-map/
├── RSDW_Tile_Map.html      # Main map (open via server, not file://)
├── parse_worlds.py         # Save file parser — generates world JSON files
├── server.py               # Local HTTP server with /refresh endpoint
├── Start_Map.bat           # Windows launcher (runs server.py)
├── guid_map.json               # Item GUID → name database (community data)
├── world_map_compressed.jpg    # World map background — 6MB compressed (default)
└── .gitignore
```

**Generated at runtime (not committed):**
```
world_<WorldName>.json   (one per save slot)
```

---

## How the parser works

The `.sav` file is a binary format. The parser:

1. Reads the **class table** at the start of the file to map class indices to storage type names
2. Scans for **SPWN** blocks (spawned building objects) and records their type, position in the file, and world coordinates (X/Y as 64-bit doubles)
3. Scans the file for **ItemData JSON blobs** — `{"GUID": "...", "ItemData": "...", "Count": N}` — embedded in the binary stream
4. Assigns each item blob to the **nearest preceding SPWN** in file space (binary analysis confirmed items always follow their container in file order)
5. Deduplicates by **instance GUID** so duplicate inventory copies don't inflate counts
6. Resolves item GUIDs to display names via `guid_map.json` and an optional Master Checklist

---

## Calibration

If you use a different map image, markers may appear offset. The ⚙ Calibrate button in the toolbar lets you align the coordinate system to your image without touching any code.

Click **Calibrate**, then enter the known world X/Y bounds of your image:

- **World X min** — the westernmost X coordinate visible in your image
- **World X max** — the easternmost X coordinate
- **Raw Y max** — the southernmost Y coordinate (Y increases southward in Dragonwilds)
- **Raw Y min** — the northernmost Y coordinate

You can find world coordinates by hovering over known landmarks in-game (the coordinates are shown in the debug overlay). Once set, all markers reposition instantly. The values are saved in the page for the session.

The default calibration for the included `world_map_compressed.jpg` is:
```
X min: 0        X max: 302,000
Y min: -101,400  Y max: 202,000
```

---

## Zone bounds

Zones are defined in `RSDW_Tile_Map.html` as `[xMin, xMax, yMin, yMax, yOffset, name]` in world-space coordinates. Edit the `ZONES` array to adjust or add zones as the game world expands.

Current zones: Dowdun, Dowdun Reach Base, West Dowdun, Bramblemead, Bramblemead Valley, Temple Woods, Fractured Plains, Bleakfields Valley, Coalridge Pass.

---

## Adding a new world save

In `parse_worlds.py`, add an entry to the `WORLDS` dict:

```python
WORLDS = {
    'WorldOne':   'WorldOne.sav',
    'WorldTwo':   'WorldTwo.sav',
    'MyNewWorld': 'MyNewWorld.sav',   # ← add here
}
```

Then add a `<option>` for it in the world selector in `RSDW_Tile_Map.html`.

---

## Map image

Two versions of the world map are included:

| File | Size | Quality | Use case |
|------|------|---------|----------|
| `world_map_compressed.jpg` | 6 MB | Good — barely distinguishable from full quality at normal zoom | **Default** — fast download, recommended for most users |
| `world_map.png` | 67 MB | Full quality original | Best for high-DPI screens or zooming in closely |

The map loads `world_map_compressed.jpg` automatically. If you prefer the full quality version, place `world_map.png` in the same folder — it will be used as a fallback if the compressed version is absent.

> **Note:** `world_map.png` is not committed to the repo due to its size. It is available on request or can be generated by upscaling `world_map_compressed.jpg`.

The map image was hand-assembled in Figma by [Buffy-C](https://github.com/Buffy-C) from regional map tiles sourced from the [RuneScape: Dragonwilds Wiki](https://dragonwilds.runescape.wiki/). Original map artwork © Jagex Ltd.

---

## Credits

- **[Elleandria/RS-Dragonwilds-Editor](https://github.com/Elleandria/RS-Dragonwilds-Editor)** — `guid_map.json` item GUID database, extracted from game assets via CUE4Parse. This project would not have working item names without that work.
- **[Dragonwilds Wiki](https://dragonwilds.runescape.wiki/)** — additional item reference data.
- **Jagex** — RuneScape: Dragonwilds. Map tiles are in-game screenshots included for personal/community reference only.
