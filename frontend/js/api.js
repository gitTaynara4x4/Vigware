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
  bulkCloseOptions() { return this.request("/api/occurrences/bulk/options"); },
  searchBulkOccurrences(filters = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value).trim() !== "") {
        params.set(key, String(value).trim());
      }
    });
    const query = params.toString();
    return this.request(`/api/occurrences/bulk/search${query ? `?${query}` : ""}`);
  },
  closeBulkOccurrences(occurrenceIds, log) {
    return this.request("/api/occurrences/bulk/close", {
      method: "POST",
      body: JSON.stringify({ occurrence_ids: occurrenceIds, log }),
    });
  },
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
  addLog(id, text) {
    return this.request(`/api/occurrences/${id}/log`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
  },
  addTemporaryNote(id, note = "", providence = "") {
    return this.request(`/api/occurrences/${id}/temporary-note`, {
      method: "POST",
      body: JSON.stringify({ note, providence }),
    });
  },
  addManualEvent(id, event_code, note = "") {
    return this.request(`/api/occurrences/${id}/manual-event`, {
      method: "POST",
      body: JSON.stringify({ event_code, note }),
    });
  },
  addMediaNote(id, filenames) {
    return this.request(`/api/occurrences/${id}/media-note`, {
      method: "POST",
      body: JSON.stringify({ filenames }),
    });
  },
};
