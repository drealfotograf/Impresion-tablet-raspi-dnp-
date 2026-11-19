from flask import Flask, render_template, request, jsonify, send_from_directory
import base64
import tempfile
import subprocess
import os
import glob
import re
import uuid
import json
import time
import threading
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB max upload

CARPETA_MASCARAS = os.path.join(app.static_folder, "mascaras")
CARPETA_PERFILES = os.path.join(app.static_folder, "perfiles")
CARPETA_GALERIA = os.path.join(app.static_folder, "galeria")
CARPETA_FTP = os.path.join(app.static_folder, "galeria", "incoming")

os.makedirs(CARPETA_MASCARAS, exist_ok=True)
os.makedirs(CARPETA_PERFILES, exist_ok=True)
os.makedirs(CARPETA_GALERIA, exist_ok=True)
os.makedirs(CARPETA_FTP, exist_ok=True)

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
EXTENSIONES_PSD = {".psd", ".psb"}
EXTENSIONES_RAW = {
    ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".raf", ".dng",
    ".srw", ".pef", ".mrw", ".3fr", ".rwl", ".raw",
}
TODAS_EXTENSIONES = EXTENSIONES_IMAGEN | EXTENSIONES_PSD | EXTENSIONES_RAW

# Track gallery version for efficient polling
galeria_version = 0
galeria_lock = threading.Lock()


def bump_galeria_version():
    global galeria_version
    with galeria_lock:
        galeria_version += 1


def convertir_a_jpg(ruta_origen, ruta_destino):
    """Convierte cualquier imagen/PSD/RAW a JPG usando ImageMagick/dcraw."""
    ext = os.path.splitext(ruta_origen)[1].lower()

    if ext in EXTENSIONES_RAW:
        ruta_ppm = ruta_origen + ".ppm"
        result = subprocess.run(
            ["dcraw", "-c", "-w", "-h", ruta_origen],
            capture_output=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout:
            with open(ruta_ppm, "wb") as f:
                f.write(result.stdout)
            conv = subprocess.run(
                ["convert", ruta_ppm, "-quality", "95", ruta_destino],
                capture_output=True, text=True, timeout=60,
            )
            try:
                os.unlink(ruta_ppm)
            except OSError:
                pass
            if conv.returncode == 0:
                return True

        conv = subprocess.run(
            ["convert", ruta_origen + "[0]", "-quality", "95", ruta_destino],
            capture_output=True, text=True, timeout=120,
        )
        return conv.returncode == 0

    conv = subprocess.run(
        ["convert", ruta_origen + "[0]", "-quality", "95", ruta_destino],
        capture_output=True, text=True, timeout=120,
    )
    return conv.returncode == 0


def procesar_archivo_ftp(ruta_archivo):
    """Procesa un archivo que llegó por FTP: convierte si es necesario y mueve a galería."""
    nombre = os.path.basename(ruta_archivo)
    ext = os.path.splitext(nombre)[1].lower()

    if ext not in TODAS_EXTENSIONES:
        return

    uid = uuid.uuid4().hex[:8]
    nombre_base = os.path.splitext(nombre)[0]

    if ext in (".jpg", ".jpeg"):
        nombre_final = f"{uid}_{nombre}"
        ruta_final = os.path.join(CARPETA_GALERIA, nombre_final)
        try:
            os.rename(ruta_archivo, ruta_final)
        except OSError:
            import shutil
            shutil.move(ruta_archivo, ruta_final)
    elif ext == ".png":
        nombre_final = f"{uid}_{nombre}"
        ruta_final = os.path.join(CARPETA_GALERIA, nombre_final)
        try:
            os.rename(ruta_archivo, ruta_final)
        except OSError:
            import shutil
            shutil.move(ruta_archivo, ruta_final)
    else:
        nombre_final = f"{uid}_{nombre_base}.jpg"
        ruta_final = os.path.join(CARPETA_GALERIA, nombre_final)
        if not convertir_a_jpg(ruta_archivo, ruta_final):
            print(f"[watcher] Error al convertir: {nombre}")
            return
        try:
            os.unlink(ruta_archivo)
        except OSError:
            pass

    meta_path = ruta_final + ".meta.json"
    with open(meta_path, "w") as f:
        json.dump({
            "nombre_original": nombre_base,
            "formato_original": ext,
            "origen": "ftp",
        }, f)

    bump_galeria_version()
    print(f"[watcher] Procesado: {nombre} → {nombre_final}")


def archivo_estable(ruta, espera=2):
    """Comprueba que el archivo no está siendo escrito (tamaño estable)."""
    try:
        s1 = os.path.getsize(ruta)
        time.sleep(espera)
        s2 = os.path.getsize(ruta)
        return s1 == s2 and s2 > 0
    except OSError:
        return False


def watcher_ftp():
    """Hilo que vigila la carpeta incoming/ para archivos nuevos por FTP."""
    print(f"[watcher] Vigilando carpeta FTP: {CARPETA_FTP}")
    while True:
        try:
            for nombre in os.listdir(CARPETA_FTP):
                ruta = os.path.join(CARPETA_FTP, nombre)
                if not os.path.isfile(ruta):
                    continue
                if nombre.startswith("."):
                    continue
                ext = os.path.splitext(nombre)[1].lower()
                if ext not in TODAS_EXTENSIONES:
                    continue
                if not archivo_estable(ruta):
                    continue
                try:
                    procesar_archivo_ftp(ruta)
                except Exception as e:
                    print(f"[watcher] Error procesando {nombre}: {e}")
        except Exception as e:
            print(f"[watcher] Error en bucle: {e}")
        time.sleep(3)


@app.route("/")
def index():
    return render_template("index.html")


# --- Galería ---

@app.route("/galeria")
def listar_galeria():
    fotos = []
    for nombre in sorted(os.listdir(CARPETA_GALERIA)):
        ruta = os.path.join(CARPETA_GALERIA, nombre)
        if not os.path.isfile(ruta):
            continue
        base, ext = os.path.splitext(nombre)
        if ext.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        meta_path = ruta + ".meta.json"
        nombre_original = base
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                nombre_original = meta.get("nombre_original", base)
            except Exception:
                pass
        fotos.append({
            "archivo": nombre,
            "nombre": nombre_original,
            "url": f"/static/galeria/{nombre}",
        })
    return jsonify(fotos)


@app.route("/galeria/version")
def galeria_version_endpoint():
    """Devuelve la versión actual de la galería para polling eficiente."""
    return jsonify({"version": galeria_version})


@app.route("/subir-galeria", methods=["POST"])
def subir_galeria():
    if "archivos" not in request.files:
        return jsonify({"error": "No se enviaron archivos"}), 400

    archivos = request.files.getlist("archivos")
    subidos = []
    errores = []

    for archivo in archivos:
        if not archivo.filename:
            continue
        nombre_orig = archivo.filename
        nombre_seg = secure_filename(nombre_orig)
        ext = os.path.splitext(nombre_seg)[1].lower()

        if ext not in TODAS_EXTENSIONES:
            errores.append(f"{nombre_orig}: formato no soportado")
            continue

        uid = uuid.uuid4().hex[:8]
        ruta_tmp = os.path.join(CARPETA_GALERIA, f"tmp_{uid}{ext}")
        archivo.save(ruta_tmp)

        if ext in (".jpg", ".jpeg", ".png"):
            nombre_final = f"{uid}_{nombre_seg}"
            ruta_final = os.path.join(CARPETA_GALERIA, nombre_final)
            os.rename(ruta_tmp, ruta_final)
        else:
            nombre_base = os.path.splitext(nombre_seg)[0]
            nombre_final = f"{uid}_{nombre_base}.jpg"
            ruta_final = os.path.join(CARPETA_GALERIA, nombre_final)

            if not convertir_a_jpg(ruta_tmp, ruta_final):
                errores.append(f"{nombre_orig}: error al convertir")
                try:
                    os.unlink(ruta_tmp)
                except OSError:
                    pass
                continue

            try:
                os.unlink(ruta_tmp)
            except OSError:
                pass

        meta_path = ruta_final + ".meta.json"
        with open(meta_path, "w") as f:
            json.dump({
                "nombre_original": os.path.splitext(nombre_orig)[0],
                "formato_original": ext,
            }, f)

        nombre_display = os.path.splitext(nombre_orig)[0]
        subidos.append({
            "archivo": nombre_final,
            "nombre": nombre_display,
            "url": f"/static/galeria/{nombre_final}",
        })

    if subidos:
        bump_galeria_version()

    return jsonify({"ok": True, "subidos": subidos, "errores": errores})


@app.route("/eliminar-galeria", methods=["POST"])
def eliminar_galeria():
    datos = request.get_json()
    if not datos or "archivo" not in datos:
        return jsonify({"error": "No se indicó archivo"}), 400

    nombre = os.path.basename(datos["archivo"])
    ruta = os.path.join(CARPETA_GALERIA, nombre)

    if not os.path.isfile(ruta):
        return jsonify({"error": "Archivo no encontrado"}), 404

    os.remove(ruta)
    meta_path = ruta + ".meta.json"
    if os.path.isfile(meta_path):
        os.remove(meta_path)

    bump_galeria_version()
    return jsonify({"ok": True})


# --- Máscaras ---

@app.route("/mascaras")
def listar_mascaras():
    archivos = sorted(glob.glob(os.path.join(CARPETA_MASCARAS, "*.png")))
    mascaras = []
    for ruta in archivos:
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        label = nombre.replace("_", " ").title()
        mascaras.append({
            "archivo": f"mascaras/{os.path.basename(ruta)}",
            "nombre": label,
        })
    return jsonify(mascaras)


@app.route("/subir-mascara", methods=["POST"])
def subir_mascara():
    if "archivo" not in request.files:
        return jsonify({"error": "No se envió archivo"}), 400

    archivo = request.files["archivo"]
    if not archivo.filename:
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    if not archivo.filename.lower().endswith(".png"):
        return jsonify({"error": "Solo se aceptan archivos PNG"}), 400

    nombre = secure_filename(archivo.filename)
    ruta = os.path.join(CARPETA_MASCARAS, nombre)
    archivo.save(ruta)

    nombre_base = os.path.splitext(nombre)[0]
    label = nombre_base.replace("_", " ").replace("-", " ").title()

    return jsonify({
        "ok": True,
        "mascara": {"archivo": f"mascaras/{nombre}", "nombre": label},
    })


@app.route("/eliminar-mascara", methods=["POST"])
def eliminar_mascara():
    datos = request.get_json()
    if not datos or "archivo" not in datos:
        return jsonify({"error": "No se indicó archivo"}), 400

    nombre_archivo = os.path.basename(datos["archivo"])
    ruta = os.path.join(CARPETA_MASCARAS, nombre_archivo)

    if not os.path.isfile(ruta):
        return jsonify({"error": "Archivo no encontrado"}), 404

    os.remove(ruta)
    return jsonify({"ok": True})


# --- Impresoras ---

@app.route("/impresoras")
def listar_impresoras():
    try:
        resultado = subprocess.run(
            ["lpstat", "-p", "-d"], capture_output=True, text=True, timeout=5
        )
        lineas = resultado.stdout.strip().splitlines()
    except Exception:
        return jsonify({"impresoras": [], "predeterminada": None})

    impresoras = []
    predeterminada = None

    for linea in lineas:
        m = re.match(r"printer\s+(\S+)\s+", linea)
        if m:
            impresoras.append(m.group(1))
        m2 = re.match(r"system default destination:\s+(\S+)", linea)
        if m2:
            predeterminada = m2.group(1)

    return jsonify({"impresoras": impresoras, "predeterminada": predeterminada})


# --- Perfiles de color ---

@app.route("/perfiles")
def listar_perfiles():
    perfiles = [{"archivo": "", "nombre": "Sin perfil (por defecto)"}]

    archivos = sorted(glob.glob(os.path.join(CARPETA_PERFILES, "*.ic[cm]")))
    for ruta in archivos:
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        label = nombre.replace("_", " ").replace("-", " ").title()
        perfiles.append({"archivo": os.path.basename(ruta), "nombre": label})

    return jsonify(perfiles)


@app.route("/subir-perfil", methods=["POST"])
def subir_perfil():
    if "archivo" not in request.files:
        return jsonify({"error": "No se envió archivo"}), 400

    archivo = request.files["archivo"]
    if not archivo.filename:
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in (".icc", ".icm"):
        return jsonify({"error": "Solo se aceptan archivos .icc o .icm"}), 400

    nombre = secure_filename(archivo.filename)
    ruta = os.path.join(CARPETA_PERFILES, nombre)
    archivo.save(ruta)

    nombre_base = os.path.splitext(nombre)[0]
    label = nombre_base.replace("_", " ").replace("-", " ").title()

    return jsonify({"ok": True, "perfil": {"archivo": nombre, "nombre": label}})


# --- Impresión ---

@app.route("/imprimir", methods=["POST"])
def imprimir():
    datos = request.get_json()
    if not datos or "imagen" not in datos:
        return jsonify({"error": "No se recibió imagen"}), 400

    copias = max(1, int(datos.get("copias", 1)))
    impresora = datos.get("impresora", "").strip() or None
    perfil_archivo = datos.get("perfil", "").strip()

    imagen_b64 = datos["imagen"]
    if "," in imagen_b64:
        imagen_b64 = imagen_b64.split(",", 1)[1]

    try:
        imagen_bytes = base64.b64decode(imagen_b64)
    except Exception:
        return jsonify({"error": "Imagen en formato inválido"}), 400

    ruta_imagen = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(imagen_bytes)
            ruta_imagen = tmp.name

        if perfil_archivo:
            ruta_perfil = os.path.join(CARPETA_PERFILES, secure_filename(perfil_archivo))
            if os.path.isfile(ruta_perfil):
                ruta_convertida = ruta_imagen + "_perfil.png"
                conv = subprocess.run(
                    ["convert", ruta_imagen, "-profile", ruta_perfil, ruta_convertida],
                    capture_output=True, text=True, timeout=30,
                )
                if conv.returncode == 0 and os.path.isfile(ruta_convertida):
                    os.unlink(ruta_imagen)
                    ruta_imagen = ruta_convertida

        cmd = ["lp", "-n", str(copias), "-o", "fit-to-page"]
        if impresora:
            cmd += ["-d", impresora]
        cmd.append(ruta_imagen)

        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if resultado.returncode != 0:
            return jsonify({"error": f"Error de impresión: {resultado.stderr}"}), 500

        return jsonify({"ok": True, "mensaje": f"Imprimiendo {copias} copia(s)…"})

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Tiempo de espera agotado"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if ruta_imagen and os.path.isfile(ruta_imagen):
            os.unlink(ruta_imagen)


if __name__ == "__main__":
    t = threading.Thread(target=watcher_ftp, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
