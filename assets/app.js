/* Native app is the default path. Upload only on explicit form submission. */
'use strict';
document.querySelectorAll('.tp3').forEach((root) => {
  const form = root.querySelector('.tp3-form');
  if (!form) return;
  const config = JSON.parse(root.dataset.config);
  const status = root.querySelector('.tp3-status');
  const progress = root.querySelector('.tp3-progress');
  const results = root.querySelector('.tp3-results');
  const cancel = root.querySelector('.tp3-cancel');
  const submit = form.querySelector('[type=submit]');
  const storageKey = 'tp3-job:' + config.api;
  let job = null;
  let failures = 0;
  let timer = null;
  async function api(path, options = {}) {
    const response = await fetch(config.api + path, {
      ...options, credentials: 'same-origin',
      headers: {'X-WP-Nonce': config.nonce},
      signal: AbortSignal.timeout(options.method === 'POST' ? 180000 : 20000),
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.message || data.detail || 'Falha na solicitação');
      error.status = response.status;
      throw error;
    }
    return data;
  }
  function remember(id) {
    try { id ? sessionStorage.setItem(storageKey, id) : sessionStorage.removeItem(storageKey); } catch (_) { /* private mode */ }
  }
  function finish() {
    clearTimeout(timer);
    job = null;
    remember(null);
    submit.disabled = false;
    cancel.disabled = true;
  }
  function show(output) {
    results.replaceChildren();
    ['txt', 'srt', 'vtt'].forEach((format) => {
      const label = document.createElement('label');
      label.textContent = format.toUpperCase() + ' — revisão independente';
      const area = document.createElement('textarea');
      area.value = output[format];
      label.append(area);
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Salvar ' + format.toUpperCase();
      button.addEventListener('click', () => {
        const url = URL.createObjectURL(new Blob([area.value], {type: 'text/plain;charset=utf-8'}));
        const link = document.createElement('a');
        link.href = url;
        link.download = 'transcricao.' + format;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      });
      results.append(label, button);
    });
  }
  async function poll() {
    if (!job) return;
    try {
      const data = await api('jobs/' + job);
      failures = 0;
      status.textContent = data.message || data.state;
      progress.value = data.progress;
      if (data.state === 'done') {
        const result = await api('jobs/' + job + '/result');
        show(result.outputs);
        status.textContent = 'Concluído. Revise e salve os resultados.';
        finish();
      } else if (['error', 'cancelled'].includes(data.state)) {
        status.textContent = data.state === 'cancelled' ? 'Cancelado.' : data.message;
        finish();
      } else timer = setTimeout(poll, 2000);
    } catch (error) {
      if (error.status === 404) {
        finish();
        status.textContent = 'O trabalho expirou ou não está disponível nesta conta. Você pode iniciar outro.';
        return;
      }
      failures += 1;
      status.textContent = error.message + ' — consultando novamente…';
      if (failures < 10) timer = setTimeout(poll, 5000);
      else {
        status.textContent = 'Conexão perdida. Recarregue a página para recuperar o acompanhamento.';
        // Keep the saved id: a failed request does not cancel server work.
        submit.disabled = true;
      }
    }
  }
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const file = form.elements.media.files[0];
    if (!file || file.size < 1 || file.size > 100 * 1024 * 1024) {
      status.textContent = 'Selecione um arquivo de até 100 MiB.';
      return;
    }
    submit.disabled = true;
    results.replaceChildren();
    progress.value = 0;
    status.textContent = 'Enviando arquivo ao servidor…';
    try {
      const data = await api('jobs', {method: 'POST', body: new FormData(form)});
      job = data.id;
      failures = 0;
      remember(job);
      cancel.disabled = false;
      poll();
    } catch (error) {
      status.textContent = error.message;
      submit.disabled = false;
    }
  });
  cancel.addEventListener('click', async () => {
    if (!job) return;
    try {
      await api('jobs/' + job, {method: 'DELETE'});
      status.textContent = 'Cancelamento solicitado; aguardando o segmento ou download atual.';
    } catch (error) { status.textContent = error.message; }
  });
  try { job = sessionStorage.getItem(storageKey); } catch (_) { /* private mode */ }
  if (job && /^[a-f0-9]{32}$/.test(job)) {
    submit.disabled = true;
    cancel.disabled = false;
    poll();
  }
});
