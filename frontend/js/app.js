window.VigApp = {
  user: null,
  appBooted: false,
  authenticating: false,

  async init() {
    this.cacheLoginElements();
    this.bindLoginEvents();

    try {
      const session = await VigAPI.me();
      await this.openApplication(session.user);
    } catch (error) {
      if (error.status !== 401) console.error("Falha ao verificar sessão:", error);
      this.showLogin();
    }
  },

  cacheLoginElements() {
    this.startupView = document.getElementById("startupView");
    this.loginView = document.getElementById("loginView");
    this.appView = document.getElementById("appView");
    this.loginForm = document.getElementById("loginForm");
    this.loginEmail = document.getElementById("loginEmail");
    this.loginPassword = document.getElementById("loginPassword");
    this.loginError = document.getElementById("loginError");
    this.loginSubmit = document.getElementById("loginSubmit");
    this.togglePassword = document.getElementById("toggleLoginPassword");
  },

  bindLoginEvents() {
    this.loginForm?.addEventListener("submit", (event) => this.handleLogin(event));

    this.togglePassword?.addEventListener("click", () => {
      const showing = this.loginPassword.type === "text";
      this.loginPassword.type = showing ? "password" : "text";
      this.togglePassword.classList.toggle("showing", !showing);
      this.togglePassword.setAttribute("aria-pressed", String(!showing));
      this.togglePassword.setAttribute("aria-label", showing ? "Mostrar senha" : "Ocultar senha");
      this.loginPassword.focus();
    });

    document.getElementById("forgotPasswordBtn")?.addEventListener("click", () => {
      this.setLoginMessage(
        "Solicite a redefinição da senha ao administrador responsável pelo Vigware.",
        "info"
      );
    });

    document.getElementById("loginNewsBtn")?.addEventListener("click", () => {
      this.setLoginMessage("Vigware Cloud: novo monitoramento, rotas internas e fechamento múltiplo.", "info");
    });

    document.getElementById("loginSupportBtn")?.addEventListener("click", () => {
      this.setLoginMessage("O canal de suporte poderá ser configurado nas preferências da empresa.", "info");
    });

    window.addEventListener("vigware:unauthorized", () => this.handleExpiredSession());
  },

  async handleLogin(event) {
    event.preventDefault();
    if (this.authenticating) return;

    const email = this.loginEmail.value.trim();
    const password = this.loginPassword.value;

    if (!email || !password) {
      this.setLoginMessage("Preencha o e-mail e a senha.");
      (!email ? this.loginEmail : this.loginPassword).focus();
      return;
    }

    this.authenticating = true;
    this.setLoginLoading(true);
    this.clearLoginMessage();

    try {
      const result = await VigAPI.login(email, password);
      await this.openApplication(result.user);
    } catch (error) {
      this.setLoginMessage(error.message || "Não foi possível entrar no Vigware.");
      this.loginPassword.select();
    } finally {
      this.authenticating = false;
      this.setLoginLoading(false);
    }
  },

  async openApplication(user) {
    this.user = user;
    this.startupView.hidden = true;
    this.loginView.hidden = true;
    this.appView.hidden = false;
    document.body.classList.remove("auth-loading", "login-mode");
    document.body.classList.add("app-mode");

    if (!this.appBooted) {
      await this.bootApplication();
      this.appBooted = true;
    }

    this.renderCurrentUser();
  },

  async bootApplication() {
    try {
      await VigUI.loadPartial("sidebarMount", "/static/partials/sidebar.html");
      await VigUI.loadPartial("topbarMount", "/static/partials/topbar.html");
      await VigUI.loadPartial("monitoringMount", "/static/partials/monitoring.html?v=timeline-segware-20260711");
      await VigUI.loadPartial("modalMount", "/static/partials/occurrence_modal.html");

      VigMonitoring.bindEvents();
      this.bindApplicationEvents();
      await VigMonitoring.refresh();
      await VigMonitoring.handleRoute();

      VigWS.start(async () => {
        await VigMonitoring.refresh();
        if (VigMonitoring.currentView === "bulk" && VigMonitoring.bulkRows.length) {
          await VigMonitoring.searchBulkClose();
        }
      });
    } catch (error) {
      if (error.status === 401) {
        this.showLogin("Sua sessão expirou. Entre novamente.");
        return;
      }
      console.error(error);
      VigUI.toast(`Erro ao carregar Vigware: ${error.message}`);
      throw error;
    }
  },

  bindApplicationEvents() {
    document.getElementById("btnLogout")?.addEventListener("click", async () => {
      const button = document.getElementById("btnLogout");
      if (button) button.disabled = true;
      try {
        await VigAPI.logout();
      } catch (error) {
        console.warn("Falha ao encerrar sessão no servidor:", error);
      } finally {
        VigWS.stop();
        location.hash = "";
        location.reload();
      }
    });
  },

  renderCurrentUser() {
    const name = this.user?.name || "Operador";
    const roleLabels = {
      admin: "Administrador",
      administrator: "Administrador",
      supervisor: "Supervisor",
      operator: "Operador",
    };
    const initials = name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "OP";

    const nameElement = document.getElementById("currentUserName");
    const roleElement = document.getElementById("currentUserRole");
    const avatarElement = document.getElementById("currentUserAvatar");

    if (nameElement) nameElement.textContent = name;
    if (roleElement) roleElement.textContent = roleLabels[this.user?.role] || this.user?.role || "Operador";
    if (avatarElement) avatarElement.textContent = initials;
  },

  handleExpiredSession() {
    if (document.body.classList.contains("login-mode")) return;
    VigWS.stop();
    this.showLogin("Sua sessão expirou. Entre novamente.");
  },

  showLogin(message = "") {
    VigWS.stop();
    this.startupView.hidden = true;
    this.appView.hidden = true;
    this.loginView.hidden = false;
    document.body.classList.remove("auth-loading", "app-mode");
    document.body.classList.add("login-mode");

    if (message) this.setLoginMessage(message, "info");
    else this.clearLoginMessage();

    requestAnimationFrame(() => this.loginEmail?.focus());
  },

  setLoginLoading(loading) {
    if (!this.loginSubmit) return;
    this.loginSubmit.disabled = loading;
    this.loginSubmit.classList.toggle("loading", loading);
    const label = this.loginSubmit.querySelector("span");
    if (label) label.textContent = loading ? "Entrando..." : "Entrar";
  },

  setLoginMessage(message, kind = "error") {
    if (!this.loginError) return;
    this.loginError.hidden = false;
    this.loginError.textContent = message;
    this.loginError.classList.toggle("is-info", kind === "info");
  },

  clearLoginMessage() {
    if (!this.loginError) return;
    this.loginError.hidden = true;
    this.loginError.textContent = "";
    this.loginError.classList.remove("is-info");
  },
};

VigApp.init();
