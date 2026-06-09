import pandas as pd
import glob
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# =========================================================
# 1. MÉTRICAS
# =========================================================

dfs_m = []
ruta_metricas = os.path.join("datos", "metricas")

logger.info("--- LECTURA DE MÉTRICAS ---")

for juego in os.listdir(ruta_metricas):

    ruta_juego = os.path.join(ruta_metricas, juego)

    if not os.path.isdir(ruta_juego):
        continue

    for archivo in glob.glob(os.path.join(ruta_juego, "*.csv")):

        df = pd.read_csv(archivo)

        # Normalizar participante
        df["participant"] = (
            df["participant"]
            .astype(str)
            .str.replace(r'\s+', '', regex=True)
            .str.lower()
        )

        # Normalizar nombre del juego
        df["juego_norm"] = (
            juego.strip()
            .lower()
            .replace(" ", "")
        )

        dfs_m.append(df)

# Concatenar métricas
df_m = pd.concat(dfs_m, ignore_index=True)

# Variables derivadas
df_m["pupil_mean"] = df_m[["pupil_left", "pupil_right"]].mean(axis=1)

df_m["movimiento"] = (
    df_m[["gyro_x", "gyro_y", "gyro_z"]]
    .abs()
    .sum(axis=1)
)

# Features agregadas
df_feat = (
    df_m
    .groupby(["participant", "juego_norm"])
    .agg({
        "pupil_mean": ["mean", "std"],
        "movimiento": "mean",
        "gaze2d_x": "std",
        "gaze2d_y": "std"
    })
    .reset_index()
)

df_feat.columns = [
    "participant",
    "juego_norm",
    "pupil_mean",
    "pupil_std",
    "movimiento_mean",
    "gaze_x_var",
    "gaze_y_var"
]

# =========================================================
# 2. CUESTIONARIOS
# =========================================================

mapeo_nasa = {
    "nasa_mental": ["mental"],
    "nasa_fisica": ["física", "fisica"],
    "nasa_temporal": ["rapidez", "tiempos"],
    "nasa_rendimiento": ["rendimiento"],
    "nasa_esfuerzo": ["esfuerzo"],
    "nasa_frustracion": [
        "te sentiste frustrado",
        "medida te sentiste frustrado"
    ]
}

mapa_emocion = {
    "nada": 1,
    "casi nada": 2,
    "poco": 3,
    "ni mucho ni poco": 4,
    "bastante": 5,
    "mucho": 6,
    "muchísimo": 7
}

positivas = [
    "alegría",
    "felicidad/placer",
    "entusiasmo/excitación",
    "satisfacción",
    "relax"
]

negativas = [
    "asco",
    "ira/enfado",
    "ansiedad",
    "miedo",
    "frustración",
    "tristeza/depresión",
    "fatiga/cansancio",
    "aburrimiento"
]

dfs_q = []

ruta_cuestionarios = os.path.join("datos", "cuestionarios")

archivos_q = (
    glob.glob(os.path.join(ruta_cuestionarios, "*.csv")) +
    glob.glob(os.path.join(ruta_cuestionarios, "*.xlsx"))
)

logger.info("--- PROCESANDO CUESTIONARIOS ---")

for archivo in archivos_q:

    nombre_fich = os.path.basename(archivo).lower()

    # -----------------------------------------------------
    # Detectar juego
    # -----------------------------------------------------

    if "fall" in nombre_fich:
        juego_nombre = "fallguys"

    elif "sonic" in nombre_fich:
        juego_nombre = "sonic"

    elif "tetris" in nombre_fich:
        juego_nombre = "tetris"

    else:
        juego_nombre = "desconocido"

    # -----------------------------------------------------
    # Leer archivo
    # -----------------------------------------------------

    if archivo.endswith(".csv"):
        df = pd.read_csv(archivo)
    else:
        df = pd.read_excel(archivo)

    # Normalizar columnas
    df.columns = (
        df.columns
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
        .str.lower()
    )

    print("\nCOLUMNAS ORIGINALES:")
    print(df.columns.tolist())

    # -----------------------------------------------------
    # Renombrar columnas NASA + participant
    # -----------------------------------------------------

    nuevas_columnas = {}
    asignadas = set()

    for col_real in df.columns:

        col_norm = col_real.lower()

        # Buscar columnas NASA
        for clave, keywords in mapeo_nasa.items():

            if clave in asignadas:
                continue

            if any(k in col_norm for k in keywords):

                nuevas_columnas[col_real] = clave
                asignadas.add(clave)

                break

        # Buscar participant
        if (
            "código de participación" in col_norm
            and "participant" not in asignadas
        ):
            nuevas_columnas[col_real] = "participant"
            asignadas.add("participant")

    print("\nCOLUMNAS RENOMBRADAS:")
    print(nuevas_columnas)

    # Aplicar renombrado
    df = df.rename(columns=nuevas_columnas)

    # -----------------------------------------------------
    # Convertir emociones
    # -----------------------------------------------------

    for col in df.columns:

        if col in positivas + negativas:

            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.lower()
                .map(mapa_emocion)
            )

    # -----------------------------------------------------
    # Filtrar columnas importantes
    # -----------------------------------------------------

    cols_interes = (
        ["participant"] +
        list(mapeo_nasa.keys()) +
        positivas +
        negativas
    )

    df = df[
        [c for c in df.columns if c in cols_interes]
    ].copy()

    # -----------------------------------------------------
    # Normalizar participante
    # -----------------------------------------------------

    if "participant" in df.columns:

        df["participant"] = (
            df["participant"]
            .astype(str)
            .str.replace(r'\s+', '', regex=True)
            .str.lower()
        )

        df["juego_norm"] = juego_nombre

        dfs_q.append(df)

# =========================================================
# 3. CONCATENAR CUESTIONARIOS
# =========================================================

df_q = pd.concat(dfs_q, ignore_index=True)

# Convertir NASA a numérico
for col in list(mapeo_nasa.keys()):

    if col in df_q.columns:

        df_q[col] = pd.to_numeric(
            df_q[col],
            errors='coerce'
        )

# Invertir rendimiento
df_q["nasa_rendimiento_inv"] = 11 - df_q["nasa_rendimiento"]

# =========================================================
# 4. VARIABLES EMOCIONALES
# =========================================================

df_q["afecto_positivo"] = df_q[
    [c for c in positivas if c in df_q.columns]
].mean(axis=1)

df_q["afecto_negativo"] = df_q[
    [c for c in negativas if c in df_q.columns]
].mean(axis=1)

df_q["balance_emocional"] = (
    df_q["afecto_positivo"] -
    df_q["afecto_negativo"]
)

# NASA total
df_q["nasa_carga_total"] = df_q[
    [
        "nasa_mental",
        "nasa_fisica",
        "nasa_temporal",
        "nasa_esfuerzo",
        "nasa_frustracion",
        "nasa_rendimiento_inv"
    ]
].mean(axis=1)

# =========================================================
# 5. MERGE FINAL
# =========================================================

logger.info(f"Juegos en métricas: {df_feat['juego_norm'].unique()}")
logger.info(f"Juegos en cuestionarios: {df_q['juego_norm'].unique()}")

df_final = pd.merge(
    df_feat,
    df_q,
    on=["participant", "juego_norm"],
    how="left"
)

# =========================================================
# 6. INFORME
# =========================================================

con_datos = df_final["nasa_carga_total"].notna().sum()

logger.info(
    f"ÉXITO: {con_datos} filas tienen datos completos de cuestionario."
)

print("\nVALORES NASA FRUSTRACIÓN:")
print(df_final["nasa_frustracion"].head())

# =========================================================
# 7. EXPORTAR
# =========================================================

df_final.to_csv(
    "datos_finales_procesados.csv",
    index=False
)

logger.info("Archivo exportado correctamente.")