import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    layout="wide", 
    page_title="Consola de Análisis Biométrico",
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;700&family=Montserrat:wght@800&display=swap');

    /* Fuente principal para el cuerpo */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1e293b;
    }

    /* Fuente para datos y números (JETBRAINS MONO) */
    [data-testid="stMetricValue"], .stDataFrame, code, .tick text {
        font-family: 'JetBrains Mono', monospace !important;
        letter-spacing: -0.8px;
    }

    /* Fuente para TITULOS (MONTSERRAT) */
    h1, h2, h3 {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #0f172a;
        border-left: 10px solid #1e293b;
        padding-left: 15px;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }

    .main { background-color: #ffffff; }

    /* Tarjetas de métricas */
    .stMetric {
        background-color: #f8fafc;
        padding: 20px;
        border: 1px solid #e2e8f0;
        border-radius: 0px;
    }

    [data-testid="stMetricLabel"] {
        text-transform: uppercase;
        font-weight: 700;
        font-size: 0.7rem;
        color: #64748b;
    }

    /* Barra lateral */
    [data-testid="stSidebar"] {
        background-color: #f1f5f9;
        border-right: 2px solid #1e293b;
    }
    
    /* Selectores */
    .stSelectbox label, .stMultiSelect label {
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.75rem;
    }
    </style>
    """, unsafe_allow_html=True)

def cargar_datos():
    try:
        df = pd.read_csv("datos_finales_procesados.csv")
        return df
    except:
        st.error("ERROR DE SISTEMA: No se encontró la fuente de datos.")
        return None

def main():
    # --- CABECERA ---
    st.markdown("# ANÁLISIS DE FATIGA MENTAL BASADO EN NASA TLX Y MÉTRICAS OCULARES")
    st.write("")

    df = cargar_datos()
    if df is not None:
        # --- PANEL DE CONTROL ---
        with st.sidebar:
            st.markdown("### CONTROL DE SESIÓN")
            juegos = sorted(df["juego_norm"].unique())
            juego_sel = st.selectbox("SELECCIONAR JUEGO", juegos)

            todos_parts = sorted(df[df["juego_norm"] == juego_sel]["participant"].unique())
            part_sel = st.multiselect("COMPARATIVA DE SUJETOS", todos_parts, default=todos_parts[:1])
            
            if st.checkbox("SELECCIONAR TODOS LOS SUJETOS"):
                part_sel = todos_parts

            st.divider()
            st.markdown(f"**SESIÓN:** {juego_sel.upper()}")
            st.markdown(f"**MUESTRA:** {len(part_sel)} SUJETOS")

        # Filtrado de datos
        df_p = df[(df["juego_norm"] == juego_sel) & (df["participant"].isin(part_sel))]
        
        if df_p.empty:
            st.warning("CONSULTA NULA: No se han encontrado registros.")
            return

        # --- SECCIÓN 1: INDICADORES CLAVE ---
        m1, m2, m3, m4 = st.columns(4)
        
        val_carga = df_p["nasa_carga_total"].mean()
        val_pupila = df_p["pupil_mean"].mean()
        val_balance = df_p["balance_emocional"].mean()
        val_movimiento = df_p["movimiento_mean"].mean()

        m1.metric("ÍNDICE DE CARGA MENTAL", f"{val_carga:.2f}")
        m2.metric("DIÁMETRO PUPILAR (MM)", f"{val_pupila:.2f}")
        m3.metric("BALANCE EMOCIONAL", f"{val_balance:.2f}")
        m4.metric("INTENSIDAD MOVIMIENTO", f"{val_movimiento:.2f}")

        st.write("")

        # --- SECCIÓN 2: PERFILES Y DISTRIBUCIÓN ---
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("PERFIL DE CARGA SUBJETIVA")
            dims = ["Mental", "Física", "Temporal", "Esfuerzo", "Frustración", "Rendimiento (invertido)"]
            
            fig_radar = go.Figure()

            for p in part_sel:
                d_part = df_p[df_p["participant"] == p]
                if not d_part.empty:
                    valores = [d_part["nasa_mental"].iloc[0], d_part["nasa_fisica"].iloc[0], 
                               d_part["nasa_temporal"].iloc[0], d_part["nasa_esfuerzo"].iloc[0], 
                               d_part["nasa_frustracion"].iloc[0], d_part["nasa_rendimiento_inv"].iloc[0]]
                    
                    fig_radar.add_trace(go.Scatterpolar(
                        r=valores,
                        theta=dims,
                        fill='toself',
                        name=f"SUJETO: {p}"
                    ))

            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 10], gridcolor="#cbd5e1", tickfont={"family": "JetBrains Mono"}),
                    angularaxis=dict(gridcolor="#cbd5e1")
                ),
                font=dict(family="Inter", size=12),
                showlegend=True,
                legend=dict(orientation="h", y=-0.2),
                margin=dict(l=40, r=40, t=40, b=40)
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        with col_right:
            st.subheader("POLARIDAD DEL AFECTO")
            
            afectos = df_p.groupby("participant")[["afecto_positivo", "afecto_negativo"]].mean().reset_index()
            df_emo = afectos.melt(id_vars="participant", var_name="Tipo", value_name="Puntaje")
            
            # Traducción de etiquetas en el gráfico
            df_emo["Tipo"] = df_emo["Tipo"].replace({"afecto_positivo": "Afecto Positivo", "afecto_negativo": "Afecto Negativo"})

            fig_bar = px.bar(df_emo, 
                             x="participant", 
                             y="Puntaje", 
                             color="Tipo", 
                             barmode="group",
                             color_discrete_map={
                                 "Afecto Positivo": "#059669", 
                                 "Afecto Negativo": "#b91c1c"
                             })
            
            fig_bar.update_layout(
                font=dict(family="Inter"),
                xaxis_title="IDENTIFICADOR SUJETO",
                yaxis_title="PUNTUACIÓN",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(title="", orientation="h", y=-0.2),
                yaxis=dict(gridcolor="#f1f5f9", tickfont=dict(family="JetBrains Mono"))
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # --- SECCIÓN 3: CORRELACIONES ---
        st.subheader("CORRELACIÓN BIOMÉTRICA GRUPAL")
        fig_scatter = px.scatter(df_p, x="pupil_mean", y="movimiento_mean", 
                                 color="participant",
                                 size="nasa_carga_total",
                                 labels={"pupil_mean": "MEDIA PUPILAR", "movimiento_mean": "INTENSIDAD MOV.", "participant": "SUJETO"},
                                 template="plotly_white")
        
        fig_scatter.update_layout(
            font=dict(family="Inter"),
            xaxis=dict(tickfont=dict(family="JetBrains Mono")),
            yaxis=dict(tickfont=dict(family="JetBrains Mono"))
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # --- INSPECTOR ---
        with st.expander("INSPECTOR DE DATOS BRUTOS"):
            st.dataframe(df_p.style.format(precision=3), use_container_width=True)

if __name__ == "__main__":
    main()