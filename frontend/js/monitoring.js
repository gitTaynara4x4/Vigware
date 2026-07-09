window.VigMonitoring = {
  currentOccurrenceId: null,
  boardColumns: {},
  detailData: null,
  timelineFilter: "all",
  queueFocus: null,
  isOpeningOccurrence: false,
  mediaFiles: [],

  async refresh() {
    const data = await VigAPI.monitoring();
    this.boardColumns = data.columns || {};
    this.renderBoard(this.boardColumns);
    if (this.currentOccurrenceId && !document.getElementById("incidentWorkspace")?.hidden) {
      try {
        const detail = await VigAPI.occurrence(this.currentOccurrenceId);
        this.renderWorkspace(detail);
      } catch (error) {
        console.warn("Não foi possível atualizar atendimento aberto", error);
      }
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
  },

  eventIcon(card) {
    const code = String(card.event_code || "").toUpperCase();
    const desc = String(card.description || "").toLowerCase();
    if (code === "1250" || desc.includes("keep alive") || desc.includes("conex") || desc.includes("comunica")) return "◇";
    if (code === "1130" || desc.includes("alarme") || desc.includes("furto") || desc.includes("disparo")) return "◆";
    if (code === "3130" || desc.includes("normalizada") || desc.includes("restaura")) return "✓";
    if (desc.includes("pânico") || desc.includes("panico")) return "!";
    if (desc.includes("desarme") || desc.includes("arme")) return "⌂";
    return "◆";
  },

  cardHtml(card) {
    const priority = card.priority || "medium";
    const client = card.client_name || card.account_name || "Conta não cadastrada";
    const partition = card.partition_number || "001";
    const selected = Number(this.currentOccurrenceId) === Number(card.id) ? " selected" : "";
    const countBadge = Number(card.event_count || 0) > 1 ? `<span class="card-count">${Number(card.event_count)}</span>` : "";
    return `
      <a class="occ-card ${priority}${selected}" href="#occurrence-${card.id}" role="button" draggable="true" data-id="${card.id}" data-status="${VigUI.escape(card.status || "")}" onclick="return window.VigMonitoring.handleCardAnchorClick(event, ${card.id})" ondblclick="return window.VigMonitoring.handleCardAnchorClick(event, ${card.id})">
        <div class="card-icon" aria-hidden="true">${this.eventIcon(card)}</div>
        <div class="card-main">
          <div class="card-client">${VigUI.escape(client)}</div>
          <div class="card-account">${VigUI.escape(card.account_code)} - ${VigUI.escape(partition)}</div>
          <div class="card-desc">${VigUI.escape(card.description)}</div>
        </div>
        <div class="card-side">
          ${countBadge}
          <span class="card-code">${VigUI.escape(card.event_code)}</span>
        </div>
      </a>
    `;
  },

  handleCardAnchorClick(event, id) {
    // Caminho mais seguro: o próprio card é um link (#occurrence-ID).
    // Mesmo se a tela atualizar e perder listeners, o hash continua abrindo a ocorrência.
    const occurrenceId = Number(id);
    if (!Number.isFinite(occurrenceId) || occurrenceId <= 0) return false;

    const card = event?.target?.closest?.(".occ-card");
    if (this.cardMovedTooMuch(card, event) || this.wasJustDragged()) {
      event?.preventDefault?.();
      return false;
    }

    event?.preventDefault?.();
    event?.stopPropagation?.();
    if (window.location.hash !== `#occurrence-${occurrenceId}`) {
      window.location.hash = `occurrence-${occurrenceId}`;
    }
    this.openOccurrence(occurrenceId);
    return false;
  },

  cardMovedTooMuch(card, event) {
    if (!card || !event || event.clientX === undefined) return false;
    const dx = Math.abs((event.clientX || 0) - Number(card.dataset.downX || event.clientX || 0));
    const dy = Math.abs((event.clientY || 0) - Number(card.dataset.downY || event.clientY || 0));
    return dx > 10 || dy > 10;
  },

  wasJustDragged() {
    return Date.now() - Number(this._lastDragAt || 0) < 280;
  },

  openCardFromElement(card, event) {
    if (!card) return false;
    if (event?.target?.closest?.(".status-action,.command-action,.manual-event-btn,.timeline-filter,.queue-filter,.media-empty-button,input,textarea,select,label")) return false;
    if (this.cardMovedTooMuch(card, event) || this.wasJustDragged()) return false;
    const id = Number(card.dataset.id);
    if (!Number.isFinite(id) || id <= 0) return false;
    const now = Date.now();
    if (this._lastCardOpenId === id && now - Number(this._lastCardOpenAt || 0) < 350) return true;
    this._lastCardOpenId = id;
    this._lastCardOpenAt = now;
    event?.preventDefault?.();
    event?.stopPropagation?.();
    if (window.location.hash !== `#occurrence-${id}`) window.location.hash = `occurrence-${id}`;
    this.openOccurrence(id);
    return true;
  },

  openFromHash() {
    const match = String(window.location.hash || "").match(/^#occurrence-(\d+)$/);
    if (!match) return false;
    const id = Number(match[1]);
    if (!Number.isFinite(id) || id <= 0) return false;
    this.openOccurrence(id);
    return true;
  },

  showWorkspaceSkeleton(id) {
    const board = document.getElementById("boardView");
    const workspace = document.getElementById("incidentWorkspace");
    if (board) board.hidden = true;
    if (workspace) workspace.hidden = false;
    const title = document.getElementById("detailTitle");
    const subtitle = document.getElementById("detailSubtitle");
    const timeline = document.getElementById("detailTimeline");
    if (title) title.textContent = `Ocorrência #${id}`;
    if (subtitle) subtitle.textContent = "Carregando ocorrência...";
    if (timeline) timeline.innerHTML = `<div class="empty">Carregando ocorrência...</div>`;
  },

  async openOccurrence(id) {
    const occurrenceId = Number(id);
    if (!Number.isFinite(occurrenceId) || occurrenceId <= 0) {
      VigUI.toast("Ocorrência inválida");
      return;
    }

    if (this.isOpeningOccurrence && Number(this.currentOccurrenceId) === occurrenceId) return;
    this.isOpeningOccurrence = true;

    try {
      this.currentOccurrenceId = occurrenceId;
      this.showWorkspaceSkeleton(occurrenceId);
      const data = await VigAPI.occurrence(occurrenceId);

      try {
        await VigAPI.watchOccurrence(occurrenceId);
      } catch (watchError) {
        console.warn("Não foi possível marcar ocorrência como assistida:", watchError);
      }

      this.renderWorkspace(data);
    } catch (error) {
      console.error("Erro ao abrir ocorrência:", error);
      VigUI.toast(error?.message || "Não foi possível abrir a ocorrência");
      this.currentOccurrenceId = null;
      const workspace = document.getElementById("incidentWorkspace");
      const board = document.getElementById("boardView");
      if (workspace) workspace.hidden = true;
      if (board) board.hidden = false;
    } finally {
      this.isOpeningOccurrence = false;
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

  setTimelineFilter(filter) {
    this.timelineFilter = filter || "all";
    document.querySelectorAll(".timeline-filter").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.filter === this.timelineFilter);
    });
    if (this.detailData) this.renderTimeline(this.detailData);
  },

  timelineCategory(item) {
    const type = String(item.type || "").toUpperCase();
    if (["EVENT", "RESTORE", "AUTO_FINISH", "ACCOUNT_EVENT", "MANUAL_EVENT", "ARM_STATE"].includes(type)) return "events";
    if (["LOG", "WATCH", "UNWATCH", "COMMAND_REQUEST", "NOTE"].includes(type)) return "logs";
    if (["STATUS"].includes(type)) return "occurrence";
    return "events";
  },

  filteredTimeline(data) {
    const occurrenceItems = (data.timeline || []).map(x => ({ ...x, _source: "occurrence" }));
    const accountItems = (data.account_events || []).map(x => ({ ...x, _source: "account" }));
    let items = [];

    if (this.timelineFilter === "all") {
      items = [...occurrenceItems, ...accountItems];
    } else if (this.timelineFilter === "auxiliary") {
      items = accountItems;
    } else if (this.timelineFilter === "occurrence") {
      items = occurrenceItems.filter(t => this.timelineCategory(t) === "occurrence" || t._source === "occurrence");
    } else {
      items = [...occurrenceItems, ...accountItems].filter(t => this.timelineCategory(t) === this.timelineFilter);
    }

    items.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    return items;
  },

  renderTimeline(data) {
    const items = this.filteredTimeline(data);
    const box = document.getElementById("detailTimeline");
    if (!box) return;
    if (!items.length) {
      box.innerHTML = `<div class="empty">Nenhum registro neste filtro</div>`;
      return;
    }

    let lastSource = null;
    const html = [];
    for (const item of items) {
      if (item._source !== lastSource && item._source === "account") {
        html.push(`<div class="timeline-divider">Histórico da conta</div>`);
      }
      lastSource = item._source;
      html.push(this.timelineHtml(item));
    }
    box.innerHTML = html.join("");
  },

  renderWorkspace(data) {
    this.detailData = data;
    const occ = data.occurrence || {};
    const account = data.account || {};
    const client = data.client || {};
    const statusKey = this.queueFocus || this.statusKey(occ.status);
    const queue = this.boardColumns[statusKey] || [];

    document.getElementById("detailQueueTitle").textContent = occ.status_label || "Ocorrência";
    document.getElementById("detailQueueCount").textContent = queue.length;
    document.getElementById("detailQueueList").innerHTML = queue.length
      ? queue.map(card => this.cardHtml(card)).join("")
      : `<div class="empty">Nenhuma ocorrência</div>`;

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

    document.getElementById("detailTemporaryNotes").innerHTML = this.temporaryNotesHtml(data);
    document.getElementById("detailMediaPreview").innerHTML = this.mediaPreviewHtml(data);
    document.getElementById("detailServiceOrders").innerHTML = this.serviceOrdersHtml(data);

    document.getElementById("detailContacts").innerHTML = (data.contacts || []).map(c => `
      <div class="detail-row">
        <div class="detail-row-icon">☎</div>
        <div class="detail-row-main">
          <strong>${VigUI.escape(c.name)}</strong>
          <span>${VigUI.escape(c.password_hint || c.function || "Contato")}</span>
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

    this.renderTimeline(data);

    document.querySelectorAll(".command-action").forEach(btn => {
      btn.addEventListener("click", () => this.requestCommand(btn.dataset.command, btn.dataset.partition));
    });
    document.querySelectorAll(".manual-event-btn").forEach(btn => {
      btn.addEventListener("click", () => this.createManualEvent(btn.dataset.eventCode));
    });
  },

  temporaryNotesHtml(data) {
    const notes = (data.timeline || []).filter(t => String(t.type || "").toUpperCase() === "NOTE").slice(0, 2);
    if (!notes.length) {
      return `<div class="temporary-empty"><span>Anotação:</span><span>Providência:</span></div>`;
    }
    return notes.map(n => `
      <div class="temporary-note-item">
        <strong>${VigUI.escape(n.title || "Anotação")}</strong>
        ${n.description ? `<span>${VigUI.escape(n.description)}</span>` : ""}
      </div>
    `).join("");
  },

  mediaPreviewHtml(data) {
    const media = (data.timeline || []).filter(t => String(t.type || "").toUpperCase() === "MEDIA").slice(0, 4);
    if (!media.length) {
      return `<button class="media-empty-button" id="btnOpenMedia3" type="button">Nenhuma mídia vinculada · clicar para anexar</button>`;
    }
    return media.map(m => `<div class="media-thumb-placeholder">▧<span>${VigUI.escape(m.title || "Mídia")}</span></div>`).join("");
  },

  serviceOrdersHtml(data) {
    const orders = (data.timeline || []).filter(t => String(t.type || "").toUpperCase() === "SERVICE_ORDER").slice(0, 3);
    if (!orders.length) {
      return `<div class="detail-row slim"><div class="detail-row-icon">▧</div><div class="detail-row-main"><strong>Sem ordem de serviço aberta</strong><span>Use log ou finalize a ocorrência para registrar providência.</span></div></div>`;
    }
    return orders.map(o => `
      <div class="detail-row slim"><div class="detail-row-icon">▧</div><div class="detail-row-main"><strong>${VigUI.escape(o.title)}</strong><span>${VigUI.escape(o.description || "")}</span></div></div>
    `).join("");
  },

  timelineHtml(t) {
    const type = String(t.type || "").toUpperCase();
    const iconMap = {
      STATUS: "↔",
      RESTORE: "✓",
      AUTO_FINISH: "✓",
      LOG: "♟",
      WATCH: "♟",
      UNWATCH: "♟",
      COMMAND_REQUEST: "↯",
      NOTE: "✎",
      MEDIA: "▧",
      MANUAL_EVENT: "#",
      ARM_STATE: "⌂",
      ACCOUNT_EVENT: "✓",
      EVENT: "!",
    };
    const cls = `type-${type.toLowerCase()}`;
    return `
      <div class="seg-timeline-item ${cls}" data-timeline-type="${VigUI.escape(type)}">
        <div class="seg-time-icon">${iconMap[type] || "!"}</div>
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

  async createManualEvent(code) {
    if (!this.currentOccurrenceId || !code) return;
    const note = window.prompt(`Observação para evento manual ${code}:`, "");
    if (note === null) return;
    await VigAPI.addManualEvent(this.currentOccurrenceId, code, note);
    VigUI.toast(`Evento manual ${code} registrado`);
    const data = await VigAPI.occurrence(this.currentOccurrenceId);
    this.renderWorkspace(data);
  },

  async saveLog() {
    if (!this.currentOccurrenceId) return;
    const text = document.getElementById("logText")?.value || "";
    if (!text.trim()) {
      VigUI.toast("Digite o log antes de salvar");
      return;
    }
    await VigAPI.addLog(this.currentOccurrenceId, text.trim());
    document.getElementById("logText").value = "";
    document.getElementById("logComposer").hidden = true;
    VigUI.toast("Log salvo");
    const data = await VigAPI.occurrence(this.currentOccurrenceId);
    this.renderWorkspace(data);
  },

  async saveTempNote() {
    if (!this.currentOccurrenceId) return;
    const note = document.getElementById("tempNoteText")?.value || "";
    const providence = document.getElementById("tempProvidenceText")?.value || "";
    if (!note.trim() && !providence.trim()) {
      VigUI.toast("Digite anotação ou providência");
      return;
    }
    await VigAPI.addTemporaryNote(this.currentOccurrenceId, note.trim(), providence.trim());
    document.getElementById("tempNoteText").value = "";
    document.getElementById("tempProvidenceText").value = "";
    document.getElementById("tempNoteComposer").hidden = true;
    VigUI.toast("Anotação salva");
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

  async moveOccurrence(id, status) {
    const occurrenceId = Number(id);
    if (!Number.isFinite(occurrenceId) || !status) return;
    try {
      await VigAPI.setStatus(occurrenceId, status, `Movido por arrastar para ${status}`);
      VigUI.toast("Ocorrência movida");
      await this.refresh();
    } catch (error) {
      console.error("Erro ao mover ocorrência", error);
      VigUI.toast(error?.message || "Não foi possível mover ocorrência");
    }
  },

  toggleLogComposer() {
    const el = document.getElementById("logComposer");
    if (!el) return;
    el.hidden = !el.hidden;
    if (!el.hidden) document.getElementById("logText")?.focus();
  },

  toggleTempNoteComposer() {
    const el = document.getElementById("tempNoteComposer");
    if (!el) return;
    el.hidden = !el.hidden;
    if (!el.hidden) document.getElementById("tempNoteText")?.focus();
  },

  openMediaDrawer() {
    const drawer = document.getElementById("mediaDrawer");
    if (drawer) drawer.hidden = false;
  },

  closeMediaDrawer() {
    const drawer = document.getElementById("mediaDrawer");
    if (drawer) drawer.hidden = true;
  },

  handleMediaFiles(files) {
    const list = Array.from(files || []).slice(0, 5);
    this.mediaFiles = list;
    const box = document.getElementById("mediaDrawerList");
    if (!box) return;
    if (!list.length) {
      box.innerHTML = `<div class="empty-media">Nenhuma mídia vinculada.</div>`;
      return;
    }
    box.innerHTML = list.map(file => `<div class="media-file-row"><span>▧</span><strong>${VigUI.escape(file.name)}</strong><small>${Math.round(file.size / 1024)} KB</small></div>`).join("");
  },

  async saveMedia() {
    if (!this.currentOccurrenceId) return;
    if (!this.mediaFiles.length) {
      VigUI.toast("Selecione pelo menos uma mídia");
      return;
    }
    const names = this.mediaFiles.map(f => f.name).join(", ");
    await VigAPI.addMediaNote(this.currentOccurrenceId, names);
    this.mediaFiles = [];
    this.closeMediaDrawer();
    VigUI.toast("Mídia registrada na ocorrência");
    const data = await VigAPI.occurrence(this.currentOccurrenceId);
    this.renderWorkspace(data);
  },

  bindDragAndDrop() {
    if (this._dragDropBound) return;
    this._dragDropBound = true;

    document.addEventListener("dragstart", event => {
      const card = event.target.closest(".occ-card");
      if (!card) return;
      event.dataTransfer.setData("text/plain", card.dataset.id || "");
      event.dataTransfer.effectAllowed = "move";
      this._draggingNow = true;
      this._lastDragAt = Date.now();
      card.classList.add("dragging");
    }, true);

    document.addEventListener("dragend", event => {
      const card = event.target.closest(".occ-card");
      if (card) card.classList.remove("dragging");
      this._lastDragAt = Date.now();
      window.setTimeout(() => { this._draggingNow = false; }, 180);
      document.querySelectorAll(".drop-zone.is-over").forEach(el => el.classList.remove("is-over"));
    }, true);

    document.addEventListener("dragover", event => {
      const zone = event.target.closest(".drop-zone");
      if (!zone) return;
      event.preventDefault();
      zone.classList.add("is-over");
      event.dataTransfer.dropEffect = "move";
    }, true);

    document.addEventListener("dragleave", event => {
      const zone = event.target.closest(".drop-zone");
      if (!zone) return;
      if (!zone.contains(event.relatedTarget)) zone.classList.remove("is-over");
    }, true);

    document.addEventListener("drop", event => {
      const zone = event.target.closest(".drop-zone");
      if (!zone) return;
      event.preventDefault();
      zone.classList.remove("is-over");
      const id = event.dataTransfer.getData("text/plain");
      const status = zone.dataset.status;
      this._lastDragAt = Date.now();
      window.setTimeout(() => { this._draggingNow = false; }, 180);
      this.moveOccurrence(id, status);
    }, true);
  },

  bindEvents() {
    document.getElementById("btnRefresh")?.addEventListener("click", () => this.refresh());
    document.getElementById("queueBackBtn")?.addEventListener("click", () => this.backToBoard());
    document.getElementById("btnBackBoard2")?.addEventListener("click", () => this.backToBoard());
    document.getElementById("btnCloseModal")?.addEventListener("click", () => this.closeModal());
    document.getElementById("btnOpenLog")?.addEventListener("click", () => this.toggleLogComposer());
    document.getElementById("btnSaveLog")?.addEventListener("click", () => this.saveLog());
    document.getElementById("btnOpenTempNote")?.addEventListener("click", () => this.toggleTempNoteComposer());
    document.getElementById("btnEditTempNote")?.addEventListener("click", () => this.toggleTempNoteComposer());
    document.getElementById("btnSaveTempNote")?.addEventListener("click", () => this.saveTempNote());
    document.getElementById("btnOpenMedia")?.addEventListener("click", () => this.openMediaDrawer());
    document.getElementById("btnOpenMedia2")?.addEventListener("click", () => this.openMediaDrawer());
    document.getElementById("btnCloseMedia")?.addEventListener("click", () => this.closeMediaDrawer());
    document.getElementById("btnCancelMedia")?.addEventListener("click", () => this.closeMediaDrawer());
    document.getElementById("btnSaveMedia")?.addEventListener("click", () => this.saveMedia());
    document.getElementById("mediaFileInput")?.addEventListener("change", event => this.handleMediaFiles(event.target.files));

    document.querySelectorAll(".status-action").forEach(btn => {
      btn.addEventListener("click", () => this.changeStatus(btn.dataset.status));
    });
    document.querySelectorAll(".timeline-filter").forEach(btn => {
      btn.addEventListener("click", () => this.setTimelineFilter(btn.dataset.filter));
    });
    document.querySelectorAll(".queue-filter").forEach(btn => {
      btn.addEventListener("click", () => {
        this.queueFocus = btn.dataset.queue;
        document.querySelectorAll(".queue-filter").forEach(b => b.classList.toggle("active", b === btn));
        if (this.detailData) this.renderWorkspace(this.detailData);
      });
    });

    if (!this._delegatedCardClickBound) {
      this._delegatedCardClickBound = true;
      const rememberPointer = event => {
        const card = event.target.closest?.(".occ-card");
        if (!card) return;
        card.dataset.downX = String(event.clientX || 0);
        card.dataset.downY = String(event.clientY || 0);
      };
      const openFromEvent = event => {
        const card = event.target.closest?.(".occ-card");
        if (!card) return;
        const board = document.getElementById("boardView");
        const workspace = document.getElementById("incidentWorkspace");
        const isInBoard = board && board.contains(card);
        const isInWorkspaceQueue = workspace && workspace.contains(card);
        if (!isInBoard && !isInWorkspaceQueue) return;
        this.openCardFromElement(card, event);
      };
      document.addEventListener("pointerdown", rememberPointer, true);
      document.addEventListener("pointerup", openFromEvent, true);
      document.addEventListener("click", openFromEvent, true);
      document.addEventListener("dblclick", openFromEvent, true);
      document.addEventListener("keydown", event => {
        if (event.key !== "Enter" && event.key !== " ") return;
        const card = event.target.closest?.(".occ-card");
        if (!card) return;
        this.openCardFromElement(card, event);
      }, true);
      window.addEventListener("hashchange", () => this.openFromHash());
      window.setTimeout(() => this.openFromHash(), 80);
    }

    document.addEventListener("click", event => {
      const btn = event.target.closest("#btnOpenMedia3");
      if (btn) this.openMediaDrawer();
    });

    this.bindDragAndDrop();
  },
};
