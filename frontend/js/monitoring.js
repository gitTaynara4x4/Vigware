window.VigMonitoring = {
  currentOccurrenceId: null,
  boardColumns: {},
  detailData: null,

  async refresh() {
    const data = await VigAPI.monitoring();
    this.boardColumns = data.columns || {};
    this.renderBoard(this.boardColumns);
    if (this.currentOccurrenceId && !document.getElementById("incidentWorkspace")?.hidden) {
      try {
        const detail = await VigAPI.occurrence(this.currentOccurrenceId);
        this.renderWorkspace(detail);
      } catch {}
    }
  },

  renderBoard(columns) {
    const keys = ["newers", "started", "displacement", "observation"];
    let total = 0;
    let high = 0;

    for (const key of keys) {
      const list = columns[key] || [];
      total += list.length;
      high += list.filter(x => x.priority === "high").length;
      const body = document.getElementById(`col-${key}`);
      const count = document.getElementById(`count-${key}`);
      if (count) count.textContent = list.length;
      if (!body) continue;
      if (!list.length) {
        body.innerHTML = `<div class="empty">Nenhuma ocorrência</div>`;
        continue;
      }
      body.innerHTML = list.map(card => this.cardHtml(card)).join("");
    }

    const metricTotal = document.getElementById("metricTotal");
    const metricHigh = document.getElementById("metricHigh");
    const metricUpdated = document.getElementById("metricUpdated");
    if (metricTotal) metricTotal.textContent = total;
    if (metricHigh) metricHigh.textContent = high;
    const now = new Date();
    if (metricUpdated) metricUpdated.textContent = now.toLocaleTimeString("pt-BR");
    const segClock = document.getElementById("segClock");
    if (segClock) segClock.textContent = now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

    document.querySelectorAll(".occ-card").forEach(btn => {
      btn.addEventListener("click", () => this.openOccurrence(Number(btn.dataset.id)));
    });
  },

  eventIcon(card) {
    const code = String(card.event_code || "").toUpperCase();
    const desc = String(card.description || "").toLowerCase();
    if (code === "1250" || desc.includes("keep alive") || desc.includes("conex") || desc.includes("comunica")) return "◇";
    if (desc.includes("pânico") || desc.includes("panico")) return "!";
    if (desc.includes("desarme") || desc.includes("arme")) return "⌂";
    return "◆";
  },

  cardHtml(card) {
    const priority = card.priority || "medium";
    const client = card.client_name || card.account_name || "Conta não cadastrada";
    const partition = card.partition_number || "001";
    const selected = this.currentOccurrenceId === card.id ? " selected" : "";
    return `
      <button class="occ-card ${priority}${selected}" type="button" data-id="${card.id}">
        <div class="card-icon" aria-hidden="true">${this.eventIcon(card)}</div>
        <div class="card-main">
          <div class="card-client">${VigUI.escape(client)}</div>
          <div class="card-account">${VigUI.escape(card.account_code)} - ${VigUI.escape(partition)}</div>
          <div class="card-desc">${VigUI.escape(card.description)}</div>
        </div>
        <div class="card-code">${VigUI.escape(card.event_code)}</div>
      </button>
    `;
  },

  async openOccurrence(id) {
    this.currentOccurrenceId = id;
    await VigAPI.watchOccurrence(id);
    const data = await VigAPI.occurrence(id);
    this.renderWorkspace(data);
    document.getElementById("boardView").hidden = true;
    document.getElementById("incidentWorkspace").hidden = false;
  },

  async backToBoard() {
    if (this.currentOccurrenceId) {
      try { await VigAPI.unwatchOccurrence(this.currentOccurrenceId); } catch {}
    }
    this.currentOccurrenceId = null;
    this.detailData = null;
    document.getElementById("incidentWorkspace").hidden = true;
    document.getElementById("boardView").hidden = false;
    await this.refresh();
  },

  async closeModal() {
    await this.backToBoard();
  },

  statusKey(status) {
    const map = { NEW: "newers", STARTED: "started", DISPLACEMENT: "displacement", IN_PLACE: "inPlace", OBSERVATION: "observation" };
    return map[status] || "newers";
  },

  renderWorkspace(data) {
    this.detailData = data;
    const occ = data.occurrence || {};
    const account = data.account || {};
    const client = data.client || {};
    const statusKey = this.statusKey(occ.status);
    const queue = this.boardColumns[statusKey] || [];

    document.getElementById("detailQueueTitle").textContent = occ.status_label || "Ocorrência";
    document.getElementById("detailQueueCount").textContent = queue.length;
    document.getElementById("detailQueueList").innerHTML = queue.length
      ? queue.map(card => this.cardHtml(card)).join("")
      : `<div class="empty">Nenhuma ocorrência</div>`;
    document.querySelectorAll("#detailQueueList .occ-card").forEach(btn => {
      btn.addEventListener("click", () => this.openOccurrence(Number(btn.dataset.id)));
    });

    const clientName = occ.client_name || client.trade_name || client.name || account.name || `Conta ${occ.account_code}`;
    document.getElementById("detailTypeIcon").textContent = this.eventIcon(occ);
    document.getElementById("detailTitle").textContent = occ.description || "Ocorrência";
    document.getElementById("detailSubtitle").textContent = `Grupo de ocorrências · ${occ.event_code || "-"}`;
    document.getElementById("detailStatus").textContent = occ.status_label || occ.status || "--";
    document.getElementById("detailClientName").textContent = clientName;
    document.getElementById("detailClientMeta").textContent = `Conta: ${occ.account_code || account.code || "-"} | Partição: ${occ.partition_number || account.partition_number || "001"}`;

    const address = client.address || account.notes || data.location_hint || "Endereço não cadastrado";
    document.getElementById("detailLocation").innerHTML = `
      <div class="local-line strong">⌂ ${VigUI.escape(address)}</div>
      <div class="local-line">Conta ${VigUI.escape(occ.account_code || "-")} · Partição ${VigUI.escape(occ.partition_number || "001")}</div>
      <div class="local-line dark">Meio de comunicação primário: ACTIVE NET / JFL</div>
    `;

    const protocol = data.operator_hint || account.protocol_note || "Sem procedimento específico cadastrado. Seguir protocolo padrão da central: confirmar evento, tentar contato, registrar providência e escalar conforme criticidade.";
    document.getElementById("detailProtocol").textContent = protocol;

    document.getElementById("detailContacts").innerHTML = (data.contacts || []).map(c => `
      <div class="detail-row">
        <div class="detail-row-icon">☎</div>
        <div class="detail-row-main">
          <strong>${VigUI.escape(c.name)}</strong>
          <span>${VigUI.escape(c.password_hint || "Contato")}</span>
        </div>
        <div class="detail-phone">${VigUI.escape(c.phone || "-")}</div>
      </div>
    `).join("") || `<div class="empty flat">Sem contatos cadastrados</div>`;

    document.getElementById("detailZones").innerHTML = (data.zones || []).map(z => `
      <div class="detail-row slim"><div class="detail-row-icon">▣</div><div class="detail-row-main"><strong>${VigUI.escape(z.zone_number)} - ${VigUI.escape(z.name)}</strong><span>${VigUI.escape(z.area || "")}</span></div></div>
    `).join("") || `<div class="empty flat">Sem zonas/áreas cadastradas</div>`;

    document.getElementById("detailConnections").innerHTML = (data.connections || []).map(c => `
      <div class="detail-row slim"><div class="connection-dot"></div><div class="detail-row-main"><strong>${VigUI.escape(c.name)} - ${VigUI.escape(c.status)}</strong><span>Último evento ${VigUI.escape(c.last_event_code || "-")} · ${VigUI.fmtDate(c.last_event_at)}</span></div></div>
    `).join("");

    document.getElementById("detailTimeline").innerHTML = (data.timeline || []).map(t => this.timelineHtml(t)).join("") || `<div class="empty">Sem timeline</div>`;
  },

  timelineHtml(t) {
    const icon = t.type === "STATUS" ? "↔" : (t.type === "RESTORE" ? "✓" : "!");
    return `
      <div class="seg-timeline-item">
        <div class="seg-time-icon">${icon}</div>
        <div class="seg-time-main">
          <strong>${VigUI.escape(t.title)}</strong>
          ${t.description ? `<span>${VigUI.escape(t.description)}</span>` : ""}
        </div>
        <time>${VigUI.fmtDate(t.created_at)}</time>
      </div>
    `;
  },

  renderModal(data) {
    this.renderWorkspace(data);
  },

  async changeStatus(status) {
    if (!this.currentOccurrenceId) return;
    await VigAPI.setStatus(this.currentOccurrenceId, status);
    VigUI.toast("Status atualizado");
    await this.refresh();
    if (["FINISHED", "CANCELED"].includes(status)) {
      await this.backToBoard();
      return;
    }
    const data = await VigAPI.occurrence(this.currentOccurrenceId);
    this.renderWorkspace(data);
  },

  bindEvents() {
    document.getElementById("btnRefresh")?.addEventListener("click", () => this.refresh());
    document.getElementById("queueBackBtn")?.addEventListener("click", () => this.backToBoard());
    document.getElementById("btnBackBoard2")?.addEventListener("click", () => this.backToBoard());
    document.getElementById("btnCloseModal")?.addEventListener("click", () => this.closeModal());
    document.querySelectorAll(".status-action").forEach(btn => {
      btn.addEventListener("click", () => this.changeStatus(btn.dataset.status));
    });
  },
};
