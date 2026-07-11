window.VigWS = {
  socket: null,
  reconnectTimer: null,
  heartbeatTimer: null,
  stopped: true,
  onMessage: null,

  start(onMessage) {
    this.stop();
    this.stopped = false;
    this.onMessage = onMessage;
    this.connect();
  },

  connect() {
    if (this.stopped) return;

    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${location.host}/ws/monitoring`;
    this.socket = new WebSocket(url);

    const dot = () => document.querySelector(".status-dot");
    const label = () => document.getElementById("wsStatus");

    this.socket.addEventListener("open", () => {
      dot()?.classList.add("online");
      if (label()) label().textContent = "Tempo real online";

      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = setInterval(() => {
        try {
          if (this.socket?.readyState === WebSocket.OPEN) this.socket.send("ping");
        } catch {}
      }, 25000);
    });

    this.socket.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type !== "connected") this.onMessage?.(data);
      } catch {}
    });

    this.socket.addEventListener("close", (event) => {
      clearInterval(this.heartbeatTimer);
      dot()?.classList.remove("online");

      if (event.code === 4401) {
        window.dispatchEvent(new CustomEvent("vigware:unauthorized"));
        return;
      }

      if (this.stopped) return;
      if (label()) label().textContent = "Reconectando...";
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    });
  },

  stop() {
    this.stopped = true;
    clearTimeout(this.reconnectTimer);
    clearInterval(this.heartbeatTimer);
    this.reconnectTimer = null;
    this.heartbeatTimer = null;

    if (this.socket) {
      try { this.socket.close(); } catch {}
    }
    this.socket = null;
  },
};
