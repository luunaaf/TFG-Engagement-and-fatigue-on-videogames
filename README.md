
# TFG - Tobii Glasses Fatigue & Engagement Detection

This repository contains two main modules: an **Historical Data Analysis** tool and a **Real-Time Tobii Pro Glasses 3 Tracking System**.

---

## Prerequisites & Installation

### 1. System Requirements
* **Python 3.10+** installed.
* **Node.js (v18+)** installed.
* **FFmpeg**: Ensure `ffmpeg` is installed and added to your system's PATH variables (or place `ffmpeg.exe` directly into this project directory).

### 2. Dependencies Installation

Open your terminal in the project root folder and run:

```bash
pip install numpy opencv-python pandas matplotlib jupyter

npm init -y
npm install express socket.io

```

---

## Execution Guide

### Scenario 1: Real-Time Monitoring System (Live Demo)

To launch the real-time pipeline, open **two separate terminal tabs** and execute these steps in the exact following order:

1. **Start the Middleware Server (Node.js)**
```bash
node server.js

```


2. **Open the Dashboard (Web Browser)**
Navigate to: `http://localhost:3000`
3. **Launch the Mathematical Processing Core (Python)**
```bash
python tobii_tracker.py

```


---

### Scenario 2: Historical Data Analysis (Offline)

To process the pre-existing dataset and generate statistical NASA-TLX correlation metrics:

1. **Clean and Normalize Data**
```bash
python procesar_datos.py

```


2. **Launch the Analytical Interface**
```bash
streamlit run app.py

```