window.VigMonitoring = {
  currentOccurrenceId: null,
  boardColumns: {},
  detailData: null,
  draggingOccurrenceId: null,
  draggingFromStatus: null,
  isDraggingCard: false,
  suppressCardClickUntil: 0,

  columnStatusMap: {
    newers: "NEW",
    started: "STARTED",
    displacement: "DISPLACEMENT",
    observation: "OBSERVATION",
  },

  statusLabelMap: {
    NEW: "Novos",
    STARTED: "Iniciado",
    DISPLACEMENT: "Deslocamento",
    OBSERVATION: "Observação",
  },

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
      body.dataset.column = key;
      body.dataset.status = this.columnStatusMap[key] || "NEW";
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

    // Clique nos cards é tratado por delegação em bindEvents().
    // Isso evita o problema de perder listeners quando a tela atualiza em tempo real.
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
      <button
        class="occ-card ${priority}${selected}"
        type="button"
        draggable="true"
        data-occurrence-id="${card.id}"
        data-id="${card.id}"
        data-status="${VigUI.escape(card.status || "")}"
        onclick="return window.vigOpenOccurrenceFromCard(this, event);"
        ondblclick="return window.vigOpenOccurrenceFromCard(this, event);"
      >
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

  showWorkspaceLoading(occurrenceId) {
    const board = document.getElementById("boardView");
    const workspace = document.getElementById("incidentWorkspace");
    if (board) board.hidden = true;
    if (workspace) workspace.hidden = false;

    const safeId = VigUI.escape(occurrenceId);
    const setText = (id, value) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    };
    setText("detailQueueTitle", "Abrindo");
    setText("detailQueueCount", "...");
    setText("detailTypeIcon", "◇");
    setText("detailTitle", `Ocorrência #${safeId}`);
    setText("detailSubtitle", "Carregando atendimento...");
    setText("detailStatus", "...");
    setText("detailClientName", "Carregando cliente...");
    setText("detailClientMeta", "Aguarde");

    const html = `<div class="empty flat">Carregando ocorrência #${safeId}...</div>`;
    ["detailQueueList", "detailTimeline", "detailLocation", "detailProtocol", "detailContacts", "detailZones", "detailConnections"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = html;
    });
  },

  async openOccurrence(id) {
    const occurrenceId = Number(id);
    if (!Number.isFinite(occurrenceId) || occurrenceId <= 0) {
      VigUI.toast("Ocorrência inválida");
      return false;
    }

    this.currentOccurrenceId = occurrenceId;
    this.showWorkspaceLoading(occurrenceId);

    try {
      const data = await VigAPI.occurrence(occurrenceId);

      try {
        await VigAPI.watchOccurrence(occurrenceId);
      } catch (watchError) {
        console.warn("Não foi possível marcar ocorrência como assistida:", watchError);
      }

      this.renderWorkspace(data);
      return false;
    } catch (error) {
      console.error("Erro ao abrir ocorrência:", error);
      VigUI.toast(error?.message || "Não foi possível abrir a ocorrência");
      // Mantém a tela de atendimento aberta mostrando o erro, em vez de parecer que nada aconteceu.
      const timeline = document.getElementById("detailTimeline");
      if (timeline) {
        timeline.innerHTML = `<div class="empty flat">Erro ao carregar ocorrência: ${VigUI.escape(error?.message || error)}</div>`;
      }
      return false;
    }
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
    // Clique nos cards da fila lateral também é tratado por delegação em bindEvents().

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
      <div class="connection-card">
        <div class="connection-top">
          <div class="connection-dot ${c.armed ? "armed" : "disarmed"}"></div>
          <div class="detail-row-main">
            <strong>${VigUI.escape(c.name)} - ${VigUI.escape(c.status)}</strong>
            <span>Partição ${VigUI.escape(c.partition_number || "001")} · ${VigUI.escape(c.armed_label || "--")}</span>
          </div>
          <div class="connection-state ${c.armed ? "is-armed" : "is-disarmed"}">${VigUI.escape(c.armed_label || "--")}</div>
        </div>
        <div class="connection-meta">
          <span>Último evento ${VigUI.escape(c.last_event_code || "-")} · ${VigUI.fmtDate(c.last_event_at)}</span>
          <span>Último arme/desarme ${VigUI.escape(c.last_arm_event_code || "-")} · ${c.last_arm_event_at ? VigUI.fmtDate(c.last_arm_event_at) : "--"}</span>
        </div>
        <div class="connection-actions">
          <button type="button" class="command-action" data-command="ARM" data-partition="${VigUI.escape(c.partition_number || "001")}">Armar</button>
          <button type="button" class="command-action" data-command="DISARM" data-partition="${VigUI.escape(c.partition_number || "001")}">Desarmar</button>
        </div>
      </div>
    `).join("");

    const occurrenceTimeline = (data.timeline || []).map(t => this.timelineHtml(t)).join("");
    const accountHistory = (data.account_events || []).length
      ? `<div class="timeline-divider">Histórico da conta / arme e desarme</div>` + data.account_events.map(t => this.timelineHtml(t)).join("")
      : "";
    document.getElementById("detailTimeline").innerHTML = occurrenceTimeline + accountHistory || `<div class="empty">Sem timeline</div>`;

    document.querySelectorAll(".command-action").forEach(btn => {
      btn.addEventListener("click", () => this.requestCommand(btn.dataset.command, btn.dataset.partition));
    });
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


  statusToColumn(status) {
    const map = { NEW: "newers", STARTED: "started", DISPLACEMENT: "displacement", OBSERVATION: "observation" };
    return map[String(status || "").toUpperCase()] || "newers";
  },

  findCardInBoard(occurrenceId) {
    const id = Number(occurrenceId);
    for (const [columnKey, list] of Object.entries(this.boardColumns || {})) {
      const index = (list || []).findIndex(card => Number(card.id) === id);
      if (index >= 0) return { columnKey, index, card: list[index] };
    }
    return null;
  },

  optimisticallyMoveCard(occurrenceId, targetStatus) {
    const targetColumn = this.statusToColumn(targetStatus);
    const found = this.findCardInBoard(occurrenceId);
    if (!found) return;

    const card = { ...found.card, status: targetStatus, status_label: this.statusLabelMap[targetStatus] || targetStatus };
    const nextColumns = { ...this.boardColumns };
    for (const key of Object.keys(nextColumns)) {
      nextColumns[key] = [...(nextColumns[key] || [])].filter(item => Number(item.id) !== Number(occurrenceId));
    }
    nextColumns[targetColumn] = [card, ...(nextColumns[targetColumn] || [])];
    this.boardColumns = nextColumns;
    this.renderBoard(this.boardColumns);
  },

  clearDropUi() {
    document.body.classList.remove("dragging-occurrence");
    document.querySelectorAll(".column-body.drop-over, .column.drop-over").forEach(el => el.classList.remove("drop-over"));
    document.querySelectorAll(".occ-card.dragging").forEach(el => el.classList.remove("dragging"));
  },

  async moveOccurrenceByDrag(occurrenceId, targetStatus) {
    const id = Number(occurrenceId);
    const status = String(targetStatus || "").toUpperCase();
    if (!Number.isFinite(id) || !this.statusLabelMap[status]) return;

    const found = this.findCardInBoard(id);
    const oldStatus = String(found?.card?.status || "").toUpperCase();
    if (oldStatus === status) return;

    this.suppressCardClickUntil = Date.now() + 800;
    this.optimisticallyMoveCard(id, status);

    try {
      await VigAPI.setStatus(id, status, `Movido por arrastar para ${this.statusLabelMap[status]}`);
      VigUI.toast(`Movido para ${this.statusLabelMap[status]}`);
      await this.refresh();

      if (this.currentOccurrenceId === id && !document.getElementById("incidentWorkspace")?.hidden) {
        const data = await VigAPI.occurrence(id);
        this.renderWorkspace(data);
      }
    } catch (error) {
      console.error("Erro ao mover ocorrência por arrastar:", error);
      VigUI.toast(error?.message || "Não foi possível mover a ocorrência");
      await this.refresh();
    }
  },

  async requestCommand(command, partition) {
    if (!this.currentOccurrenceId) return;
    const label = command === "ARM" ? "Armar" : "Desarmar";
    const ok = window.confirm(`${label} a partição ${partition || "001"}?`);
    if (!ok) return;
    const res = await VigAPI.sendCommand(this.currentOccurrenceId, command, partition);
    VigUI.toast(`Comando solicitado: ${res.label || label}`);
    const data = await VigAPI.occurrence(this.currentOccurrenceId);
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

    if (!this._dragDropBound) {
      this._dragDropBound = true;

      document.addEventListener("dragstart", event => {
        const card = event.target?.closest?.(".occ-card");
        const board = document.getElementById("boardView");
        if (!card || !board || !board.contains(card)) return;

        const id = card.dataset.occurrenceId || card.dataset.id;
        this.draggingOccurrenceId = id;
        this.draggingFromStatus = card.dataset.status || null;
        this.isDraggingCard = true;
        this.suppressCardClickUntil = Date.now() + 1000;

        card.classList.add("dragging");
        document.body.classList.add("dragging-occurrence");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(id));
        event.dataTransfer.setData("application/x-vigware-occurrence", String(id));
      }, true);

      document.addEventListener("dragover", event => {
        const body = event.target?.closest?.(".column-body");
        const board = document.getElementById("boardView");
        if (!body || !board || !board.contains(body) || !this.isDraggingCard) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        document.querySelectorAll(".column-body.drop-over").forEach(el => {
          if (el !== body) el.classList.remove("drop-over");
        });
        body.classList.add("drop-over");
        body.closest(".column")?.classList.add("drop-over");
      }, true);

      document.addEventListener("dragleave", event => {
        const body = event.target?.closest?.(".column-body");
        if (!body) return;
        const related = event.relatedTarget;
        if (related && body.contains(related)) return;
        body.classList.remove("drop-over");
        body.closest(".column")?.classList.remove("drop-over");
      }, true);

      document.addEventListener("drop", event => {
        const body = event.target?.closest?.(".column-body");
        const board = document.getElementById("boardView");
        if (!body || !board || !board.contains(body) || !this.isDraggingCard) return;

        event.preventDefault();
        event.stopPropagation();

        const id = event.dataTransfer.getData("application/x-vigware-occurrence") || event.dataTransfer.getData("text/plain") || this.draggingOccurrenceId;
        const targetStatus = body.dataset.status || this.columnStatusMap[body.dataset.column];

        this.clearDropUi();
        this.isDraggingCard = false;
        this.draggingOccurrenceId = null;
        this.draggingFromStatus = null;
        this.suppressCardClickUntil = Date.now() + 900;

        this.moveOccurrenceByDrag(id, targetStatus);
      }, true);

      document.addEventListener("dragend", () => {
        this.clearDropUi();
        this.isDraggingCard = false;
        this.draggingOccurrenceId = null;
        this.draggingFromStatus = null;
        this.suppressCardClickUntil = Date.now() + 500;
      }, true);
    }

    if (!this._delegatedCardClickBound) {
      this._delegatedCardClickBound = true;

      window.vigOpenOccurrenceFromCard = (card, event) => {
        if (this.isDraggingCard || Date.now() < this.suppressCardClickUntil) {
          if (event) {
            event.preventDefault();
            event.stopPropagation();
          }
          return false;
        }
        try {
          if (event) {
            event.preventDefault();
            event.stopPropagation();
          }
          const id = card?.dataset?.occurrenceId || card?.dataset?.id || card?.getAttribute?.("data-id");
          this.openOccurrence(id);
        } catch (error) {
          console.error("Falha no clique do card:", error);
          VigUI.toast("Falha ao abrir card");
        }
        return false;
      };

      const openFromEvent = (event) => {
        const card = event.target?.closest?.(".occ-card,[data-occurrence-id]");
        if (!card) return;

        const board = document.getElementById("boardView");
        const workspace = document.getElementById("incidentWorkspace");
        const isInBoard = board && board.contains(card);
        const isInWorkspaceQueue = workspace && workspace.contains(card);
        if (!isInBoard && !isInWorkspaceQueue) return;

        window.vigOpenOccurrenceFromCard(card, event);
      };

      document.addEventListener("click", openFromEvent, true);
      document.addEventListener("pointerup", openFromEvent, true);
      document.addEventListener("dblclick", openFromEvent, true);
    }
  },
};
