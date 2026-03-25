import streamlit as st
import pandas as pd
import json
import websocket
import threading
from queue import Queue, Empty
import time
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

if "data_queue" not in st.session_state:
    st.session_state.data_queue = Queue()
    st.session_state.live_data = pd.DataFrame(columns=["timestamp", "pupil_mean", "gaze_x", "gaze_y"])
    st.session_state.streaming = False
    logger.info("Estado de sesión inicializado")

def socket_worker(url, data_queue):
    logger.info(f"Intentando conectar al WebSocket: {url}")
    try:
        ws = websocket.create_connection(url, timeout=7)
        logger.info("Conexión WebSocket establecida con éxito")
        
        while st.session_state.streaming:
            try:
                message = ws.recv()
                if not message:
                    logger.warning("Mensaje vacío recibido")
                    continue
                
                data = json.loads(message)
                
                if "gaze2d" in data:
                    p_left = data.get("left_eye", {}).get("pupil", {}).get("diameter")
                    p_right = data.get("right_eye", {}).get("pupil", {}).get("diameter")
                    
                    pupils = [p for p in [p_left, p_right] if p is not None and p > 0]
                    p_mean = sum(pupils) / len(pupils) if pupils else 0
                    
                    payload = {
                        "timestamp": data.get("timestamp", time.time()),
                        "pupil_mean": p_mean,
                        "gaze_x": data["gaze2d"][0],
                        "gaze_y": data["gaze2d"][1]
                    }
                    data_queue.put(payload)
                else:
                    logger.debug(f"JSON recibido sin datos de gaze: {list(data.keys())}")
            
            except json.JSONDecodeError as je:
                logger.error(f"Error al decodificar JSON: {je}")
            except websocket.WebSocketConnectionClosedException:
                logger.error("La conexión WebSocket se cerró inesperadamente")
                break
            except Exception as e:
                logger.error(f"Error durante la recepción de datos: {type(e).__name__} - {e}")
                break
        
        ws.close()
        logger.info("Socket cerrado correctamente")
    except Exception as e:
        logger.critical(f"Fallo crítico al intentar conectar: {e}")
        st.session_state.streaming = False

def vista_tiempo_real():
    st.header("Conexión en Vivo - Tobii SDK")
    ip_gafas = st.text_input("IP de las Tobii Glasses 3", "192.168.71.50")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Conectar y Stream"):
            if not st.session_state.streaming:
                logger.info(f"Iniciando hilo de streaming para IP: {ip_gafas}")
                st.session_state.streaming = True
                url = f"ws://{ip_gafas}/live/data"
                t = threading.Thread(
                    target=socket_worker, 
                    args=(url, st.session_state.data_queue), 
                    daemon=True
                )
                t.start()
            else:
                logger.warning("El streaming ya estaba activo")
    
    with c2:
        if st.button("Desconectar"):
            logger.info("Deteniendo streaming por usuario")
            st.session_state.streaming = False

    monitor = st.empty()
    
    while st.session_state.streaming:
        new_rows = []
        count = 0
        while not st.session_state.data_queue.empty():
            try:
                new_rows.append(st.session_state.data_queue.get_nowait())
                count += 1
            except Empty:
                break
        
        if new_rows:
            df_new = pd.DataFrame(new_rows)
            st.session_state.live_data = pd.concat([st.session_state.live_data, df_new], ignore_index=True).tail(100)
            logger.debug(f"Procesados {count} paquetes nuevos")
        
        with monitor.container():
            if not st.session_state.live_data.empty:
                ultimo = st.session_state.live_data.iloc[-1]
                st.metric("Pupila (Media)", f"{ultimo['pupil_mean']:.2f} mm")
                st.line_chart(st.session_state.live_data.set_index("timestamp")["pupil_mean"])
                st.write(f"Gaze X: {ultimo['gaze_x']:.3f} | Gaze Y: {ultimo['gaze_y']:.3f}")
            else:
                st.info("Esperando datos del WebSocket...")
        
        time.sleep(0.05)

def vista_historica():
    st.header("Análisis de Datos Históricos")
    try:
        logger.info("Cargando datos_finales.csv")
        df = pd.read_csv("datos_finales.csv")
        juego = st.selectbox("Juego", df["juego_normalizado"].unique())
        participante = st.selectbox("Participante", df[df["juego_normalizado"] == juego]["participant"].unique())
        df_p = df[(df["juego_normalizado"] == juego) & (df["participant"] == participante)]
        st.bar_chart(df_p[["pupil_mean", "movimiento_mean"]])
    except FileNotFoundError:
        logger.error("Archivo datos_finales.csv no encontrado")
        st.error("No se encontró el archivo de datos procesados.")
    except Exception as e:
        logger.error(f"Error en vista histórica: {e}")
        st.error(f"Error inesperado: {e}")

def main():
    st.set_page_config(layout="wide", page_title="Tobii G3 Analyzer")
    opcion = st.sidebar.radio("Navegación", ["Histórico", "Tiempo Real"])
    logger.info(f"Navegando a: {opcion}")
    
    if opcion == "Histórico":
        vista_historica()
    else:
        vista_tiempo_real()

if __name__ == "__main__":
    main()