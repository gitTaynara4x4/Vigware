window.VigWS = {
  socket: null,
  start(onMessage) {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${location.host}/ws/monitoring`;
    this.socket = new WebSocket(url);
    const dot = () => document.querySelector(".status-dot");
    const label = () => document.getElementById("wsStatus");

    this.socket.addEventListener("open", () => {
      dot()?.classList.add("online");
      if (label()) label().textContent = "Tempo real online";
      setInterval(() => {
        try { this.socket?.send("ping"); } catch {}
      }, 25000);
    });

    this.socket.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type !== "connected") onMessage?.(data);
      } catch {}
    });

    this.socket.addEventListener("close", () => {
      dot()?.classList.remove("online");
      if (label()) label().textContent = "Reconectando...";
      setTimeout(() => this.start(onMessage), 3000);
    });
  },
};
