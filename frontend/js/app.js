(async function boot() {
  try {
    await VigUI.loadPartial("sidebarMount", "/static/partials/sidebar.html");
    await VigUI.loadPartial("topbarMount", "/static/partials/topbar.html");
    await VigUI.loadPartial("monitoringMount", "/static/partials/monitoring.html");
    await VigUI.loadPartial("modalMount", "/static/partials/occurrence_modal.html");

    VigMonitoring.bindEvents();
    await VigMonitoring.refresh();

    VigWS.start(async () => {
      await VigMonitoring.refresh();
    });
  } catch (error) {
    console.error(error);
    document.body.innerHTML = `<pre style="padding:24px;color:#c00">Erro ao carregar Vigware: ${error.message}</pre>`;
  }
})();
