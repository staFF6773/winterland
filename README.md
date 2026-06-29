# Winterland

Modern desktop wallpaper manager for **Arch Linux** and the **Hyprland** compositor. Manage static and animated wallpapers efficiently.

## Features

### Static wallpapers
- Supports PNG, JPG, JPEG, WEBP, and BMP
- Preview before applying
- One-click apply
- Remembers last used wallpaper
- Per-monitor wallpapers via `hyprpaper`

### Animated wallpapers
- Supports MP4, WEBM, and GIF
- Integration with `mpvpaper` for Wayland
- Play, pause, stop, and restart controls
- Target monitor selection

### Library
- Automatic folder scanning
- Grid thumbnails
- Search by name
- Filters for images, videos, or GIFs
- Favorites
- Wallpaper history

### Settings
- Customizable wallpaper folder
- Autostart with Hyprland
- Restore last wallpaper on login
- JSON persistence

### Hyprland integration
- Automatic monitor detection with `hyprctl`
- Compatible with `hyprpaper` and `mpvpaper`
- Apply changes without restarting Hyprland

### Extras
- Drag and drop to add wallpapers
- Auto-rotation
- Playlists
- Keyboard shortcuts
- Multi-monitor support
- Notifications on wallpaper change
- Export and import configuration

## Requirements

### System dependencies
```bash
sudo pacman -S hyprland hyprpaper mpvpaper mpv python python-pip
```

### Python dependencies
```bash
pip install -r requirements.txt
```

## Installation

### Manual (pip)
```bash
git clone https://github.com/staFF6773/winterland.git
cd winterland
pip install -e .
```

### PKGBUILD (local build)
```bash
git clone https://github.com/staFF6773/winterland.git
cd winterland
makepkg -si
```

## Usage

```bash
winterland
```

### Autostart with Hyprland
Add the following line to `~/.config/hypr/hyprland.conf`:
```
exec-once = winterland
```

## Project structure

```
winterland/
├── main.py                 # Entry point
├── gui/                    # GUI (PySide6)
│   ├── components/         # Reusable components
│   └── ...
├── backend/                # Business logic
├── config/                 # Configuration management
├── assets/                 # Resources (icons, QSS styles)
├── utils/                  # Utilities
└── wallpapers/             # Default wallpaper folder
```

## Keyboard shortcuts

| Shortcut        | Action                          |
|-----------------|---------------------------------|
| `Ctrl+O`        | Add wallpaper                   |
| `Ctrl+F`        | Search                          |
| `Ctrl+S`        | Save configuration              |
| `Ctrl+,`        | Open settings                   |
| `Space`         | Play/Pause (animated)           |
| `R`             | Rotate to next wallpaper        |
| `F`             | Toggle favorite                 |
| `Del`           | Remove from library             |
| `F11`           | Fullscreen                      |

## License

GNU General Public License v3.0 or later
