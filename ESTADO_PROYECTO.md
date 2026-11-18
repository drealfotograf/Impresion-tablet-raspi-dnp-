# Estado del Proyecto — Impresión Fotos Boda

**Última actualización:** 2026-11-18

## Descripción

App web Flask para Raspberry Pi 3B+ con impresora térmica DNP DS620. Los invitados de la boda acceden desde móvil/tablet, seleccionan una foto, la ajustan en un canvas (10×15 cm, 300 DPI) con plantillas decorativas e imprimen.

## Repositorio

https://github.com/drealfotograf/Impresion-tablet-raspi-dnp-

## Archivos del proyecto

| Archivo | Función |
|---------|---------|
| `app.py` | Backend Flask — endpoints API |
| `templates/index.html` | Frontend completo (HTML/CSS/JS) |
| `requirements.txt` | Dependencia: `flask` |
| `static/mascaras/*.png` | Plantillas de marcos (3 incluidas) |
| `static/perfiles/` | Carpeta para perfiles ICC/ICM |
| `.claude/launch.json` | Config del dev server (Flask en puerto 5000) |

## Funcionalidades implementadas

### Canvas (1800×1200 px)
- Aspecto 3:2 (10×15 cm a 300 DPI)
- Cover-fit automático de la imagen
- Zoom con pellizco (touch) y rueda del ratón
- Drag con un dedo (touch) y click-arrastrar (mouse)
- El zoom sigue el centro del gesto

### Ajustes de foto (solo afectan la foto, NO la plantilla)
- Luminosidad (-100 a +100)
- Contraste (-100 a +100)
- Saturación (-100 a +100)
- Viveza (-100 a +100) — saturación selectiva en píxeles menos saturados
- Color / Tono (-180° a +180°) — hue-rotate
- Enfoque (0 a 100) — unsharp mask
- Claridad (0 a 100) — unsharp mask con radio mayor
- Textura (0 a 100) — unsharp mask con radio fino
- Blanco y negro (toggle on/off)
- Botón "Restablecer ajustes"

### Plantillas / Máscaras PNG
- Carrusel horizontal con miniaturas
- 3 incluidas: Marco Clásico, Sin Marco, Viñeta
- Subir plantillas PNG personalizadas (botón "+")
- Eliminar plantillas (botón "×")
- Se renderizan ENCIMA de la foto (no les afectan los filtros)
- API: `GET /mascaras`, `POST /subir-mascara`, `POST /eliminar-mascara`

### Impresión
- Copias ilimitadas (selector - / +)
- Selección de impresora (dropdown, cargado desde CUPS vía `lpstat`)
- Selección de perfil de color ICC/ICM
- Subida de perfiles ICC personalizados
- Impresión vía comando `lp` con `-o fit-to-page`
- Aplicación de perfil ICC con ImageMagick `convert -profile`
- API: `GET /impresoras`, `GET /perfiles`, `POST /subir-perfil`, `POST /imprimir`

### Diseño
- Estilo minimalista moderno
- Colores empresa: azul (#1e3d5c) y arena (#c9a96e)
- Fuente: Inter (Google Fonts)
- Responsive (mobile-first)
- Paneles colapsables: "Ajustes de foto" y "Ajustes de impresión"
- Overlay con spinner al imprimir

## Stack técnico

- **Backend:** Python + Flask
- **Frontend:** HTML5 Canvas, CSS custom properties, JS vanilla
- **Impresión:** CUPS (`lp`), ImageMagick (`convert`)
- **Hardware destino:** Raspberry Pi 3B+ + DNP DS620

## Pendiente / Ideas futuras

- (vacío por ahora — añadir aquí lo que surja)
