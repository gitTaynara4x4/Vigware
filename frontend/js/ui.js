window.VigUI = {
  async loadPartial(mountId, url) {
    const mount = document.getElementById(mountId);
    if (!mount) return;
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) {
      const error = new Error(`Não foi possível carregar ${url}`);
      error.status = res.status;
      throw error;
    }
    mount.innerHTML = await res.text();
  },

  toast(message) {
    const old = document.querySelector(".toast");
    if (old) old.remove();
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2600);
  },

  fmtDate(value) {
    if (!value) return "--";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString("pt-BR");
  },

  escape(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;"
    }[ch]));
  },

  info(label, value) {
    return `<div class="info-item"><div class="info-label">${this.escape(label)}</div><div class="info-value">${this.escape(value || "-")}</div></div>`;
  },
};
