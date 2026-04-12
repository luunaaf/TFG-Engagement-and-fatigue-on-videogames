import asyncio
import websockets
import json
import time
import random
import math

async def enviar_datos_simulados(websocket):
    print(f"🟢 ¡Cliente conectado desde {websocket.remote_address}!")
    start_time = time.time()
    
    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # 1. Simular diámetro de la pupila (entre 2.5 y 4.5 mm)
            # Usamos una onda senoidal lenta para simular cambios de luz/carga cognitiva
            base_pupil = 3.5 + math.sin(elapsed * 0.2) * 0.5 + random.uniform(-0.1, 0.1)
            
            # 2. Simular parpadeos (Blinks)
            # Damos un 2% de probabilidad en cada frame de que el usuario parpadee
            if random.random() < 0.02:
                # Durante un parpadeo, la cámara pierde la pupila (envía 0 o None)
                left_p, right_p = 0.0, 0.0
            else:
                # Si no parpadea, enviamos el diámetro normal con una ligerísima asimetría
                left_p = max(0, base_pupil + random.uniform(-0.05, 0.05))
                right_p = max(0, base_pupil + random.uniform(-0.05, 0.05))

            # 3. Simular la mirada (Gaze 2D) vagando por la pantalla (valores de 0.0 a 1.0)
            gaze_x = 0.5 + math.sin(elapsed * 0.5) * 0.3 + random.uniform(-0.02, 0.02)
            gaze_y = 0.5 + math.cos(elapsed * 0.3) * 0.3 + random.uniform(-0.02, 0.02)

            # Construir el JSON exactamente como lo escupen las G3
            payload = {
                "timestamp": current_time,
                "gaze2d": [gaze_x, gaze_y],
                "left_eye": {
                    "pupil": {"diameter": left_p}
                },
                "right_eye": {
                    "pupil": {"diameter": right_p}
                }
            }
            
            # Enviar el paquete y esperar 20ms (simulando 50 Hz)
            await websocket.send(json.dumps(payload))
            await asyncio.sleep(0.02) 
            
    except websockets.ConnectionClosed:
        print("🔴 Cliente desconectado. Esperando nueva conexión...")

async def main():
    # Levantamos el servidor aceptando el protocolo g3api
    async with websockets.serve(enviar_datos_simulados, "localhost", 8080, subprotocols=["g3api"]):
        print("Simulador de Tobii Glasses 3 INICIADO.")
        print("Escuchando en: ws://localhost:8080")
        print("Esperando a que conectes tu interfaz Streamlit...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())