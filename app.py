from flask import Flask, render_template, request, jsonify, send_from_directory
import base64
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
CARPETA_COLA = os.path.join(app.static_folder, "cola")

os.makedirs(CARPETA_MASCARAS, exist_ok=True)
os.makedirs(CARPETA_PERFILES, exist_ok=True)
os.makedirs(CARPETA_GALERIA, exist_ok=True)
os.makedirs(CARPETA_FTP, exist_ok=True)
os.makedirs(CARPETA_COLA, exist_ok=True)

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


def guardar_trabajo(imagen_bytes, copias, impresora, perfil):
    job_id = uuid.uuid4().hex[:12]
    ruta_img = os.path.join(CARPETA_COLA, f"{job_id}.png")
    ruta_meta = os.path.join(CARPETA_COLA, f"{job_id}.json")
    with open(ruta_img, "wb") as f:
        f.write(imagen_bytes)
    with open(ruta_meta, "w") as f:
        json.dump({
            "id": job_id, "copias": copias,
            "impresora": impresora, "perfil": perfil,
            "estado": "pendiente", "creado": time.time(), "intentos": 0,
        }, f)
    return job_id


def ejecutar_trabajo(job_id):
    ruta_img = os.path.join(CARPETA_COLA, f"{job_id}.png")
    ruta_meta = os.path.join(CARPETA_COLA, f"{job_id}.json")
    if not os.path.isfile(ruta_meta) or not os.path.isfile(ruta_img):
        return False, "Trabajo no encontrado"

    with open(ruta_meta) as f:
        job = json.load(f)

    job["estado"] = "imprimiendo"
    job["intentos"] = job.get("intentos", 0) + 1
    with open(ruta_meta, "w") as f:
        json.dump(job, f)

    ruta_imagen = ruta_img
    ruta_perfil_tmp = None
    try:
        if job.get("perfil"):
            ruta_perfil = os.path.join(CARPETA_PERFILES, secure_filename(job["perfil"]))
            if os.path.isfile(ruta_perfil):
                ruta_perfil_tmp = ruta_img + "_perfil.png"
                conv = subprocess.run(
                    ["convert", ruta_img, "-profile", ruta_perfil, ruta_perfil_tmp],
                    capture_output=True, text=True, timeout=30,
                )
                if conv.returncode == 0 and os.path.isfile(ruta_perfil_tmp):
                    ruta_imagen = ruta_perfil_tmp

        cmd = ["lp", "-n", str(job["copias"]), "-o", "fit-to-page"]
        if job.get("impresora"):
            cmd += ["-d", job["impresora"]]
        cmd.append(ruta_imagen)

        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if resultado.returncode == 0:
            job["estado"] = "completado"
            with open(ruta_meta, "w") as f:
                json.dump(job, f)
            limpiar_trabajo(job_id)
            return True, f"Imprimiendo {job['copias']} copia(s)…"
        else:
            job["estado"] = "error"
            job["error"] = resultado.stderr.strip()
            with open(ruta_meta, "w") as f:
                json.dump(job, f)
            return False, resultado.stderr.strip()
    except subprocess.TimeoutExpired:
        job["estado"] = "error"
        job["error"] = "Tiempo agotado"
        with open(ruta_meta, "w") as f:
            json.dump(job, f)
        return False, "Tiempo agotado"
    except Exception as e:
        job["estado"] = "error"
        job["error"] = str(e)
        with open(ruta_meta, "w") as f:
            json.dump(job, f)
        return False, str(e)
    finally:
        if ruta_perfil_tmp and os.path.isfile(ruta_perfil_tmp):
            try:
                os.unlink(ruta_perfil_tmp)
            except OSError:
                pass


def limpiar_trabajo(job_id):
    for sufijo in (".png", ".json"):
        ruta = os.path.join(CARPETA_COLA, f"{job_id}{sufijo}")
        try:
            if os.path.isfile(ruta):
                os.unlink(ruta)
        except OSError:
            pass


def reanudar_cola():
    reanudados = 0
    for nombre in os.listdir(CARPETA_COLA):
        if not nombre.endswith(".json"):
            continue
        ruta = os.path.join(CARPETA_COLA, nombre)
        try:
            with open(ruta) as f:
                job = json.load(f)
            if job.get("estado") in ("pendiente", "imprimiendo"):
                job_id = job["id"]
                print(f"[cola] Reanudando trabajo: {job_id} ({job.get('intentos', 0)} intentos previos)")
                ok, msg = ejecutar_trabajo(job_id)
                print(f"[cola] {'OK' if ok else 'Error'}: {msg}")
                reanudados += 1
        except Exception as e:
            print(f"[cola] Error leyendo {nombre}: {e}")
    if reanudados:
        print(f"[cola] {reanudados} trabajo(s) reanudado(s) tras reinicio")


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
        m = re.match(r"printer\s+(\S+)\s+(.*)", linea)
        if m:
            nombre = m.group(1)
            info = m.group(2).strip()
            estado = "desconocido"
            if "idle" in info.lower():
                estado = "disponible"
            elif "printing" in info.lower():
                estado = "imprimiendo"
            elif "disabled" in info.lower() or "stopped" in info.lower():
                estado = "offline"
            impresoras.append({"nombre": nombre, "estado": estado, "info": info})
        m2 = re.match(r"system default destination:\s+(\S+)", linea)
        if m2:
            predeterminada = m2.group(1)

    return jsonify({"impresoras": impresoras, "predeterminada": predeterminada})


@app.route("/impresoras/buscar")
def buscar_impresoras():
    encontradas = []
    try:
        resultado = subprocess.run(
            ["lpinfo", "-v"], capture_output=True, text=True, timeout=10
        )
        for linea in resultado.stdout.strip().splitlines():
            parts = linea.strip().split(None, 1)
            if len(parts) == 2:
                tipo, uri = parts
                encontradas.append({"tipo": tipo, "uri": uri})
    except Exception:
        pass
    return jsonify({"encontradas": encontradas})


@app.route("/impresoras/agregar", methods=["POST"])
def agregar_impresora():
    datos = request.get_json()
    uri = datos.get("uri", "").strip()
    nombre = datos.get("nombre", "").strip()
    if not uri or not nombre:
        return jsonify({"error": "Faltan URI y nombre"}), 400
    nombre = re.sub(r"[^a-zA-Z0-9_-]", "_", nombre)
    try:
        resultado = subprocess.run(
            ["lpadmin", "-p", nombre, "-E", "-v", uri, "-m", "everywhere"],
            capture_output=True, text=True, timeout=15,
        )
        if resultado.returncode == 0:
            return jsonify({"ok": True, "nombre": nombre})
        return jsonify({"error": resultado.stderr.strip() or "Error al agregar"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cola")
def listar_cola():
    trabajos = []
    for nombre in sorted(os.listdir(CARPETA_COLA)):
        if not nombre.endswith(".json"):
            continue
        try:
            with open(os.path.join(CARPETA_COLA, nombre)) as f:
                job = json.load(f)
            trabajos.append({
                "id": job.get("id"),
                "estado": job.get("estado"),
                "copias": job.get("copias"),
                "impresora": job.get("impresora"),
                "intentos": job.get("intentos", 0),
                "error": job.get("error"),
            })
        except Exception:
            pass
    return jsonify(trabajos)


@app.route("/cola/reintentar", methods=["POST"])
def reintentar_trabajo():
    datos = request.get_json()
    job_id = datos.get("id", "").strip()
    if not job_id:
        return jsonify({"error": "Falta ID"}), 400
    job_id = re.sub(r"[^a-f0-9]", "", job_id)
    ok, msg = ejecutar_trabajo(job_id)
    if ok:
        return jsonify({"ok": True, "mensaje": msg})
    return jsonify({"error": msg}), 500


@app.route("/cola/limpiar", methods=["POST"])
def limpiar_cola():
    limpiados = 0
    for nombre in os.listdir(CARPETA_COLA):
        if not nombre.endswith(".json"):
            continue
        ruta = os.path.join(CARPETA_COLA, nombre)
        try:
            with open(ruta) as f:
                job = json.load(f)
            if job.get("estado") in ("completado", "error"):
                limpiar_trabajo(job["id"])
                limpiados += 1
        except Exception:
            pass
    return jsonify({"ok": True, "limpiados": limpiados})


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

    # Persistent queue: image saved to disk BEFORE printing
    job_id = guardar_trabajo(imagen_bytes, copias, impresora, perfil_archivo)
    ok, msg = ejecutar_trabajo(job_id)

    if ok:
        return jsonify({"ok": True, "mensaje": msg, "trabajo": job_id})
    return jsonify({"error": f"Error de impresión: {msg}"}), 500


if __name__ == "__main__":
    reanudar_cola()
    t = threading.Thread(target=watcher_ftp, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
