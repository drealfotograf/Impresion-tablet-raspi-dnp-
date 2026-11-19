# Guía: Enviar fotos desde cámaras Canon a la Raspberry Pi por WiFi/FTP

## Requisitos previos

1. Raspberry Pi conectada a la red WiFi (o por cable Ethernet)
2. Haber ejecutado `sudo bash setup_ftp.sh` en la Pi
3. Las cámaras conectadas a la **misma red WiFi** que la Pi

## Datos de conexión FTP

| Campo | Valor |
|-------|-------|
| Servidor | IP de la Raspberry Pi (ej: `192.168.1.100`) |
| Puerto | 21 |
| Usuario | `camara` |
| Contraseña | `boda2026` |
| Carpeta destino | `/` (raíz) |
| Modo pasivo | ON |

> Para ver la IP de tu Pi: ejecuta `hostname -I` en la terminal de la Pi.

---

## Canon EOS 5D Mark IV

### Configurar conexión WiFi

1. **MENU → Pestaña de configuración (llave inglesa) → Wi-Fi/NFC → Activar**
2. Pulsa **SET** → Selecciona **Función Wi-Fi**
3. Elige **Transferir imgs a servidor FTP** (icono de servidor)
4. Selecciona **Buscar red** → Elige tu red WiFi → Introduce contraseña WiFi
5. **Configuración de dirección IP**: Ajuste automático (DHCP)

### Configurar servidor FTP

1. En **Ajuste del servidor FTP**:
   - **Nombre del servidor**: IP de la Pi (ej: `192.168.1.100`)
   - **Número de puerto**: `21`
   - **Modo pasivo**: **ON**
2. **Ajuste de inicio de sesión**:
   - **Nombre de inicio**: `camara`
   - **Contraseña**: `boda2026`
3. **Carpeta de destino**:
   - **Carpeta raíz** → Seleccionar
4. Cuando veas pantalla de confirmación **"Conectado"**, está listo

### Enviar fotos

- **Envío automático tras disparar**: MENU → Wi-Fi → Transferencia FTP → **Envío automático** → **Activar**
- **Envío manual**: Reproduce la foto → Pulsa **SET** → **Enviar imagen** → Selecciona imágenes

### Elegir qué enviar

- MENU → Wi-Fi → Transferencia FTP → **Tipo de archivo a transferir**:
  - **RAW+JPEG → Enviar ambos** (más lento, máxima calidad)
  - **RAW+JPEG → Solo JPEG** (más rápido, recomendado para boda)
  - **RAW+JPEG → Solo RAW** (si quieres editar en la app)

---

## Canon EOS R6 Mark II

### Configurar conexión WiFi

1. **MENU → Pestaña de comunicación (📶) → Conexión Wi-Fi/Bluetooth → Wi-Fi: Activar**
2. **Función Wi-Fi** → **Transferir imgs a servidor FTP**
3. **Añadir dispositivo** → **Buscar red** → Selecciona tu WiFi → Contraseña
4. Configuración IP: **Automática**

### Configurar servidor FTP

1. **Config. servidor FTP**:
   - **Dirección del servidor**: IP de la Pi
   - **Nº de puerto**: `21`
   - **Modo pasivo**: **ON**
2. **Inicio de sesión**:
   - **Nombre de usuario**: `camara`
   - **Contraseña**: `boda2026`
3. **Carpeta de destino**: **Carpeta raíz**
4. Espera a ver **"Conectado al servidor FTP"**

### Envío automático (recomendado para boda)

1. MENU → Comunicación → **Transferencia FTP** → **Transferencia automática** → **Activar**
2. **Imgs para transferir**: Elige **JPEG** o **RAW+JPEG** o **Solo RAW**

### Envío por lotes

1. MENU → Comunicación → **Transferencia FTP** → **Transf. por lotes**
2. Selecciona rango de imágenes → **Transferir**

### Consejo: Envío mientras disparas

La R6 II puede enviar en segundo plano mientras sigues disparando. Con **transferencia automática activada**, cada foto se envía al servidor FTP inmediatamente después de capturarla.

---

## Canon EOS R5 Mark II

### Configurar conexión WiFi

1. **MENU → Pestaña de comunicación (📶) → Conexión Wi-Fi/Bluetooth → Wi-Fi: Activar**
2. **Función Wi-Fi** → **Transferir imgs a servidor FTP**
3. **Añadir dispositivo** → **Buscar red** → Red WiFi → Contraseña
4. Configuración IP: **Automática**

### Configurar servidor FTP

1. **Config. servidor FTP**:
   - **Dirección**: IP de la Pi
   - **Puerto**: `21`
   - **Modo pasivo**: **ON**
2. **Inicio de sesión**:
   - **Usuario**: `camara`
   - **Contraseña**: `boda2026`
3. **Carpeta destino**: **Carpeta raíz**

### Envío automático

1. MENU → Comunicación → **Transferencia FTP** → **Transf. automática** → **Activar**
2. **Tipo de imagen**: JPEG, RAW, o RAW+JPEG

### WiFi 5GHz (más rápido)

La R5 II soporta WiFi 5GHz. Si tu router lo soporta:
1. En la config WiFi, elige la red de 5GHz
2. Los archivos se transferirán más rápido (~2x)

### Transferencia a través de FTPS (opcional)

La R5 II soporta FTPS (FTP seguro). Para activarlo:
1. Config servidor FTP → FTPS → **ON**
2. Requiere configuración SSL adicional en vsftpd (ver sección avanzada)

---

## Recomendaciones para la boda

### Configuración recomendada

| Ajuste | Valor |
|--------|-------|
| Formato de disparo | RAW + JPEG (doble slot si es posible) |
| FTP envía | **Solo JPEG** (rápido, invitados ven foto al instante) |
| Transferencia automática | **ON** |
| Calidad JPEG | L (máxima) |

### ¿Por qué enviar JPEG y no RAW?

| | JPEG (L) | RAW (CR2/CR3) |
|---|---|---|
| Tamaño | ~8-15 MB | ~30-60 MB |
| Tiempo WiFi | ~2-5 seg | ~10-30 seg |
| Calidad impresión | Excelente para 10×15 | Máxima |
| Buffer cámara | No se llena | Se puede llenar |

**Recomendación**: Dispara en RAW+JPEG, envía **solo JPEG** por FTP. Los RAW quedan en la tarjeta para postproducción posterior.

### Si necesitas enviar RAW

- Configura **Solo RAW** en transferencia FTP
- El servidor los convierte automáticamente a JPG (tarda ~5-15 seg por foto)
- Mientras se convierte, la foto no aparece en la galería
- Una vez convertido, aparece automáticamente

### Consejo: Red WiFi dedicada

Para máxima fiabilidad, usa un **router dedicado** solo para las cámaras y la Pi:
1. Router WiFi portátil (TP-Link, etc.)
2. SSID: `BODA-FOTOS` (nombre fácil de recordar)
3. Sin conexión a Internet (evita interferencias)
4. Canal fijo (1, 6 u 11 en 2.4GHz)
5. Pi conectada por cable Ethernet al router → más estable

### Múltiples cámaras simultáneas

Las 3 cámaras pueden enviar fotos al mismo servidor FTP a la vez. Cada foto recibe un nombre único (UUID) al procesarse, así que no hay conflictos.

---

## Verificar que funciona

1. Desde la Pi, comprueba que vsftpd está activo:
   ```bash
   sudo systemctl status vsftpd
   ```

2. Haz una foto de prueba con la cámara configurada

3. Mira los logs:
   ```bash
   # Log del FTP
   tail -f /var/log/vsftpd.log
   
   # Log del watcher (en la terminal donde corre app.py)
   # Verás: [watcher] Procesado: IMG_1234.CR2 → abc12345_IMG_1234.jpg
   ```

4. Abre la app en el navegador → la foto aparece en la galería automáticamente

## Solución de problemas

| Problema | Solución |
|----------|----------|
| Cámara no conecta al WiFi | Verificar contraseña WiFi, acercar cámara al router |
| "Error de conexión FTP" | Comprobar IP del servidor, `ping <IP>` desde otro dispositivo |
| Foto no aparece en galería | Esperar ~5 seg (conversión RAW). Revisar log del watcher |
| Transferencia muy lenta | Usar WiFi 5GHz si disponible, o enviar solo JPEG |
| "Login failed" | Verificar usuario `camara` / contraseña `boda2026` |
| vsftpd no arranca | `sudo systemctl status vsftpd` para ver el error |
