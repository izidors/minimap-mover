# Promise Minimap Mover

A lightweight, unofficial **World of Tanks** client modification that lets you reposition the in-battle minimap with a keyboard-and-mouse shortcut. The mod remembers the minimap's position and size between battles.

**Version in the supplied source:** `1.1.2`

## Features

- Drag the minimap to a preferred position during battle.
- Keep ordinary **Ctrl + click** minimap actions available, including pings.
- Save the minimap offset and size to a local configuration file.
- Restore the saved position when the minimap is initialized in a new battle.
- Limit movement so that part of the minimap remains on screen.
- Refresh the minimap display after moving it and restore its selected size.

## Controls

| Action | Control |
| --- | --- |
| Normal minimap action (such as ping) | **Ctrl + click** on the minimap |
| Move the minimap | Hold **Ctrl + Shift**, then **left-click and drag** |

Movement begins after a **5-pixel drag threshold** to distinguish a click from a drag. Release the mouse button to finish moving and save the position.

**Note:** The current implementation uses Ctrl + Shift as the drag modifier and does not perform a minimap hit-test before beginning a drag. Avoid dragging elsewhere on screen while holding this shortcut.

## Installation

1. Obtain a `.wotmod` package built for your World of Tanks client version.
2. Copy the package into the game's matching mod-version directory:

   ```text
   World_of_Tanks/mods/<game-version>/
   ```

3. Start World of Tanks and enter a battle.
4. Hold **Ctrl + Shift** and drag with the left mouse button to position the minimap.

The source supplied here does not establish which specific World of Tanks client builds have been tested. Check compatibility before installing a release.

## Configuration

The mod automatically creates a configuration file under the World of Tanks preferences directory:

```text
<preferences>/mods/promise/minimap_mover.cfg
```

It stores three space-separated values:

```text
offset_x offset_y size_index
```

- `offset_x`: horizontal offset from the minimap's original layout position.
- `offset_y`: vertical offset from the minimap's original layout position.
- `size_index`: saved minimap size index (`0` through `5`).

The configuration is written when a drag finishes. If no valid saved position exists, the mod uses the default position. To reset the saved placement, close the game and remove `minimap_mover.cfg`.

## Building from source

The project layout includes `src/` and `build.py`. Build requirements and command-line options depend on the actual `build.py` implementation, which was not included in the supplied source excerpt.

Inspect the build script before compiling:

```powershell
python .\build.py --help
```

The mod source uses Python 2-era APIs (including `long`) and World of Tanks client modules such as `BigWorld`, `Keys`, and `MinimapComponent`; it is not a standalone Python application.

## How it works

The mod hooks the minimap component's battle lifecycle, records its original position, and applies a saved offset. While the movement shortcut is active, it polls the mouse position and updates the minimap display. When dragging ends, it saves the offset and refreshes the minimap size. It also unregisters its input handlers and cancels active callbacks during cleanup.

## Troubleshooting

**Position is not remembered:** Check whether the game can write to `<preferences>/mods/promise/minimap_mover.cfg`.

**Minimap size or display looks wrong:** Try leaving and re-entering a battle. The mod includes a display refresh that temporarily changes and then restores the selected minimap size.

**Mod does not load:** Verify that the `.wotmod` was built for the installed World of Tanks version and check the game's logs for `MinimapMover` messages.

## Disclaimer

This is an independent, unofficial community modification for **World of Tanks**. It is not affiliated with or endorsed by Wargaming. Compatibility and permitted use are subject to the current game client and applicable game/mod policies.

## License

No license has been specified in the supplied source. Add a `LICENSE` file if you intend to grant others permission to reuse, modify, or redistribute the code.
