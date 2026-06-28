# Wallpaper Manager para Hyprland

Aplicación de escritorio moderna para **Arch Linux** y el compositor **Hyprland** que permite administrar fondos de pantalla estáticos y animados de forma eficiente.

## Características

### Fondos estáticos
- Soporte para PNG, JPG, JPEG, WEBP y BMP.
- Vista previa antes de aplicar.
- Aplicación con un clic.
- Recordatorio del último fondo utilizado.
- Un fondo diferente para cada monitor mediante `hyprpaper`.

### Fondos animados
- Soporte para MP4, WEBM y GIF.
- Integración con `mpvpaper` para Wayland.
- Controles de reproducción, pausa, detención y reinicio.
- Selección del monitor destino.

### Biblioteca
- Escaneo automático de carpetas.
- Miniaturas en cuadrícula.
- Búsqueda por nombre.
- Filtros por imágenes, vídeos o GIF.
- Favoritos.
- Historial de fondos aplicados.

### Configuración
- Carpeta principal configurable.
- Inicio automático con Hyprland.
- Restauración del último fondo al iniciar sesión.
- Persistencia en JSON.

### Integración con Hyprland
- Detección automática de monitores con `hyprctl`.
- Compatibilidad con `hyprpaper` y `mpvpaper`.
- Aplicación de cambios sin reiniciar Hyprland.

### Extras
- Arrastrar y soltar para añadir wallpapers.
- Rotación automática de fondos.
- Listas de reproducción.
- Atajos de teclado.
- Soporte multi-monitor.
- Notificaciones al cambiar de fondo.
- Exportación e importación de configuraciones.

## Requisitos

### Dependencias del sistema
```bash
sudo pacman -S hyprland hyprpaper mpvpaper mpv python python-pip
```

### Dependencias de Python
```bash
pip install -r requirements.txt
```

## Instalación

### Desde AUR (recomendado)
```bash
yay -S wallpaper-manager
```

### Manual
```bash
git clone https://github.com/example/wallpaper-manager.git
cd wallpaper-manager
pip install -e .
```

## Uso

```bash
wallpaper-manager
```

### Inicio automático con Hyprland
Añade la siguiente línea a `~/.config/hypr/hyprland.conf`:
```
exec-once = wallpaper-manager
```

## Estructura del proyecto

```
wallpaper-manager/
├── main.py                 # Punto de entrada
├── gui/                    # Interfaz gráfica (PySide6)
│   ├── components/         # Componentes reutilizables
│   └── ...
├── backend/                # Lógica de negocio
├── config/                 # Gestión de configuración
├── assets/                 # Recursos (iconos SVG, estilos QSS)
├── utils/                  # Utilidades
└── wallpapers/             # Carpeta por defecto
```

## Atajos de teclado

| Atajo            | Acción                          |
|------------------|---------------------------------|
| `Ctrl+O`         | Añadir wallpaper                |
| `Ctrl+F`         | Buscar                          |
| `Ctrl+S`         | Guardar configuración           |
| `Ctrl+,`         | Abrir ajustes                   |
| `Espacio`        | Reproducir/Pausar (animado)     |
| `R`              | Rotar al siguiente wallpaper    |
| `F`              | Marcar como favorito            |
| `Del`            | Eliminar de la biblioteca       |
| `F11`            | Pantalla completa               |

## Licencia

MIT
