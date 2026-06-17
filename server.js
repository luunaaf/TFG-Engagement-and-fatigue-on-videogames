const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const dgram = require("dgram");

const app = express();

const server = http.createServer(app);

const io = new Server(server, {
  cors: { origin: "*" }
});

app.use(express.static("public"));

/* -------------------------------------------------- */
/* UDP SERVER (RECIBE PYTHON) */
/* -------------------------------------------------- */

const udpServer = dgram.createSocket("udp4");

udpServer.on("message", (msg) => {

  try {

    const data = JSON.parse(msg.toString());

    /* ============================================== */
    /* TELEMETRÍA GAZE */
    /* ============================================== */

    if (data.type === "gaze") {

      io.emit("gaze", data);
    }

    /* ============================================== */
    /* MOTOR DE FATIGA */
    /* ============================================== */

    else if (data.type === "fatigue_update") {

      const fi = data.fatigue_index;

      /* -------------------------------------------- */
      /* GENERAR ALERTAS AUTOMÁTICAS */
      /* -------------------------------------------- */

      let alert = {

        active: false,

        level: null,

        title: "",

        message: ""
      };

      // ============================================
      // NORMAL
      // ============================================

      if (fi < 0.20) {

        alert = {

          active: false,

          level: "normal",

          title: "Estado Normal",

          message:
            "No se detectan signos relevantes de fatiga."
        };
      }

      // ============================================
      // WARNING / MODERADA
      // ============================================

      else if (fi >= 0.20 && fi < 0.50) {

        alert = {

          active: true,

          level: "moderada",

          title: "⚠️ WARNING",

          message:
            "Fatiga moderada detectada. Posible reducción de atención y rendimiento visual."
        };

        console.log(
          `⚠️ WARNING -> FI=${fi.toFixed(3)}`
        );
      }

      // ============================================
      // ALERTA CRÍTICA
      // ============================================

      else if (fi >= 0.50) {

        alert = {

          active: true,

          level: "alta",

          title: "🚨 ALERTA CRÍTICA",

          message:
            "Fatiga severa detectada. Deterioro oculomotor significativo."
        };

        console.log(
          `🚨 ALERTA CRÍTICA -> FI=${fi.toFixed(3)}`
        );
      }

      /* -------------------------------------------- */
      /* AÑADIR ALERTA AL PAYLOAD */
      /* -------------------------------------------- */

      data.alert = alert;

      /* -------------------------------------------- */
      /* ENVIAR AL FRONTEND */
      /* -------------------------------------------- */

      io.emit("fatigue", data);
    }

  } catch (err) {

    console.log(
      "❌ Error procesando UDP:",
      err.message
    );
  }
});

udpServer.on("error", (err) => {

  console.log(
    `❌ Error UDP: ${err.stack}`
  );
});

udpServer.bind(5005, () => {

  console.log(
    "📡 Escuchando Python UDP en puerto 5005"
  );
});

/* -------------------------------------------------- */
/* WEB SERVER */
/* -------------------------------------------------- */

server.listen(3000, () => {

  console.log("🚀 Dashboard listo:");

  console.log("http://localhost:3000");
});