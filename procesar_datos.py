import pandas as pd
import glob
import os

dfs_m = []

ruta_metricas = os.path.join("datos", "metricas")
for juego in os.listdir(ruta_metricas):
    ruta_juego = os.path.join(ruta_metricas, juego)
    if not os.path.isdir(ruta_juego):
        continue
    for archivo in glob.glob(os.path.join(ruta_juego, "*.csv")):
        df = pd.read_csv(archivo)
        df["juego"] = juego
        dfs_m.append(df)

if not dfs_m:
    raise RuntimeError("No se encontraron métricas")

df_m = pd.concat(dfs_m, ignore_index=True)
df_m["pupil_mean"] = df_m[["pupil_left", "pupil_right"]].mean(axis=1)
df_m["movimiento"] = df_m[["gyro_x", "gyro_y", "gyro_z"]].abs().sum(axis=1)

df_feat = df_m.groupby(["participant", "juego"]).agg({
    "pupil_mean": ["mean", "std"],
    "movimiento": "mean",
    "gaze2d_x": "std",
    "gaze2d_y": "std"
})

df_feat.columns = ["pupil_mean", "pupil_std", "movimiento_mean", "gaze_x_var", "gaze_y_var"]
df_feat = df_feat.reset_index()

dfs_q = []

ruta_cuestionarios = os.path.join("datos", "cuestionarios")
archivos = glob.glob(os.path.join(ruta_cuestionarios, "*.csv")) + glob.glob(os.path.join(ruta_cuestionarios, "*.xlsx"))

for archivo in archivos:
    juego = os.path.basename(archivo).split(" - ")[0]
    if archivo.endswith(".csv"):
        df = pd.read_csv(archivo)
    else:
        df = pd.read_excel(archivo)
    df["juego"] = juego
    dfs_q.append(df)

if not dfs_q:
    raise RuntimeError("No se encontraron cuestionarios")

df_q = pd.concat(dfs_q, ignore_index=True)
df_q.columns = df_q.columns.str.strip()
df_q = df_q.loc[:, ~df_q.columns.str.endswith("2")]

df_q = df_q.rename(columns={
    "Indique su Código de Participación": "participant",
    "Del 1 (Muy bajo) al 10 (Muy alto): ¿Cuánto esfuerzo mental tuviste que invertir para alcanzar tu nivel de rendimiento en el juego?": "nasa_mental",
    "Del 1 (Muy bajo) al 10 (Muy alto): ¿En qué medida te sentiste frustrado/a durante el juego?": "nasa_frustracion"
})

positivas = ["Alegría", "Felicidad/placer", "Entusiasmo/Excitación", "Satisfacción", "Relax"]
negativas = ["Asco", "Ira/enfado", "Ansiedad", "Miedo", "Frustración", "Tristeza/depresión", "Fatiga/cansancio", "Aburrimiento"]

def map_valor(x):
    if pd.isna(x):
        return pd.NA
    x = str(x).strip().lower()
    mapa = {
        "nada": 1,
        "casi nada": 2,
        "poco": 3,
        "ni mucho ni poco": 4,
        "bastante": 5,
        "mucho": 6,
        "muchísimo": 7
    }
    return mapa.get(x, pd.NA)

for col in positivas + negativas:
    if col in df_q.columns:
        df_q[col] = df_q[col].apply(map_valor)

for col in ["nasa_mental", "nasa_frustracion"]:
    if col in df_q.columns:
        df_q[col] = pd.to_numeric(df_q[col], errors="coerce")

df_q["afecto_positivo"] = df_q[[c for c in positivas if c in df_q.columns]].mean(axis=1)
df_q["afecto_negativo"] = df_q[[c for c in negativas if c in df_q.columns]].mean(axis=1)

for df in [df_feat, df_q]:
    df["participant"] = df["participant"].astype(str).str.strip().str.lower()

mapa_juegos = {
    "sonic": "sonic racing"
}

df_feat["juego_normalizado"] = df_feat["juego"].str.strip().str.lower().map(mapa_juegos).fillna(df_feat["juego"].str.strip().str.lower())
df_q["juego_normalizado"] = df_q["juego"].str.strip().str.lower()

df_final = pd.merge(
    df_feat,
    df_q,
    left_on=["participant", "juego_normalizado"],
    right_on=["participant", "juego_normalizado"],
    how="left"
)

for col in ["afecto_positivo", "afecto_negativo", "nasa_mental", "nasa_frustracion"]:
    if col not in df_final.columns:
        df_final[col] = pd.NA

df_final["balance_emocional"] = df_final["afecto_positivo"] - df_final["afecto_negativo"]

df_final.to_csv("datos_finales.csv", index=False)