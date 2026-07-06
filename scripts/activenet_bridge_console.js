(() => {
  if (window.__vigwareActiveNetBridgeInstalled) {
    console.warn('Vigware Active Net Bridge já instalado. Use window.__vigwareActiveNetSendTable()');
    return;
  }

  window.__vigwareActiveNetBridgeInstalled = true;

  const VIGWARE_API_BASE = 'http://127.0.0.1:8002';
  const BATCH_URL = `${VIGWARE_API_BASE}/api/activenet/batch`;
  const EVENT_URL = `${VIGWARE_API_BASE}/api/activenet/event`;
  const sentKeys = new Set();

  function normalizeText(value) {
    return String(value || '').trim().replace(/\s+/g, ' ');
  }

  function readVisibleEventsTable() {
    const tables = [...document.querySelectorAll('table')];
    const table = tables.find(t => {
      const headerText = normalizeText(t.innerText).toLowerCase();
      return headerText.includes('conta') && headerText.includes('evento') && headerText.includes('descrição');
    });

    if (!table) return [];

    const headers = [...table.querySelectorAll('thead th')].map(th => normalizeText(th.innerText));

    return [...table.querySelectorAll('tbody tr')]
      .map(tr => {
        const cells = [...tr.querySelectorAll('td')].map(td => normalizeText(td.innerText));
        const row = {};
        cells.forEach((cell, i) => {
          row[headers[i] || `col_${i + 1}`] = cell;
        });
        return row;
      })
      .filter(row => row.Conta && row.Evento);
  }

  function rowKey(row) {
    return [
      row.Conta || '',
      row.Evento || '',
      row['Data e hora'] || '',
      row['Número de série'] || '',
      row.IMEI || '',
      row.MAC || '',
      row['Informação 1'] || '',
      row['Informação 2'] || ''
    ].join('|');
  }

  function toPayloadRow(row) {
    return {
      account_code: row.Conta || row.conta || row.account_code || null,
      event_code: row.Evento || row.evento || row.event_code || null,
      description: row['Descrição'] || row.Descricao || row.description || null,
      info_1: row['Informação 1'] || row['Informacao 1'] || row.info_1 || null,
      info_2: row['Informação 2'] || row['Informacao 2'] || row.info_2 || null,
      date_time: row['Data e hora'] || row.date_time || null,
      serial_number: row['Número de série'] || row['Numero de serie'] || row.serial_number || null,
      imei: row.IMEI || row.imei || null,
      mac: row.MAC || row.mac || null,
      row
    };
  }

  async function postBatch(events) {
    if (!events.length) {
      console.log('Vigware Bridge: nenhum evento novo para enviar.');
      return { ok: true, imported: 0, skipped: 0, occurrences: 0, errors: [] };
    }

    const response = await fetch(BATCH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: 'ACTIVENET_TABLE_BRIDGE', events })
    });

    const json = await response.json();
    console.log('Vigware Bridge: enviado para Vigware', json);
    return json;
  }

  window.__vigwareActiveNetSendTable = async function(force = false) {
    const rows = readVisibleEventsTable();
    const freshRows = [];

    for (const row of rows) {
      const key = rowKey(row);
      if (!force && sentKeys.has(key)) continue;
      sentKeys.add(key);
      freshRows.push(toPayloadRow(row));
    }

    return postBatch(freshRows);
  };

  window.__vigwareActiveNetSendAll = async function() {
    return window.__vigwareActiveNetSendTable(true);
  };

  window.__vigwareActiveNetStartPolling = function(seconds = 5) {
    if (window.__vigwareActiveNetPoller) clearInterval(window.__vigwareActiveNetPoller);
    window.__vigwareActiveNetPoller = setInterval(() => {
      window.__vigwareActiveNetSendTable(false).catch(err => console.error('Vigware Bridge erro:', err));
    }, Math.max(2, Number(seconds) || 5) * 1000);
    console.log(`Vigware Bridge: polling iniciado a cada ${Math.max(2, Number(seconds) || 5)}s.`);
  };

  window.__vigwareActiveNetStopPolling = function() {
    if (window.__vigwareActiveNetPoller) clearInterval(window.__vigwareActiveNetPoller);
    window.__vigwareActiveNetPoller = null;
    console.log('Vigware Bridge: polling parado.');
  };

  function wrapFunction(name) {
    const original = window[name];
    if (typeof original !== 'function' || original.__vigwareWrapped) return;

    const wrapped = function(...args) {
      const result = original.apply(this, args);
      setTimeout(() => {
        window.__vigwareActiveNetSendTable(false).catch(err => console.error('Vigware Bridge erro:', err));
      }, 300);
      return result;
    };

    wrapped.__vigwareWrapped = true;
    window[name] = wrapped;
    console.log(`Vigware Bridge: função ${name} monitorada.`);
  }

  ['adicionarEvento', 'atualizarEvento', 'atualizarTodosOsEventos', 'removerEvento'].forEach(wrapFunction);

  console.log('%cVigware Active Net Bridge instalado', 'background:#111;color:#3ff;padding:6px 10px;border-radius:6px');
  console.log('Comandos:');
  console.log('window.__vigwareActiveNetSendTable()       // envia só novos eventos visíveis');
  console.log('window.__vigwareActiveNetSendAll()         // força enviar os 100 eventos visíveis');
  console.log('window.__vigwareActiveNetStartPolling(5)   // envia novos a cada 5s');
  console.log('window.__vigwareActiveNetStopPolling()     // para polling');
})();
