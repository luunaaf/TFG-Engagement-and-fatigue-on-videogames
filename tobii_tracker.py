import subprocess
import json
import socket
import time
import threading
import queue
import numpy as np
from scipy.stats import entropy
from collections import deque

# --- 1. CONFIGURACIÓN ---
NODE_IP = "127.0.0.1"
NODE_PORT = 5005
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
RTSP_URL = "rtsp://192.168.75.51:8554/live/all"

FPS_GAFAS = 50
VENTANA_SEGUNDOS = 60
MAX_FRAMES = FPS_GAFAS * VENTANA_SEGUNDOS
CAMPO_VISUAL_GRADOS = 60.0 

frame_queue = queue.Queue()

# --- 2. CEREBRO MATEMÁTICO (VENTANA DESLIZANTE) ---
class FatigueCalculator:
    def __init__(self):
        self.historial = deque(maxlen=MAX_FRAMES)
        self.pupil_baseline = None 
        self.ultimo_calculo = time.time()
        self.ultimo_estado_alerta = "" # Para no repetir notificaciones idénticas

    def add_data(self, data):
        self.historial.append(data)
        ahora = time.time()
        
        if len(self.historial) >= (MAX_FRAMES * 0.5) and (ahora - self.ultimo_calculo) >= 1.0:
            self.calcular()
            self.ultimo_calculo = ahora

    def calcular(self):
        try:
            datos = list(self.historial)
            n_datos = len(datos)
            dt = 1.0 / FPS_GAFAS
            
            pupils = np.array([d["pupil"] for d in datos if not d["blink"] and d["pupil"] > 0])
            blinks_array = np.array([d["blink"] for d in datos])
            coords = np.array([[d["x"], d["y"]] for d in datos if not d["blink"]])

            # 1 & 5. PDR y PDV
            pdr_norm, pdv_norm, pdr_crudo, pdv_crudo = 0.0, 0.0, 0.0, 0.0
            if len(pupils) > 0:
                if self.pupil_baseline is None: 
                    self.pupil_baseline = np.mean(pupils) 
                
                p_mean = np.mean(pupils)
                pdv_crudo = np.std(pupils)
                pdr_crudo = max(self.pupil_baseline - p_mean, 0)
                
                pdr_norm = np.clip(pdr_crudo / 0.5, 0, 1)
                pdv_norm = np.clip(pdv_crudo / 0.20, 0, 1)

            # 3, 4 & 8. BR, BD, PERCLOS
            cambios = np.diff(blinks_array.astype(int))
            inicios_blink = np.where(cambios == 1)[0]
            fines_blink = np.where(cambios == -1)[0]
            
            if len(inicios_blink) > len(fines_blink):
                fines_blink = np.append(fines_blink, n_datos - 1)
            elif len(fines_blink) > len(inicios_blink):
                inicios_blink = np.insert(inicios_blink, 0, 0)

            duraciones_blink = (fines_blink - inicios_blink) * dt
            
            br_crudo = len(inicios_blink) * (60.0 / (n_datos * dt)) 
            br_norm = 0.0 if 12 <= br_crudo <= 20 else np.clip(abs(br_crudo - 16) / 10, 0, 1) 
                
            bd_crudo = np.mean(duraciones_blink) if len(duraciones_blink) > 0 else 0
            bd_norm = np.clip((bd_crudo - 0.15) / (0.35 - 0.15), 0, 1) if bd_crudo >= 0.15 else 0.0
            
            perclos_crudo = np.sum(blinks_array) / n_datos
            perclos_norm = np.clip(perclos_crudo / 0.20, 0, 1)

            # 2, 6 & 7. FD, GE, SV
            fd_norm = ge_norm = sv_norm = fd_crudo = ge_crudo = sv_crudo = 0.0
            
            if len(coords) > 1:
                distancias = np.linalg.norm(np.diff(coords, axis=0), axis=1) * CAMPO_VISUAL_GRADOS
                velocidades = distancias / dt
                
                saccade_mask = velocidades > 30
                saccade_vels = velocidades[saccade_mask]
                if len(saccade_vels) > 0:
                    sv_crudo = np.mean(saccade_vels)
                    sv_norm = np.clip((70 - sv_crudo) / 40, 0, 1) if sv_crudo < 70 else 0.0
                
                tiempo_fix = np.sum(~saccade_mask) * dt
                num_fixaciones = max(1, np.sum(np.diff(saccade_mask.astype(int)) == -1))
                fd_crudo = tiempo_fix / num_fixaciones
                fd_norm = np.clip((fd_crudo - 0.2) / (0.5 - 0.2), 0, 1) if fd_crudo >= 0.2 else 0.0
                
                hist, _, _ = np.histogram2d(coords[:,0], coords[:,1], bins=10, range=[[0,1],[0,1]])
                probabilidades = hist.flatten() / np.sum(hist)
                probabilidades = probabilidades[probabilidades > 0]
                if len(probabilidades) > 0:
                    ge_crudo = entropy(probabilidades, base=2)
                    ge_norm = np.clip((3.0 - ge_crudo) / 3.0, 0, 1) 

            # --- FÓRMULA MAESTRA DE FATIGA ---
            fi = (pdr_norm + fd_norm + br_norm + bd_norm + pdv_norm + ge_norm + sv_norm + perclos_norm) / 8.0

            # --- LÓGICA DE NOTIFICACIÓN ---
            estado_actual = "Normal"
            alerta_msg = "Estado normal o sin signos de fatiga"
            nivel_alerta = "info"

            if fi >= 0.50:
                estado_actual = "Alta"
                alerta_msg = "¡ALERTA! Fatiga alta o deterioro oculomotor significativo"
                nivel_alerta = "critical"
            elif 0.20 <= fi < 0.50:
                estado_actual = "Moderada"
                alerta_msg = "Fatiga moderada o funcional detectada"
                nivel_alerta = "warning"

            # Enviar actualización de fatiga
            payload = {
                "type": "fatigue_update",
                "fatigue_index": float(fi),
                "status": estado_actual,
                "metrics": {
                    "PERCLOS": {"raw": float(perclos_crudo), "norm": float(perclos_norm), "unit": "%"},
                    "BR": {"raw": float(br_crudo), "norm": float(br_norm), "unit": " /min"},
                    "BD": {"raw": float(bd_crudo), "norm": float(bd_norm), "unit": " s"},
                    "PDR": {"raw": float(pdr_crudo), "norm": float(pdr_norm), "unit": " mm"},
                    "PDV": {"raw": float(pdv_crudo), "norm": float(pdv_norm), "unit": " mm"},
                    "SV": {"raw": float(sv_crudo), "norm": float(sv_norm), "unit": " deg/s"},
                    "FD": {"raw": float(fd_crudo), "norm": float(fd_norm), "unit": " s"},
                    "GE": {"raw": float(ge_crudo), "norm": float(ge_norm), "unit": " bits"}
                }
            }
            udp_sock.sendto(json.dumps(payload).encode('utf-8'), (NODE_IP, NODE_PORT))

            # Enviar NOTIFICACIÓN solo si cambia el estado para evitar spam
            if estado_actual != self.ultimo_estado_alerta:
                notification = {
                    "type": "notification",
                    "level": nivel_alerta,
                    "message": alerta_msg,
                    "value": round(float(fi), 3)
                }
                udp_sock.sendto(json.dumps(notification).encode('utf-8'), (NODE_IP, NODE_PORT))
                self.ultimo_estado_alerta = estado_actual

        except Exception as e:
            print(f"⚠️ Error interno calculando fatiga: {e}")

# --- 3. EXTRACCIÓN FFmpeg ---
def ffmpeg_reader():
    command = [
        "ffmpeg", "-rtsp_transport", "tcp", "-i", RTSP_URL,
        "-map", "0:3", "-c", "copy", "-f", "data", "-"
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    buffer_texto = ""
    
    while True:
        chunk = process.stdout.read(256)
        if not chunk: break
        
        texto = "".join([chr(b) for b in chunk if 32 <= b <= 126])
        buffer_texto += texto
        
        while "{" in buffer_texto and "}" in buffer_texto:
            start_idx = buffer_texto.find("{")
            depth, end_idx = 0, -1
            
            for i in range(start_idx, len(buffer_texto)):
                if buffer_texto[i] == '{': depth += 1
                elif buffer_texto[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end_idx = i; break
            
            if end_idx != -1:
                json_str = buffer_texto[start_idx:end_idx+1]
                buffer_texto = buffer_texto[end_idx+1:] 
                
                try:
                    data = json.loads(json_str)
                    x, y = -1.0, -1.0
                    if "gaze2d" in data and isinstance(data["gaze2d"], list) and len(data["gaze2d"]) >= 2:
                        x, y = float(data["gaze2d"][0]), float(data["gaze2d"][1])
                        
                    pr = data.get("eyeright", {}).get("pupildiameter", 0) if isinstance(data.get("eyeright"), dict) else 0
                    pl = data.get("eyeleft", {}).get("pupildiameter", 0) if isinstance(data.get("eyeleft"), dict) else 0
                    
                    pupil = float(pr) if pr is not None and float(pr) > 0 else float(pl if pl is not None else 0)
                    blink = True if (x < 0 or y < 0 or pupil <= 0) else False
                    frame_queue.put({"x": x, "y": y, "pupil": pupil, "blink": blink})
                except Exception:
                    pass 
            else:
                break

# --- 4. BUCLE MAESTRO ---
print("📡 Arrancando Lector RTSP...")
reader_thread = threading.Thread(target=ffmpeg_reader, daemon=True)
reader_thread.start()

calculadora = FatigueCalculator()
print("🚀 Reloj Maestro a 50Hz iniciado.")

try:
    while True:
        try:
            frame = frame_queue.get(timeout=0.120)
        except queue.Empty:
            frame = {"x": -1.0, "y": -1.0, "pupil": 0.0, "blink": True}
        
        gaze_payload = {
            "type": "gaze", 
            "x": round(frame["x"], 4), 
            "y": round(frame["y"], 4), 
            "pupil": round(frame["pupil"], 4), 
            "blink": frame["blink"]
        }
        udp_sock.sendto(json.dumps(gaze_payload).encode('utf-8'), (NODE_IP, NODE_PORT))
        
        calculadora.add_data(frame)

except KeyboardInterrupt:
    print("\n🛑 Tracker detenido.")
    udp_sock.close()
