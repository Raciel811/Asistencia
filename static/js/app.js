/**
 * app.js
 * ───────────────────────────────────────────────────────────────────────
 * Lógica del cliente: reloj en vivo, geolocalización del navegador (PC),
 * captura de foto vía webcam con cuenta regresiva de 3 segundos, y
 * comunicación con la API REST (/api/asistencia/*).
 */

(() => {
  "use strict";

  // ── Estado global ──────────────────────────────────────────────────
  const state = {
    latitud: null,
    longitud: null,
    direccion: "Ubicación no disponible",
    mediaStream: null,
    tipoSeleccionado: null,
    countdownTimer: null,
    secondsLeft: 3,
    capturing: false,
  };

  const COUNTDOWN_SECONDS = 3;
  const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

  // ── Referencias DOM ────────────────────────────────────────────────
  const clockEl = document.getElementById("clock");
  const clockDateEl = document.getElementById("clock-date");
  const statusChip = document.getElementById("status-chip");
  const statusText = document.getElementById("status-text");
  const locationText = document.getElementById("location-text");

  const cameraModal = document.getElementById("camera-modal");
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const countdownEl = document.getElementById("countdown");
  const progressFill = document.getElementById("progress-fill");
  const progressCaption = document.getElementById("progress-caption");
  const modalTitle = document.getElementById("modal-title");
  const modalSub = document.getElementById("modal-sub");
  const captureCaption = document.getElementById("capture-caption");
  const cancelBtn = document.getElementById("cancel-btn");
  const ovalEl = document.querySelector(".oval");

  const loadingOverlay = document.getElementById("loading-overlay");
  const loadingMessage = document.getElementById("loading-message");

  const resultModal = document.getElementById("result-modal");
  const resultIcon = document.getElementById("result-icon");
  const resultTitle = document.getElementById("result-title");
  const resultMessage = document.getElementById("result-message");
  const resultClose = document.getElementById("result-close");

  // ── Reloj ──────────────────────────────────────────────────────────
  function actualizarReloj() {
    const ahora = new Date();
    const hh = String(ahora.getHours()).padStart(2, "0");
    const mm = String(ahora.getMinutes()).padStart(2, "0");
    clockEl.textContent = `${hh}:${mm}`;
    clockDateEl.textContent = `${ahora.getDate()} ${MESES[ahora.getMonth()]} ${ahora.getFullYear()}`;
  }
  actualizarReloj();
  setInterval(actualizarReloj, 1000 * 10);
  setInterval(actualizarReloj, 1000);

  // ── Geolocalización (adaptada a PC vía navigator.geolocation) ───────
  function inicializarUbicacion() {
    if (!("geolocation" in navigator)) {
      setStatusChip("error", "Geolocalización no soportada");
      locationText.textContent = "Este navegador no soporta geolocalización";
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        state.latitud = pos.coords.latitude;
        state.longitud = pos.coords.longitude;
        setStatusChip("ok", "Activo");

        try {
          const resp = await fetch(`/api/asistencia/ubicacion?lat=${state.latitud}&lng=${state.longitud}`);
          if (resp.ok) {
            const data = await resp.json();
            state.direccion = data.direccion;
            locationText.textContent = data.direccion;
          } else {
            locationText.textContent = `${state.latitud.toFixed(5)}, ${state.longitud.toFixed(5)}`;
          }
        } catch (err) {
          locationText.textContent = `${state.latitud.toFixed(5)}, ${state.longitud.toFixed(5)}`;
        }
      },
      (error) => {
        setStatusChip("error", "Ubicación no disponible");
        const mensajes = {
          1: "Permiso de ubicación denegado",
          2: "Ubicación no disponible",
          3: "Tiempo de espera agotado",
        };
        locationText.textContent = mensajes[error.code] || "Error de ubicación";
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  }

  function setStatusChip(kind, texto) {
    statusChip.classList.remove("status-chip--pending", "status-chip--error");
    if (kind === "error") statusChip.classList.add("status-chip--error");
    if (kind === "pending") statusChip.classList.add("status-chip--pending");
    statusText.textContent = texto;
  }

  // ── Botones de acción ─────────────────────────────────────────────
  document.querySelectorAll(".action-btn").forEach((btn) => {
    btn.addEventListener("click", () => iniciarProcesoAsistencia(btn.dataset.tipo));
  });

  async function iniciarProcesoAsistencia(tipo) {
    state.tipoSeleccionado = tipo;
    const fotoDataUrl = await abrirCamaraYCapturar();
    if (!fotoDataUrl) return; // cancelado por el usuario

    mostrarCarga("Procesando foto...");
    try {
      const resp = await fetch("/api/asistencia/registrar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          imagen: fotoDataUrl,
          tipo: tipo,
          latitud: state.latitud,
          longitud: state.longitud,
        }),
      });

      const data = await resp.json();
      ocultarCarga();

      if (!resp.ok || data.exito === false) {
        mostrarResultado(false, data.mensaje || "No se pudo completar el registro", data.similitud);
        return;
      }

      mostrarResultado(
        true,
        `${data.tipo} registrado para ${data.nombre} · ${data.hora}`,
      );
    } catch (err) {
      ocultarCarga();
      mostrarResultado(false, "Error de conexión con el servidor. Intenta de nuevo.");
    }
  }

  // ── Cámara + cuenta regresiva ────────────────────────────────────
  function abrirCamaraYCapturar() {
    return new Promise(async (resolve) => {
      resetCameraUI();
      cameraModal.classList.remove("hidden");

      try {
        state.mediaStream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: "user",
            width: { ideal: 720 },
            height: { ideal: 960 },
            // Pedimos exposición/balance de blancos automáticos y continuos;
            // no todos los navegadores/cámaras lo soportan, pero cuando sí,
            // mejora bastante la captura en ambientes con poca luz.
            advanced: [{ exposureMode: "continuous" }, { whiteBalanceMode: "continuous" }],
          },
          audio: false,
        });
        video.srcObject = state.mediaStream;

        // Si el navegador expone control manual de exposición, forzamos un
        // nivel alto (algunos drivers de webcam arrancan sub-expuestos).
        await ajustarExposicionSiEsPosible(state.mediaStream);
      } catch (err) {
        cerrarCamara();
        mostrarResultado(false, "No se pudo acceder a la cámara. Verifica los permisos del navegador.");
        resolve(null);
        return;
      }

      iniciarMonitorDeBrillo();

      const finalizar = (resultado) => {
        cerrarCamara();
        resolve(resultado);
      };

      cancelBtn.onclick = () => finalizar(null);

      // Cuenta regresiva de 3 segundos, igual que la app original
      state.secondsLeft = COUNTDOWN_SECONDS;
      countdownEl.textContent = String(state.secondsLeft);
      progressFill.style.transition = "none";
      progressFill.style.width = "0%";
      requestAnimationFrame(() => {
        progressFill.style.transition = `width ${COUNTDOWN_SECONDS}s linear`;
        progressFill.style.width = "100%";
      });

      state.countdownTimer = setInterval(() => {
        state.secondsLeft -= 1;
        if (state.secondsLeft > 0) {
          countdownEl.textContent = String(state.secondsLeft);
          progressCaption.textContent = `Capturando en ${state.secondsLeft} seg...`;
          if (state.secondsLeft <= 1) ovalEl.classList.add("ready");
        } else {
          clearInterval(state.countdownTimer);
          countdownEl.textContent = "";
          modalTitle.textContent = "¡Foto capturada!";
          modalSub.textContent = "";
          captureCaption.textContent = "Procesando identidad...";
          progressCaption.textContent = "Analizando rostro...";

          const dataUrl = capturarFrame();
          finalizar(dataUrl);
        }
      }, 1000);
    });
  }

  function capturarFrame() {
    const width = video.videoWidth || 720;
    const height = video.videoHeight || 960;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    // Espejamos horizontalmente para que la foto capturada coincida con lo
    // que el usuario ve en pantalla (misma corrección que hacía la app Flutter).
    ctx.translate(width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, width, height);
    return canvas.toDataURL("image/jpeg", 0.9);
  }

  function cerrarCamara() {
    if (state.mediaStream) {
      state.mediaStream.getTracks().forEach((track) => track.stop());
      state.mediaStream = null;
    }
    if (state.countdownTimer) {
      clearInterval(state.countdownTimer);
      state.countdownTimer = null;
    }
    detenerMonitorDeBrillo();
    cameraModal.classList.add("hidden");
  }

  // ── Ajuste de exposición y monitor de luz ambiente ────────────────
  let brightnessCanvas = null;

  /**
   * Intenta forzar exposición/brillo manual vía la API de MediaStream Track
   * Capabilities, si el navegador y la cámara lo soportan. No todos lo
   * soportan (Chrome/Edge en Windows con drivers compatibles sí suelen
   * exponer esto); si falla, simplemente se ignora y queda como respaldo
   * la corrección automática que hace el backend en image_utils.py.
   */
  async function ajustarExposicionSiEsPosible(stream) {
    try {
      const [track] = stream.getVideoTracks();
      if (!track || !track.getCapabilities) return;

      const capabilities = track.getCapabilities();
      const advanced = {};

      if (capabilities.exposureMode?.includes("continuous")) {
        advanced.exposureMode = "continuous";
      }
      if (capabilities.brightness) {
        const { min, max } = capabilities.brightness;
        // Subimos el brillo manual a ~65% del rango soportado por el driver.
        advanced.brightness = min + (max - min) * 0.65;
      }
      if (capabilities.whiteBalanceMode?.includes("continuous")) {
        advanced.whiteBalanceMode = "continuous";
      }

      if (Object.keys(advanced).length > 0) {
        await track.applyConstraints({ advanced: [advanced] });
      }
    } catch (err) {
      console.warn("No se pudo ajustar exposición manual de la cámara:", err);
    }
  }

  /**
   * Muestrea periódicamente el frame de video en un canvas oculto de baja
   * resolución para calcular el brillo promedio, y avisa al usuario en
   * vivo si el ambiente está muy oscuro para el reconocimiento facial.
   */
  function iniciarMonitorDeBrillo() {
    if (!brightnessCanvas) {
      brightnessCanvas = document.createElement("canvas");
      brightnessCanvas.width = 60;
      brightnessCanvas.height = 60;
    }
    const ctx = brightnessCanvas.getContext("2d", { willReadFrequently: true });

    state.brightnessTimer = setInterval(() => {
      if (!video.videoWidth) return;
      ctx.drawImage(video, 0, 0, brightnessCanvas.width, brightnessCanvas.height);
      const { data } = ctx.getImageData(0, 0, brightnessCanvas.width, brightnessCanvas.height);

      let sum = 0;
      for (let i = 0; i < data.length; i += 4) {
        sum += (data[i] + data[i + 1] + data[i + 2]) / 3;
      }
      const brillo = sum / (data.length / 4); // 0-255

      if (brillo < 60) {
        modalSub.textContent = "⚠️ Poca luz — acércate a una fuente de luz";
        modalSub.classList.add("low-light-warning");
      } else {
        modalSub.textContent = "Mantente quieto · Buena iluminación";
        modalSub.classList.remove("low-light-warning");
      }
    }, 500);
  }

  function detenerMonitorDeBrillo() {
    if (state.brightnessTimer) {
      clearInterval(state.brightnessTimer);
      state.brightnessTimer = null;
    }
  }

  function resetCameraUI() {
    modalTitle.textContent = "Centra tu rostro en el área";
    modalSub.textContent = "Mantente quieto · Buena iluminación";
    captureCaption.textContent = "Verificación biométrica";
    progressCaption.textContent = `Capturando en ${COUNTDOWN_SECONDS} seg...`;
    ovalEl.classList.remove("ready");
    countdownEl.textContent = String(COUNTDOWN_SECONDS);
  }

  // ── Overlay de carga ──────────────────────────────────────────────
  function mostrarCarga(mensaje) {
    loadingMessage.textContent = mensaje;
    loadingOverlay.classList.remove("hidden");
  }
  function ocultarCarga() {
    loadingOverlay.classList.add("hidden");
  }

  // ── Modal de resultado ────────────────────────────────────────────
  function mostrarResultado(exito, mensaje, similitud) {
    resultIcon.textContent = exito ? "✅" : "⚠️";
    resultTitle.textContent = exito ? "Registro exitoso" : "No se pudo registrar";
    resultMessage.textContent =
      similitud !== undefined && similitud !== null
        ? `${mensaje} (similitud: ${(similitud * 100).toFixed(1)}%)`
        : mensaje;
    resultModal.classList.remove("hidden");
  }
  resultClose.addEventListener("click", () => resultModal.classList.add("hidden"));

  // ── Init ───────────────────────────────────────────────────────────
  setStatusChip("pending", "Verificando ubicación…");
  inicializarUbicacion();
})();