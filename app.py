import streamlit as st
import pandas as pd
import json
import websocket
import threading
from queue import Queue, Empty
import time

if "data_queue" not in st.session_state:
    st.session_state.data_queue = Queue()
    st.session_state.live_data = pd.DataFrame(columns=["timestamp", "pupil_mean", "gaze_x", "gaze_y"])
    st.session_state.streaming = False

def socket_worker(url, data_queue):
    try:
        ws = websocket.create_connection(url, timeout=5)
        while st.session_state.streaming:
            try:
                message = ws.recv()
                data = json.loads(message)
                
                if "gaze2d" in data or "left_eye" in data:
                    p_left = data.get("left_eye", {}).get("pupil", {}).get("diameter", 0)
                    p_right = data.get("right_eye", {}).get("pupil", {}).get("diameter", 0)
                    gaze = data.get("gaze2d", [0, 0])
                    
                    payload = {
                        "timestamp": data.get("timestamp", time.time()),
                        "pupil_mean": (p_left + p_right) / 2 if (p_left and p_right) else (p_left or p_right),
                        "gaze_x": gaze[0],
                        "gaze_y": gaze[1]
                    }
                    data_queue.put(payload)
            except:
                break
        ws.close()
    except:
        pass

def vista_tiempo_real():
    st.header("Conexión en Vivo - Tobii SDK")
    ip_gafas = st.text_input("IP de las Tobii Glasses 3", "192.168.71.50")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Conectar y Stream"):
            if not st.session_state.streaming:
                st.session_state.streaming = True
                url = f"ws://{ip_gafas}/live/data"
                t = threading.Thread(
                    target=socket_worker, 
                    args=(url, st.session_state.data_queue), 
                    daemon=True
                )
                t.start()
            else:
                st.info("Streaming activo.")
                
    with c2:
        if st.button("Desconectar"):
            st.session_state.streaming = False

    monitor = st.empty()
    
    while st.session_state.streaming:
        new_rows = []
        while not st.session_state.data_queue.empty():
            try:
                new_rows.append(st.session_state.data_queue.get_nowait())
            except Empty:
                break
        
        if new_rows:
            df_new = pd.DataFrame(new_rows)
            st.session_state.live_data = pd.concat([st.session_state.live_data, df_new], ignore_index=True).tail(100)
        
        with monitor.container():
            if not st.session_state.live_data.empty:
                ultimo = st.session_state.live_data.iloc[-1]
                st.metric("Pupila (Media)", f"{ultimo['pupil_mean']:.2f} mm")
                st.line_chart(st.session_state.live_data.set_index("timestamp")["pupil_mean"])
                st.write(f"Gaze X: {ultimo['gaze_x']:.3f} | Gaze Y: {ultimo['gaze_y']:.3f}")
        
        time.sleep(0.1)

def vista_historica():
    st.header("Análisis de Datos Históricos (CSV)")
    try:
        df = pd.read_csv("datos_finales.csv")
        juego = st.selectbox("Juego", df["juego_normalizado"].unique())
        participante = st.selectbox("Participante", df[df["juego_normalizado"] == juego]["participant"].unique())
        df_p = df[(df["juego_normalizado"] == juego) & (df["participant"] == participante)]
        st.bar_chart(df_p[["pupil_mean", "movimiento_mean"]])
    except:
        st.error("Archivo no encontrado.")

def main():
    st.set_page_config(layout="wide", page_title="Tobii G3 Analyzer")
    opcion = st.sidebar.radio("Navegación", ["Histórico", "Tiempo Real"])
    if opcion == "Histórico":
        vista_historica()
    else:
        vista_tiempo_real()

if __name__ == "__main__":
    main()