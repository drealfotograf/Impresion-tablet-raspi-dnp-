#!/bin/bash
# ============================================================
# Setup FTP server en Raspberry Pi para recibir fotos de cámaras Canon
# Ejecutar como root: sudo bash setup_ftp.sh
# ============================================================

set -e

echo "=== Instalando vsftpd y dependencias ==="
apt-get update
apt-get install -y vsftpd imagemagick dcraw

echo "=== Creando usuario FTP para cámaras ==="
# Usuario: camara / Contraseña: boda2026
# Cambiar la contraseña si lo deseas
if ! id "camara" &>/dev/null; then
    useradd -m -s /usr/sbin/nologin camara
    echo "camara:boda2026" | chpasswd
    echo "Usuario 'camara' creado con contraseña 'boda2026'"
else
    echo "Usuario 'camara' ya existe"
fi

# Detectar ruta del proyecto (por defecto /home/pi/Web-Impres-raspi-boda)
PROYECTO_DIR="${1:-/home/pi/Web-Impres-raspi-boda}"
FTP_DIR="$PROYECTO_DIR/static/galeria/incoming"

echo "=== Creando carpeta FTP: $FTP_DIR ==="
mkdir -p "$FTP_DIR"
chown camara:camara "$FTP_DIR"
chmod 775 "$FTP_DIR"

# También asegurar que la carpeta galeria sea escribible
chown -R camara:camara "$PROYECTO_DIR/static/galeria"
chmod -R 775 "$PROYECTO_DIR/static/galeria"

echo "=== Configurando vsftpd ==="
cat > /etc/vsftpd.conf << 'VSFTPD'
# vsftpd config para recibir fotos de cámaras Canon
listen=YES
listen_ipv6=NO
anonymous_enable=NO
local_enable=YES
write_enable=YES
local_umask=022
dirmessage_enable=YES
use_localtime=YES
xferlog_enable=YES
connect_from_port_20=YES

# Enjaular usuario en su carpeta
chroot_local_user=YES
allow_writeable_chroot=YES

# Modo pasivo (necesario para algunas cámaras)
pasv_enable=YES
pasv_min_port=30000
pasv_max_port=30100

# Límites
max_clients=10
max_per_ip=5
local_max_rate=0

# Seguridad
ssl_enable=NO
userlist_enable=YES
userlist_deny=NO
userlist_file=/etc/vsftpd.userlist

# Log
xferlog_file=/var/log/vsftpd.log
log_ftp_protocol=YES
VSFTPD

# Lista de usuarios permitidos
echo "camara" > /etc/vsftpd.userlist

# Configurar home del usuario camara a la carpeta incoming
usermod -d "$FTP_DIR" camara

echo "=== Reiniciando vsftpd ==="
systemctl enable vsftpd
systemctl restart vsftpd

echo "=== Configurando firewall (si ufw está activo) ==="
if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow 20/tcp
    ufw allow 21/tcp
    ufw allow 30000:30100/tcp
    echo "Puertos FTP abiertos en firewall"
fi

# Obtener IP de la Raspberry Pi
IP=$(hostname -I | awk '{print $1}')

echo ""
echo "============================================"
echo "  FTP SERVER CONFIGURADO"
echo "============================================"
echo ""
echo "  Dirección: $IP"
echo "  Puerto:    21"
echo "  Usuario:   camara"
echo "  Contraseña: boda2026"
echo "  Carpeta:   $FTP_DIR"
echo ""
echo "  Las fotos enviadas por FTP aparecerán"
echo "  automáticamente en la galería de la app."
echo ""
echo "  CONFIGURACIÓN EN LAS CÁMARAS:"
echo "  - Servidor FTP: $IP"
echo "  - Puerto: 21"
echo "  - Usuario: camara"
echo "  - Contraseña: boda2026"
echo "  - Carpeta destino: / (raíz)"
echo "  - Modo pasivo: ON"
echo ""
echo "============================================"
