window.VigMonitoring = {
  currentOccurrenceId: null,

  async refresh() {
    const data = await VigAPI.monitoring();
    this.renderBoard(data.columns);
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
    if (metricUpdated) metricUpdated.textContent = new Date().toLocaleTimeString("pt-BR");

    document.querySelectorAll(".occ-card").forEach(btn => {
      btn.addEventListener("click", () => this.openOccurrence(Number(btn.dataset.id)));
    });
  },

  eventIcon(card) {
    const code = String(card.event_code || "").toUpperCase();
    const desc = String(card.description || "").toLowerCase();
    if (code === "1250" || desc.includes("keep alive") || desc.includes("comunica")) return "◇";
    if (desc.includes("pânico") || desc.includes("panico")) return "!";
    if (desc.includes("desarme") || desc.includes("arme")) return "⌂";
    return "◆";
  },

  cardHtml(card) {
    const priority = card.priority || "medium";
    const client = card.client_name || card.account_name || "Conta não cadastrada";
    const partition = card.partition_number || "001";
    return `
      <button class="occ-card ${priority}" type="button" data-id="${card.id}">
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
    this.renderModal(data);
    const backdrop = document.getElementById("modalBackdrop");
    backdrop.hidden = false;
  },

  async closeModal() {
    const backdrop = document.getElementById("modalBackdrop");
    if (this.currentOccurrenceId) {
      try { await VigAPI.unwatchOccurrence(this.currentOccurrenceId); } catch {}
    }
    this.currentOccurrenceId = null;
    backdrop.hidden = true;
    await this.refresh();
  },

  renderModal(data) {
    const occ = data.occurrence;
    document.getElementById("modalTitle").textContent = `#${occ.id} · ${occ.description}`;
    document.getElementById("modalSubtitle").textContent = `${occ.client_name} · Conta ${occ.account_code} · ${occ.status_label}`;

    const client = data.client || {};
    document.getElementById("clientBox").innerHTML = [
      VigUI.info("Nome", client.trade_name || client.name),
      VigUI.info("Telefone", client.phone),
      VigUI.info("E-mail", client.email),
      VigUI.info("Endereço", client.address),
    ].join("");

    const account = data.account || {};
    document.getElementById("accountBox").innerHTML = [
      VigUI.info("Conta", account.code),
      VigUI.info("Local", account.name),
      VigUI.info("Armado", account.armed ? "Sim" : "Não"),
      VigUI.info("Observação", account.notes),
      VigUI.info("Protocolo", account.protocol_note),
    ].join("");

    document.getElementById("contactsBox").innerHTML = (data.contacts || []).map(c => `
      <div class="info-item">
        <div class="info-label">Prioridade ${VigUI.escape(c.priority)}</div>
        <div class="info-value">${VigUI.escape(c.name)} · ${VigUI.escape(c.phone)}</div>
        <div class="timeline-desc">${VigUI.escape(c.password_hint || "")}</div>
      </div>
    `).join("") || `<div class="empty">Sem contatos</div>`;

    document.getElementById("zonesBox").innerHTML = (data.zones || []).map(z => `
      <div class="info-item">
        <div class="info-label">Zona ${VigUI.escape(z.zone_number)} · ${VigUI.escape(z.area || "")}</div>
        <div class="info-value">${VigUI.escape(z.name)}</div>
      </div>
    `).join("") || `<div class="empty">Sem zonas</div>`;

    document.getElementById("patrolBox").innerHTML = (data.patrol_cars || []).map(p => `
      <div class="info-item">
        <div class="info-label">${p.online ? "Online" : "Offline"} · ${p.available ? "Disponível" : "Ocupada"}</div>
        <div class="info-value">${VigUI.escape(p.description)} · ${VigUI.escape(p.plates || "")}</div>
      </div>
    `).join("") || `<div class="empty">Sem viaturas</div>`;

    document.getElementById("timelineBox").innerHTML = (data.timeline || []).map(t => `
      <div class="timeline-item">
        <div class="timeline-title">${VigUI.escape(t.title)}</div>
        ${t.description ? `<div class="timeline-desc">${VigUI.escape(t.description)}</div>` : ""}
        <div class="timeline-date">${VigUI.fmtDate(t.created_at)}</div>
      </div>
    `).join("") || `<div class="empty">Sem timeline</div>`;
  },

  async changeStatus(status) {
    if (!this.currentOccurrenceId) return;
    await VigAPI.setStatus(this.currentOccurrenceId, status);
    VigUI.toast("Status atualizado");
    const data = await VigAPI.occurrence(this.currentOccurrenceId);
    this.renderModal(data);
    await this.refresh();
    if (["FINISHED", "CANCELED"].includes(status)) await this.closeModal();
  },

  bindEvents() {
    document.getElementById("btnCreateDemo")?.addEventListener("click", async () => {
      await VigAPI.createDemo();
      VigUI.toast("Demo criada");
      await this.refresh();
    });
    document.getElementById("btnSimulate")?.addEventListener("click", async () => {
      await VigAPI.simulateE130();
      VigUI.toast("Evento E130 recebido");
      await this.refresh();
    });
    document.getElementById("btnSimulateTech")?.addEventListener("click", async () => {
      await VigAPI.simulateE301();
      VigUI.toast("Evento E301 recebido");
      await this.refresh();
    });
    document.getElementById("btnReset")?.addEventListener("click", async () => {
      await VigAPI.resetDemo();
      VigUI.toast("Ocorrências limpas");
      await this.refresh();
    });
    document.getElementById("btnRefresh")?.addEventListener("click", () => this.refresh());
    document.getElementById("btnCloseModal")?.addEventListener("click", () => this.closeModal());
    document.getElementById("modalBackdrop")?.addEventListener("click", (event) => {
      if (event.target.id === "modalBackdrop") this.closeModal();
    });
    document.querySelectorAll(".status-action").forEach(btn => {
      btn.addEventListener("click", () => this.changeStatus(btn.dataset.status));
    });
  },
};
