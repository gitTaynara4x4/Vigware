window.VigAPI = {
  async request(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    let data = null;
    const type = res.headers.get("content-type") || "";
    if (type.includes("application/json")) data = await res.json();
    if (!res.ok) {
      throw new Error(data?.detail || `Erro HTTP ${res.status}`);
    }
    return data;
  },
  health() { return this.request("/api/health"); },
  monitoring() { return this.request("/api/monitoring"); },
  createDemo() { return this.request("/api/demo/seed", { method: "POST" }); },
  resetDemo() { return this.request("/api/demo/reset", { method: "POST" }); },
  simulateE130() { return this.request("/api/demo/simulate/e130", { method: "POST" }); },
  simulateE301() { return this.request("/api/demo/simulate/e301", { method: "POST" }); },
  occurrence(id) { return this.request(`/api/occurrences/${id}`); },
  watchOccurrence(id) { return this.request(`/api/occurrences/${id}/watch`, { method: "POST" }); },
  unwatchOccurrence(id) { return this.request(`/api/occurrences/${id}/unwatch`, { method: "POST" }); },
  setStatus(id, status, note = null) {
    return this.request(`/api/occurrences/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    });
  },
  sendCommand(id, command, partition = null, note = null) {
    return this.request(`/api/occurrences/${id}/command`, {
      method: "POST",
      body: JSON.stringify({ command, partition, note }),
    });
  },
};
