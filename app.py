from flask import Flask, render_template, request, jsonify
import base64
import tempfile
import subprocess
import os
import glob
import re
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

CARPETA_MASCARAS = os.path.join(app.static_folder, "mascaras")
CARPETA_PERFILES = os.path.join(app.static_folder, "perfiles")

os.makedirs(CARPETA_MASCARAS, exist_ok=True)
os.makedirs(CARPETA_PERFILES, exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


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
        # "printer DNP_DS620 is idle." or "printer DNP_DS620 disabled since..."
        m = re.match(r"printer\s+(\S+)\s+", linea)
        if m:
            impresoras.append(m.group(1))
        # "system default destination: DNP_DS620"
        m2 = re.match(r"system default destination:\s+(\S+)", linea)
        if m2:
            predeterminada = m2.group(1)

    return jsonify({"impresoras": impresoras, "predeterminada": predeterminada})


# --- Perfiles de color ---

@app.route("/perfiles")
def listar_perfiles():
    # Perfiles ICC encontrados en la carpeta de perfiles
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

    # Si hay perfil ICC, aplicar con convert de ImageMagick
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
    app.run(host="0.0.0.0", port=5000, debug=False)
