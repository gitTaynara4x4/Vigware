window.VigMonitoring = {
  currentOccurrenceId: null,
  boardColumns: {},
  detailData: null,
  timelineFilter: "all",
  queueFocus: null,
  isOpeningOccurrence: false,
  mediaFiles: [],
  currentView: "board",
  bulkSelected: new Set(),
  bulkRows: [],
  bulkOptionsLoaded: false,
  bulkMaxSelection: 50,
  _routeToken: 0,

  routePath() {
    const hash = decodeURIComponent(String(window.location.hash || ""));
    const legacyOccurrence = hash.match(/^#occurrence-(\d+)$/);
    if (legacyOccurrence) return `/ocorrencias/${legacyOccurrence[1]}`;
    if (hash.startsWith("#/")) return hash.slice(1);
    return "/monitoramento";
  },

  navigate(path, { replace = false } = {}) {
    const normalized = String(path || "/monitoramento").startsWith("/")
      ? String(path || "/monitoramento")
      : `/${path}`;
    const target = `#${normalized}`;

    if (window.location.hash === target) {
      return this.handleRoute();
    }

    if (replace) {
      window.history.replaceState(null, "", target);
      return this.handleRoute();
    }

    window.location.hash = normalized;
    return Promise.resolve();
  },

  async handleRoute() {
    const token = ++this._routeToken;
    const path = this.routePath();
    const occurrenceMatch = path.match(/^\/ocorrencias\/(\d+)$/);

    if (occurrenceMatch) {
      const id = Number(occurrenceMatch[1]);
      await this.openOccurrence(id);
      return token === this._routeToken;
    }

    if (path === "/fechamento-multiplo") {
      await this.openBulkClose();
      return token === this._routeToken;
    }

    await this.showBoardRoute();
    return token === this._routeToken;
  },

  showView(view) {
    const ids = {
      board: "boardView",
      occurrence: "incidentWorkspace",
      bulk: "bulkCloseView",
    };
    this.currentView = view;

    Object.entries(ids).forEach(([name, id]) => {
      const element = document.getElementById(id);
      if (!element) return;
      const visible = name === view;
      element.hidden = !visible;
      element.toggleAttribute("hidden", !visible);
      element.style.removeProperty("display");
    });

    this.syncSidebar(view);
    this.updateTopbar(view);
  },

  syncSidebar(view = this.currentView) {
    const route = view === "bulk" ? "/fechamento-multiplo" : "/monitoramento";
    document.querySelectorAll(".nav-item[data-route]").forEach(button => {
      button.classList.toggle("active", button.dataset.route === route);
      button.setAttribute("aria-current", button.dataset.route === route ? "page" : "false");
    });
  },

  updateTopbar(view = this.currentView) {
    const title = document.querySelector(".topbar-title");
    const subtitle = document.querySelector(".topbar-subtitle");
    const refreshButton = document.getElementById("btnRefresh");

    if (view === "bulk") {
      if (title) title.textContent = "Fechar múltiplos eventos";
      if (subtitle) subtitle.innerHTML = "Seleção e encerramento operacional em lote";
      if (refreshButton) refreshButton.textContent = "Atualizar busca";
      return;
    }

    if (view === "occurrence") {
      if (title) title.textContent = "Atendimento de ocorrência";
      if (subtitle) subtitle.innerHTML = '<span id="wsStatus">Tempo real online</span><span class="separator">•</span><span>Ocorrência em atendimento</span>';
      if (refreshButton) refreshButton.textContent = "Atualizar";
      return;
    }

    if (title) title.textContent = "Vigware Monitor";
    if (subtitle) subtitle.innerHTML = '<span id="wsStatus">Tempo real online</span><span class="separator">•</span><span>Última atualização <strong id="metricUpdated">--:--:--</strong></span>';
    if (refreshButton) refreshButton.textContent = "Atualizar";
  },

  async releaseCurrentOccurrence() {
    const occurrenceId = Number(this.currentOccurrenceId);
    this.currentOccurrenceId = null;
    this.detailData = null;
    if (!Number.isFinite(occurrenceId) || occurrenceId <= 0) return;
    try {
      await VigAPI.unwatchOccurrence(occurrenceId);
    } catch (error) {
      console.warn("Não foi possível liberar a ocorrência", error);
    }
  },

  async showBoardRoute() {
    if (this.currentView === "occurrence" || this.currentOccurrenceId) {
      await this.releaseCurrentOccurrence();
    }
    this.showView("board");
    await this.refresh();
  },

  async refreshCurrentView() {
    if (this.currentView === "bulk") {
      return this.searchBulkClose();
    }
    if (this.currentView === "occurrence" && this.currentOccurrenceId) {
      const data = await VigAPI.occurrence(this.currentOccurrenceId);
      this.renderWorkspace(data);
      return;
    }
    return this.refresh();
  },

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
      <a class="occ-card ${priority}${selected}" href="#/ocorrencias/${card.id}" draggable="false" data-id="${card.id}" data-status="${VigUI.escape(card.status || "")}" aria-label="Abrir ocorrência ${card.id}">
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

  isCardInMonitoring(card) {
    if (!card) return false;
    const board = document.getElementById("boardView");
    const workspace = document.getElementById("incidentWorkspace");
    return Boolean((board && board.contains(card)) || (workspace && workspace.contains(card)));
  },

  openCardFromElement(card, event) {
    if (!this.isCardInMonitoring(card)) return false;

    const id = Number(card.dataset.id);
    if (!Number.isFinite(id) || id <= 0) return false;

    // Depois de um arraste real o navegador ainda pode disparar um click.
    // Esse bloqueio existe somente para esse click residual, não para cliques normais.
    if (Date.now() < Number(this._suppressCardClickUntil || 0)) {
      event?.preventDefault?.();
      event?.stopPropagation?.();
      return false;
    }

    event?.preventDefault?.();
    event?.stopPropagation?.();

    this.navigate(`/ocorrencias/${id}`);
    return true;
  },

  openFromHash() {
    return this.handleRoute();
  },

  showWorkspaceSkeleton(id) {
    this.showView("occurrence");

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
    if (Number(this.currentOccurrenceId) === occurrenceId && this.detailData && this.currentView === "occurrence") {
      this.showView("occurrence");
      return;
    }

    const previousOccurrenceId = Number(this.currentOccurrenceId);
    if (Number.isFinite(previousOccurrenceId) && previousOccurrenceId > 0 && previousOccurrenceId !== occurrenceId) {
      try { await VigAPI.unwatchOccurrence(previousOccurrenceId); } catch {}
    }

    this.isOpeningOccurrence = true;

    try {
      this.currentOccurrenceId = occurrenceId;
      this.showWorkspaceSkeleton(occurrenceId);
      const expectedPath = `/ocorrencias/${occurrenceId}`;
      const data = await VigAPI.occurrence(occurrenceId);

      if (this.routePath() !== expectedPath) return;

      try {
        await VigAPI.watchOccurrence(occurrenceId);
      } catch (watchError) {
        console.warn("Não foi possível marcar ocorrência como assistida:", watchError);
      }

      if (this.routePath() !== expectedPath) {
        try { await VigAPI.unwatchOccurrence(occurrenceId); } catch {}
        return;
      }

      this.renderWorkspace(data);
    } catch (error) {
      console.error("Erro ao abrir ocorrência:", error);
      VigUI.toast(error?.message || "Não foi possível abrir a ocorrência");

      // Não volta silenciosamente para o quadro. Se a API/renderização falhar,
      // deixa a tela de atendimento aberta mostrando o erro para diagnóstico.
      const title = document.getElementById("detailTitle");
      const subtitle = document.getElementById("detailSubtitle");
      const timeline = document.getElementById("detailTimeline");
      if (title) title.textContent = `Ocorrência #${occurrenceId}`;
      if (subtitle) subtitle.textContent = "Erro ao carregar ocorrência";
      if (timeline) timeline.innerHTML = `<div class="empty error-box">${VigUI.escape(error?.message || "Não foi possível abrir a ocorrência")}</div>`;
    } finally {
      this.isOpeningOccurrence = false;
    }
  },

  async backToBoard() {
    await this.releaseCurrentOccurrence();
    return this.navigate("/monitoramento");
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
    // Mantém a ocorrência como tela ativa dentro do shell.
    this.showView("occurrence");
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

  async openBulkClose() {
    if (this.currentOccurrenceId) {
      await this.releaseCurrentOccurrence();
    }
    this.showView("bulk");
    await this.loadBulkCloseOptions();
    this.updateBulkSelectionState();
  },

  async loadBulkCloseOptions() {
    if (this.bulkOptionsLoaded) return;
    const form = document.getElementById("bulkCloseFilterForm");
    if (!form) return;

    try {
      const options = await VigAPI.bulkCloseOptions();
      this.bulkMaxSelection = Number(options.max_selection || 50);
      this.fillBulkSelect("bulkFilterEventType", options.event_types || [], "value", "label");
      this.fillBulkSelect("bulkFilterPriority", options.priorities || [], "value", "label");
      this.fillBulkSelect("bulkFilterCompany", options.companies || [], "id", "name");
      this.fillBulkSelect("bulkFilterCountry", options.countries || [], "value", "label");
      this.bulkOptionsLoaded = true;
    } catch (error) {
      console.error("Erro ao carregar filtros de fechamento múltiplo", error);
      VigUI.toast(error?.message || "Não foi possível carregar os filtros");
    }
  },

  fillBulkSelect(id, items, valueKey, labelKey) {
    const select = document.getElementById(id);
    if (!select) return;
    const currentValue = select.value;
    select.innerHTML = [
      '<option value="">Selecione...</option>',
      ...items.map(item => `<option value="${VigUI.escape(item[valueKey])}">${VigUI.escape(item[labelKey])}</option>`),
    ].join("");
    if ([...select.options].some(option => option.value === currentValue)) {
      select.value = currentValue;
    }
  },

  bulkFilters() {
    return {
      query: document.getElementById("bulkFilterQuery")?.value || "",
      event_type: document.getElementById("bulkFilterEventType")?.value || "",
      priority: document.getElementById("bulkFilterPriority")?.value || "",
      company_id: document.getElementById("bulkFilterCompany")?.value || "",
      country: document.getElementById("bulkFilterCountry")?.value || "",
      state: document.getElementById("bulkFilterState")?.value || "",
      city: document.getElementById("bulkFilterCity")?.value || "",
      neighborhood: document.getElementById("bulkFilterNeighborhood")?.value || "",
    };
  },

  clearBulkFilters() {
    document.getElementById("bulkCloseFilterForm")?.reset();
    const results = document.getElementById("bulkCloseResults");
    if (results) {
      results.innerHTML = '<tr class="bulk-empty-row"><td colspan="8">Informe os filtros desejados e clique em procurar</td></tr>';
    }
    this.bulkRows = [];
    this.bulkSelected.clear();
    const summary = document.getElementById("bulkResultSummary");
    if (summary) summary.textContent = "Informe os filtros desejados e clique em procurar";
    const shown = document.getElementById("bulkShownCount");
    if (shown) shown.textContent = "Exibindo os últimos 0 eventos abertos";
    this.updateBulkSelectionState();
  },

  async searchBulkClose() {
    const button = document.getElementById("btnBulkSearch");
    const results = document.getElementById("bulkCloseResults");
    if (!results) return;

    if (button) {
      button.disabled = true;
      button.classList.add("is-loading");
    }
    results.innerHTML = '<tr class="bulk-empty-row"><td colspan="8">Procurando eventos abertos...</td></tr>';

    try {
      const data = await VigAPI.searchBulkOccurrences(this.bulkFilters());
      this.bulkMaxSelection = Number(data.max_selection || this.bulkMaxSelection || 50);
      this.bulkRows = data.items || [];
      const validIds = new Set(this.bulkRows.filter(row => row.selectable).map(row => Number(row.id)));
      this.bulkSelected = new Set([...this.bulkSelected].filter(id => validIds.has(Number(id))));
      this.renderBulkResults();
    } catch (error) {
      console.error("Erro na busca de fechamento múltiplo", error);
      results.innerHTML = `<tr class="bulk-empty-row is-error"><td colspan="8">${VigUI.escape(error?.message || "Não foi possível procurar os eventos")}</td></tr>`;
      VigUI.toast(error?.message || "Não foi possível procurar os eventos");
    } finally {
      if (button) {
        button.disabled = false;
        button.classList.remove("is-loading");
      }
      this.updateBulkSelectionState();
    }
  },

  renderBulkResults() {
    const results = document.getElementById("bulkCloseResults");
    const summary = document.getElementById("bulkResultSummary");
    const shown = document.getElementById("bulkShownCount");
    if (!results) return;

    if (!this.bulkRows.length) {
      results.innerHTML = '<tr class="bulk-empty-row"><td colspan="8">Nenhum evento aberto encontrado com os filtros informados</td></tr>';
    } else {
      results.innerHTML = this.bulkRows.map(row => this.bulkResultRowHtml(row)).join("");
    }

    const count = this.bulkRows.length;
    const lockedCount = this.bulkRows.filter(row => !row.selectable).length;
    if (summary) {
      summary.textContent = lockedCount
        ? `${count} evento${count === 1 ? "" : "s"} encontrado${count === 1 ? "" : "s"} · ${lockedCount} bloqueado${lockedCount === 1 ? "" : "s"}`
        : `${count} evento${count === 1 ? "" : "s"} encontrado${count === 1 ? "" : "s"}`;
    }
    if (shown) shown.textContent = `Exibindo os últimos ${count} eventos abertos`;
    this.updateBulkSelectionState();
  },

  bulkResultRowHtml(row) {
    const id = Number(row.id);
    const checked = this.bulkSelected.has(id) ? "checked" : "";
    const disabled = row.selectable ? "" : "disabled";
    const lockedClass = row.selectable ? "" : " is-locked";
    const priorityLabels = { high: "Alta", medium: "Média", low: "Baixa" };
    const priority = String(row.priority || "medium").toLowerCase();
    const lockLabel = row.locked_by
      ? `<span class="bulk-lock-label" title="Em atendimento por ${VigUI.escape(row.locked_by)}">🔒 ${VigUI.escape(row.locked_by)}</span>`
      : "";

    return `
      <tr class="bulk-result-row${lockedClass}" data-id="${id}">
        <td class="bulk-check-col"><input class="bulk-row-check" type="checkbox" value="${id}" ${checked} ${disabled} aria-label="Selecionar evento ${id}"></td>
        <td><strong>${VigUI.escape(row.event_code || "-")}</strong><span>${VigUI.escape(row.description || "Evento")}</span></td>
        <td><strong>${VigUI.escape(row.client_name || "Conta não cadastrada")}</strong><span>${VigUI.escape(row.account_code || "-")} · Partição ${VigUI.escape(row.partition_number || "001")}</span></td>
        <td>${VigUI.escape(row.event_type_label || row.event_type || "Outro")}</td>
        <td><span class="bulk-priority priority-${VigUI.escape(priority)}">${VigUI.escape(priorityLabels[priority] || priority)}</span></td>
        <td><span class="bulk-status">${VigUI.escape(row.status_label || row.status || "-")}</span>${lockLabel}</td>
        <td>${VigUI.escape(row.company_name || "-")}</td>
        <td class="bulk-location" title="${VigUI.escape(row.address || "")}">${VigUI.escape(row.address || "Endereço não cadastrado")}</td>
      </tr>
    `;
  },

  toggleBulkSelection(id, checked, checkbox = null) {
    const occurrenceId = Number(id);
    const row = this.bulkRows.find(item => Number(item.id) === occurrenceId);
    if (!row?.selectable) return;

    if (checked) {
      if (!this.bulkSelected.has(occurrenceId) && this.bulkSelected.size >= this.bulkMaxSelection) {
        if (checkbox) checkbox.checked = false;
        VigUI.toast(`Permitida a seleção máxima de ${this.bulkMaxSelection} eventos`);
        return;
      }
      this.bulkSelected.add(occurrenceId);
    } else {
      this.bulkSelected.delete(occurrenceId);
    }
    this.updateBulkSelectionState();
  },

  toggleBulkSelectAll(checked) {
    if (!checked) {
      this.bulkSelected.clear();
    } else {
      for (const row of this.bulkRows) {
        if (!row.selectable) continue;
        if (this.bulkSelected.size >= this.bulkMaxSelection) break;
        this.bulkSelected.add(Number(row.id));
      }
    }

    document.querySelectorAll(".bulk-row-check").forEach(input => {
      input.checked = this.bulkSelected.has(Number(input.value));
    });
    this.updateBulkSelectionState();
  },

  updateBulkSelectionState() {
    const selectedCount = this.bulkSelected.size;
    const count = document.getElementById("bulkSelectedCount");
    const closeButton = document.getElementById("btnBulkCloseSelected");
    const selectAll = document.getElementById("bulkSelectAll");
    const log = document.getElementById("bulkCloseLog")?.value.trim() || "";
    const selectableIds = this.bulkRows.filter(row => row.selectable).map(row => Number(row.id));
    const selectedVisible = selectableIds.filter(id => this.bulkSelected.has(id)).length;

    if (count) count.textContent = `${selectedCount} evento${selectedCount === 1 ? "" : "s"} selecionado${selectedCount === 1 ? "" : "s"}`;
    if (closeButton) closeButton.disabled = selectedCount === 0 || !log || closeButton.dataset.busy === "true";
    if (selectAll) {
      selectAll.disabled = selectableIds.length === 0;
      selectAll.checked = selectableIds.length > 0 && selectedVisible === selectableIds.length;
      selectAll.indeterminate = selectedVisible > 0 && selectedVisible < selectableIds.length;
    }
  },

  async closeBulkSelected() {
    const ids = [...this.bulkSelected].map(Number).filter(Number.isFinite);
    const logField = document.getElementById("bulkCloseLog");
    const log = logField?.value.trim() || "";
    const button = document.getElementById("btnBulkCloseSelected");

    if (!ids.length) {
      VigUI.toast("Selecione pelo menos um evento");
      return;
    }
    if (!log) {
      VigUI.toast("Digite o log antes de fechar os eventos");
      logField?.focus();
      return;
    }

    const confirmed = window.confirm(`Fechar ${ids.length} evento${ids.length === 1 ? "" : "s"} e registrar o mesmo log em todos?`);
    if (!confirmed) return;

    try {
      if (button) {
        button.dataset.busy = "true";
        button.disabled = true;
        button.textContent = "Fechando eventos...";
      }
      const result = await VigAPI.closeBulkOccurrences(ids, log);
      VigUI.toast(`${result.closed_count} evento${result.closed_count === 1 ? "" : "s"} fechado${result.closed_count === 1 ? "" : "s"}`);
      this.bulkSelected.clear();
      if (logField) logField.value = "";
      await Promise.all([this.searchBulkClose(), this.refresh()]);
    } catch (error) {
      console.error("Erro ao fechar eventos em lote", error);
      VigUI.toast(error?.message || "Não foi possível fechar os eventos selecionados");
    } finally {
      if (button) {
        button.dataset.busy = "false";
        button.textContent = "Fechar eventos selecionados";
      }
      this.updateBulkSelectionState();
    }
  },

  bindDragAndDrop() {
    if (this._dragDropBound) return;
    this._dragDropBound = true;

    const DRAG_THRESHOLD_PX = 10;

    const clearDropHighlight = () => {
      document.querySelectorAll(".drop-zone.is-over").forEach(el => el.classList.remove("is-over"));
    };

    const finishPointerDrag = (event, shouldDrop) => {
      const state = this._pointerDragState;
      if (!state || (event.pointerId !== undefined && state.pointerId !== event.pointerId)) return;

      const wasDragging = Boolean(state.dragging);
      const dropZone = wasDragging && shouldDrop
        ? document.elementFromPoint(event.clientX, event.clientY)?.closest?.(".drop-zone")
        : null;

      state.card.classList.remove("dragging");
      clearDropHighlight();
      this._pointerDragState = null;

      try {
        if (state.card.hasPointerCapture?.(state.pointerId)) {
          state.card.releasePointerCapture(state.pointerId);
        }
      } catch {}

      if (!wasDragging) return;

      // Evita somente o click sintético que vem logo após soltar um card arrastado.
      this._suppressCardClickUntil = Date.now() + 350;
      event.preventDefault();
      event.stopPropagation();

      const status = dropZone?.dataset?.status;
      if (status && status !== state.card.dataset.status) {
        this.moveOccurrence(state.id, status);
      }
    };

    document.addEventListener("pointerdown", event => {
      if (event.button !== undefined && event.button !== 0) return;
      const card = event.target.closest?.(".occ-card");
      if (!this.isCardInMonitoring(card)) return;

      this._pointerDragState = {
        card,
        id: Number(card.dataset.id),
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        dragging: false,
      };
    }, true);

    document.addEventListener("pointermove", event => {
      const state = this._pointerDragState;
      if (!state || state.pointerId !== event.pointerId) return;

      const dx = event.clientX - state.startX;
      const dy = event.clientY - state.startY;
      if (!state.dragging && Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return;

      if (!state.dragging) {
        state.dragging = true;
        state.card.classList.add("dragging");
        try { state.card.setPointerCapture?.(state.pointerId); } catch {}
      }

      event.preventDefault();
      clearDropHighlight();
      const zone = document.elementFromPoint(event.clientX, event.clientY)?.closest?.(".drop-zone");
      if (zone) zone.classList.add("is-over");
    }, true);

    document.addEventListener("pointerup", event => finishPointerDrag(event, true), true);
    document.addEventListener("pointercancel", event => finishPointerDrag(event, false), true);

    // Garante que o navegador não volte a tratar o link inteiro como drag nativo.
    document.addEventListener("dragstart", event => {
      if (event.target.closest?.(".occ-card")) event.preventDefault();
    }, true);
  },

  bindEvents() {
    document.getElementById("btnRefresh")?.addEventListener("click", () => this.refreshCurrentView());
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

    document.getElementById("bulkCloseFilterForm")?.addEventListener("submit", event => {
      event.preventDefault();
      this.searchBulkClose();
    });
    document.getElementById("btnBulkClear")?.addEventListener("click", () => this.clearBulkFilters());
    document.getElementById("btnBulkBack")?.addEventListener("click", () => this.navigate("/monitoramento"));
    document.getElementById("btnBulkCloseSelected")?.addEventListener("click", () => this.closeBulkSelected());
    document.getElementById("bulkCloseLog")?.addEventListener("input", () => this.updateBulkSelectionState());
    document.getElementById("bulkSelectAll")?.addEventListener("change", event => this.toggleBulkSelectAll(event.target.checked));
    document.getElementById("bulkCloseResults")?.addEventListener("change", event => {
      const checkbox = event.target.closest?.(".bulk-row-check");
      if (!checkbox) return;
      this.toggleBulkSelection(checkbox.value, checkbox.checked, checkbox);
    });
    document.getElementById("bulkCloseResults")?.addEventListener("click", event => {
      if (event.target.closest?.("input, button, a")) return;
      const row = event.target.closest?.(".bulk-result-row");
      const checkbox = row?.querySelector?.(".bulk-row-check:not(:disabled)");
      if (!checkbox) return;
      checkbox.checked = !checkbox.checked;
      this.toggleBulkSelection(checkbox.value, checkbox.checked, checkbox);
    });

    document.querySelectorAll(".nav-item[data-route]").forEach(button => {
      button.addEventListener("click", () => {
        if (!button.disabled) this.navigate(button.dataset.route);
      });
    });

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

      document.addEventListener("click", event => {
        const card = event.target.closest?.(".occ-card");
        if (!card) return;
        this.openCardFromElement(card, event);
      }, true);

      // Links já abrem com Enter. O espaço recebe o mesmo comportamento para acessibilidade.
      document.addEventListener("keydown", event => {
        if (event.key !== " ") return;
        const card = event.target.closest?.(".occ-card");
        if (!card) return;
        this.openCardFromElement(card, event);
      }, true);

      window.addEventListener("hashchange", () => this.openFromHash());
    }

    document.addEventListener("click", event => {
      const btn = event.target.closest("#btnOpenMedia3");
      if (btn) this.openMediaDrawer();
    });

    this.bindDragAndDrop();
  },
};
