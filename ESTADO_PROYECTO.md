# Estado del Proyecto — Impresión Fotos Boda

**Última actualización:** 2026-11-19

## Descripción

App web Flask para Raspberry Pi 3B+ con impresora térmica DNP DS620. Los invitados de la boda acceden desde móvil/tablet, seleccionan una foto, la ajustan en un canvas (10×15 cm, 300 DPI) con plantillas decorativas e imprimen.

## Repositorio

https://github.com/drealfotograf/Impresion-tablet-raspi-dnp-

## Archivos del proyecto

| Archivo | Función |
|---------|---------|
| `app.py` | Backend Flask — endpoints API, watcher FTP |
| `templates/index.html` | Frontend completo (HTML/CSS/JS) |
| `requirements.txt` | Dependencia: `flask` |
| `static/mascaras/*.png` | Plantillas de marcos (3 incluidas) |
| `static/perfiles/` | Carpeta para perfiles ICC/ICM |
| `static/galeria/` | Carpeta para fotos importadas (con metadatos .meta.json) |
| `static/galeria/incoming/` | Carpeta donde el FTP deposita archivos de las cámaras |
| `setup_ftp.sh` | Script para instalar y configurar vsftpd en la Pi |
| `GUIA_CAMARAS_FTP.md` | Guía de configuración FTP para Canon 5D IV, R6 II, R5 II |
| `.claude/launch.json` | Config del dev server (Flask en puerto 5000) |
| `ESTADO_PROYECTO.md` | Este archivo — estado del proyecto |

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

### Galería de fotos
- Importar archivos desde móvil/tablet (multi-selección)
- Formatos soportados: JPG, PNG, TIFF, BMP, WebP, PSD, PSB, RAW (CR2, CR3, NEF, ARW, ORF, RW2, RAF, DNG, SRW, PEF, MRW, 3FR, RWL)
- Conversión automática de PSD/RAW a JPG usando ImageMagick y dcraw
- Grid de miniaturas con nombre del archivo original
- Tap en miniatura → carga como foto actual para editar e imprimir
- Eliminar fotos de la galería
- Panel colapsable
- Metadatos almacenados en archivos .meta.json
- Límite de upload: 100MB (para archivos RAW grandes)
- API: `GET /galeria`, `GET /galeria/version`, `POST /subir-galeria`, `POST /eliminar-galeria`

### Recepción directa desde cámaras Canon (FTP)
- Cámaras soportadas: Canon 5D Mark IV, R6 Mark II, R5 Mark II
- Servidor FTP (vsftpd) en la Raspberry Pi
- Carpeta `static/galeria/incoming/` para recepción FTP
- Hilo watcher que vigila la carpeta cada 3 segundos
- Detección de archivo estable (espera a que termine la transferencia)
- Conversión automática RAW → JPG al llegar
- JPGs pasan directamente a la galería
- Auto-refresh en frontend: polling cada 4 segundos vía `/galeria/version`
- Panel de galería se abre automáticamente cuando llegan fotos nuevas
- Script de setup: `setup_ftp.sh`
- Guía de configuración: `GUIA_CAMARAS_FTP.md`
- Soporta RAW y/o JPEG desde las cámaras

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
- Paneles colapsables: "Galería de fotos", "Ajustes de foto" y "Ajustes de impresión"
- Overlay con spinner al imprimir

## Stack técnico

- **Backend:** Python + Flask + threading (watcher FTP)
- **Frontend:** HTML5 Canvas, CSS custom properties, JS vanilla
- **Conversión:** ImageMagick (`convert`), dcraw (para RAW)
- **Impresión:** CUPS (`lp`), ImageMagick (`convert`)
- **FTP:** vsftpd (recepción desde cámaras Canon)
- **Hardware destino:** Raspberry Pi 3B+ + DNP DS620

## Dependencias del sistema (Raspberry Pi)

- Python 3 + Flask
- ImageMagick (para conversión PSD/TIFF/RAW y perfiles ICC)
- dcraw (para archivos RAW: CR2, NEF, ARW, etc.)
- CUPS (para impresión)
- vsftpd (para recepción FTP desde cámaras)

## Pendiente / Ideas futuras

- (vacío por ahora — añadir aquí lo que surja)
