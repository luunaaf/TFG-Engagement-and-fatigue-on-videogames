import streamlit as st
import pandas as pd

df = pd.read_csv("datos_finales.csv")

st.title("Estados de Ánimo y Métricas Visuales")

juego = st.selectbox("Juego", df["juego_normalizado"].unique())
df_j = df[df["juego_normalizado"] == juego]

participant = st.selectbox("Participante", df_j["participant"].unique())
df_p = df_j[df_j["participant"] == participant]

st.subheader("Métricas visuales")
st.bar_chart(df_p[
    ["pupil_mean", "movimiento_mean", "gaze_x_var", "gaze_y_var"]
])

st.subheader("Estados emocionales")
st.bar_chart(df_p[
    ["afecto_positivo", "afecto_negativo", "nasa_mental", "nasa_frustracion"]
])
