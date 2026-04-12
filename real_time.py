import streamlit as st
import pandas as pd
import json
import websocket
import threading
from collections import deque
import time
import logging

# 1. Sistema de Logs Exhaustivo
logging.basicConfig(
    level=logging.DEBUG, # Captura absolutamente todo (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s"
)
logger = logging.getLogger(__name__)

# CONFIGURACION DEL BUFFER (500 frames = 10 segundos a 50Hz)
MAX_FRAMES = 500 

@st.cache_resource
def get_shared_state():
    logger.info("Inicializando o recuperando estado compartido en memoria (shared_state).")
    return {
        "gaze_buffer": deque(maxlen=MAX_FRAMES),
        "ws_app": None
    }

shared_state = get_shared_state()

if "streaming" not in st.session_state:
    st.session_state.streaming = False
    logger.debug("Variable de sesion 'streaming' inicializada a False.")

def on_message(ws, message):
    try:
        data = json.loads(message)
        
        # Filtramos solo los paquetes que traen datos
        if "gaze2d" in data:
            left_pupil = data.get("left_eye", {}).get("pupil", {}).get("diameter")
            right_pupil = data.get("right_eye", {}).get("pupil", {}).get("diameter")
            
            pupils = [p for p in [left_pupil, right_pupil] if p is not None and p > 0]
            p_mean = sum(pupils) / len(pupils) if pupils else 0
            
            payload = {
                "timestamp": data.get("timestamp", time.time()),
                "pupil_mean": p_mean,
                "gaze_x": data["gaze2d"][0],
                "gaze_y": data["gaze2d"][1]
            }
            shared_state["gaze_buffer"].append(payload)
        else:
            # Descomentar la siguiente linea si quieres ver en consola los paquetes de estado/control
            # logger.debug("Paquete JSON recibido sin datos de gaze2d. Ignorando.")
            pass
            
    except json.JSONDecodeError as e:
        logger.error(f"Error de formato JSON al decodificar paquete: {e}")
    except Exception as e:
        logger.error(f"Error inesperado procesando paquete de datos: {e}", exc_info=True)

def on_error(ws, error):
    logger.error(f"Error capturado en la conexion WebSocket: {error}", exc_info=True)

def on_close(ws, close_status_code, close_msg):
    logger.info(f"Conexion WebSocket cerrada. Codigo de estado: {close_status_code}, Mensaje: {close_msg}")
    st.session_state.streaming = False

def on_open(ws):
    logger.info("Conexion WebSocket establecida exitosamente con el subprotocolo g3api.")

def start_socket_thread(ip_gafas):
    url = f"ws://{ip_gafas}/websocket"
    logger.info(f"Iniciando hilo de conexion WebSocket hacia: {url}")
    
    try:
        shared_state["ws_app"] = websocket.WebSocketApp(
            url,
            subprotocols=["g3api"], # REQUISITO ESTRICTO DE TOBII G3
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        logger.info("Llamando a run_forever con configuracion de pings (interval=10s, timeout=5s).")
        # El ping interval mantiene viva la conexion con el servidor interno de las gafas
        shared_state["ws_app"].run_forever(ping_interval=10, ping_timeout=5)
        logger.info("El bucle run_forever ha finalizado limpiamente.")
        
    except Exception as e:
        logger.critical(f"Fallo critico al intentar arrancar la conexion WebSocket: {e}", exc_info=True)
        st.session_state.streaming = False

def vista_tiempo_real():
    st.title("Monitor de Fatiga en Vivo")
    
    ip_gafas = st.text_input("IP de las Tobii Glasses 3", "localhost:8080")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Iniciar Streaming", type="primary", disabled=st.session_state.streaming):
            logger.info("El usuario solicito iniciar el streaming.")
            st.session_state.streaming = True
            shared_state["gaze_buffer"].clear()
            
            logger.debug("Lanzando thread en segundo plano para el WebSocket.")
            t = threading.Thread(target=start_socket_thread, args=(ip_gafas,), daemon=True)
            t.start()
            st.rerun() 

    with col2:
        if st.button("Detener", disabled=not st.session_state.streaming):
            logger.info("El usuario solicito detener el streaming.")
            if shared_state["ws_app"]:
                logger.debug("Cerrando aplicacion WebSocket de forma segura.")
                shared_state["ws_app"].close()
            st.session_state.streaming = False
            st.rerun()

    st.markdown("---")
    
    metric_placeholder = st.empty()
    chart_placeholder = st.empty()

    # Bucle de dibujo
    while st.session_state.streaming:
        try:
            buffer_list = list(shared_state["gaze_buffer"])
            
            if buffer_list:
                df_render = pd.DataFrame(buffer_list)
                ultimo = df_render.iloc[-1]
                
                with metric_placeholder.container():
                    c_pupil, c_gaze = st.columns(2)
                    
                    if ultimo['pupil_mean'] == 0:
                        c_pupil.metric("Pupila (Media)", "PARPADEO", delta="- Perdida de senal", delta_color="inverse")
                    else:
                        c_pupil.metric("Pupila (Media)", f"{ultimo['pupil_mean']:.2f} mm")
                        
                    c_gaze.metric("Coordenadas Gaze", f"X: {ultimo['gaze_x']:.2f} | Y: {ultimo['gaze_y']:.2f}")
                
                # Renderizado grafico
                df_chart = df_render[df_render['pupil_mean'] > 0].copy()
                if not df_chart.empty:
                    primer_tiempo = df_chart['timestamp'].iloc[0]
                    df_chart['Segundos'] = df_chart['timestamp'] - primer_tiempo
                    
                    chart_placeholder.line_chart(
                        data=df_chart, 
                        x="Segundos", 
                        y="pupil_mean", 
                        use_container_width=True
                    )
        except Exception as e:
            logger.error(f"Error en el bucle de renderizado de la interfaz visual: {e}", exc_info=True)
            
        time.sleep(0.1) 

def main():
    st.set_page_config(layout="wide", page_title="Fatigue Analyzer")
    logger.info("Iniciando aplicacion Streamlit de analisis Tobii.")
    vista_tiempo_real()

if __name__ == "__main__":
    main()