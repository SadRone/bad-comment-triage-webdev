const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let providers = [];
let currentJob = null;
let currentBand = '';
let pollTimer = null;

const splitCsv = (v) => v.split(',').map(x => x.trim()).filter(Boolean);
const bandLabel = {
  review_first: '검토 우선',
  context_needed: '맥락 필요',
  low_priority: '낮은 우선순위',
};

async function jsonFetch(url, options = {}) {
  const res = await fetch(url, options);
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

async function loadProviders() {
  const data = await jsonFetch('/api/providers');
  providers = data.providers;
  $('#providerCards').innerHTML = providers.map(p => `
    <div class="provider-card">
      <div class="provider-top">
        <div class="provider-name">${escapeHtml(p.name)}</div>
        <div><span class="dot ${p.configured ? 'ok' : 'off'}"></span>${p.configured ? 'READY' : 'NOT CONFIGURED'}</div>
      </div>
      <p>${escapeHtml(p.description)}</p>
      <div class="keyline">${escapeHtml(p.requires.join(' + '))}</div>
    </div>
  `).join('');
  $('#providerChecks').innerHTML = providers.map(p => `
    <label class="check ${p.configured ? '' : 'disabled'}">
      <input type="checkbox" value="${p.name}" ${p.configured ? 'checked' : 'disabled'} />
      ${p.name.toUpperCase()}
    </label>
  `).join('');
}

$('#refreshProviders').addEventListener('click', () => loadProviders().catch(showFormError));

$('#searchForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  hideFormError();
  const payload = {
    target: $('#target').value.trim(),
    aliases: splitCsv($('#aliases').value),
    keywords: splitCsv($('#keywords').value),
    providers: $$('#providerChecks input:checked').map(x => x.value),
    limit: Number($('#limit').value),
  };
  try {
    const job = await jsonFetch('/api/jobs', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    currentJob = job.id;
    currentBand = '';
    $('#jobPanel').classList.remove('hidden');
    $('#resultsPanel').classList.remove('hidden');
    $('#csvLink').href = `/api/jobs/${currentJob}/export.csv`;
    startPolling();
  } catch (err) {
    showFormError(err);
  }
});

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollOnce();
  pollTimer = setInterval(pollOnce, 1500);
}

async function pollOnce() {
  if (!currentJob) return;
  try {
    const job = await jsonFetch(`/api/jobs/${currentJob}`);
    renderJob(job);
    await loadResults();
    if (['completed','failed'].includes(job.status)) {
      clearInterval(pollTimer); pollTimer = null;
    }
  } catch (err) {
    $('#jobError').textContent = err.message;
    $('#jobError').classList.remove('hidden');
  }
}

function renderJob(job) {
  $('#jobStatus').textContent = job.status.toUpperCase();
  const stage = job.progress?.stage || job.status;
  const saved = job.counts?.total || 0;
  const widths = { queued: 8, running: 28, completed: 100, failed: 100 };
  let w = widths[job.status] || 15;
  if (stage.startsWith('collecting:')) w = 50;
  if (stage.startsWith('completed:')) w = 78;
  $('#progressBar').style.width = `${w}%`;
  $('#progressText').textContent = `단계: ${stage} · 저장 ${saved}개 · 대상: ${job.target}`;

  $('#counts').innerHTML = `
    <div class="count"><strong>${job.counts.total}</strong>전체</div>
    <div class="count review"><strong>${job.counts.review_first}</strong>검토 우선</div>
    <div class="count context"><strong>${job.counts.context_needed}</strong>맥락 필요</div>
    <div class="count low"><strong>${job.counts.low_priority}</strong>낮은 우선순위</div>
  `;

  const entries = Object.entries(job.diagnostics || {});
  $('#diagnostics').innerHTML = entries.length ? entries.map(([name,d]) => `
    <div class="diag"><h3>${escapeHtml(name)}</h3><pre>${escapeHtml(prettyDiag(d))}</pre></div>
  `).join('') : `<div class="diag"><h3>대기 중</h3><pre>수집기가 시작되면 검색 결과 수, 페이지 시도 수, 차단/오류, 저장/중복 개수를 표시합니다.</pre></div>`;

  if (job.error) {
    $('#jobError').textContent = job.error;
    $('#jobError').classList.remove('hidden');
  } else {
    $('#jobError').classList.add('hidden');
  }
}

function prettyDiag(d) {
  const lines = [];
  for (const [k,v] of Object.entries(d.stats || {})) lines.push(`${k}: ${v}`);
  lines.push(`saved: ${d.saved || 0}`);
  lines.push(`duplicates: ${d.duplicates || 0}`);
  if ((d.errors || []).length) lines.push(`errors:\n- ${d.errors.join('\n- ')}`);
  return lines.join('\n');
}

async function loadResults() {
  if (!currentJob) return;
  const q = currentBand ? `?band=${encodeURIComponent(currentBand)}` : '';
  const data = await jsonFetch(`/api/jobs/${currentJob}/results${q}`);
  $('#results').innerHTML = data.items.length ? data.items.map(renderResult).join('') : `
    <div class="result"><blockquote>아직 저장된 결과가 없습니다. 위의 파이프라인 진단에서 검색 결과 수와 차단/오류 이유를 확인하세요.</blockquote></div>
  `;
}

function renderResult(x) {
  const source = escapeHtml(x.source);
  const author = x.author ? `작성자: ${escapeHtml(x.author)}` : '';
  const date = x.published_at ? escapeHtml(x.published_at) : '';
  const href = safeHref(x.url);
  const link = href ? `<a href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer">원문 열기</a>` : '';
  return `
    <article class="result">
      <div class="result-top">
        <span class="band ${x.risk_band}">${bandLabel[x.risk_band] || x.risk_band}</span>
        <span class="score">${x.risk_score}</span>
      </div>
      <blockquote>${escapeHtml(x.text)}</blockquote>
      ${x.context ? `<div class="meta">문맥: ${escapeHtml(x.context)}</div>` : ''}
      <div class="meta"><span>${source}</span><span>${author}</span><span>${date}</span><span>${link}</span></div>
      <div class="reasons">${x.reasons.map(r => `• ${escapeHtml(r)}`).join('<br>')}</div>
    </article>`;
}

$$('.filter').forEach(btn => btn.addEventListener('click', async () => {
  $$('.filter').forEach(x => x.classList.remove('active'));
  btn.classList.add('active');
  currentBand = btn.dataset.band;
  if (currentJob) await loadResults();
}));

$('#manualBtn').addEventListener('click', async () => {
  const target = $('#manualTarget').value.trim();
  const text = $('#manualText').value.trim();
  const context = $('#manualContext').value.trim();
  if (!target || !text) return;
  try {
    const r = await jsonFetch('/api/analyze/manual', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({target,text,context})
    });
    $('#manualResult').classList.remove('hidden');
    $('#manualResult').innerHTML = `
      <div class="result-top"><span class="band ${r.risk_band}">${bandLabel[r.risk_band]}</span><span class="score">${r.risk_score}</span></div>
      <div class="reasons">${r.reasons.map(x => `• ${escapeHtml(x)}`).join('<br>')}</div>`;
  } catch (e) {
    $('#manualResult').classList.remove('hidden');
    $('#manualResult').textContent = e.message;
  }
});

function showFormError(err) { $('#formError').textContent = err.message || String(err); $('#formError').classList.remove('hidden'); }
function hideFormError() { $('#formError').classList.add('hidden'); }
function escapeHtml(v='') { return String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function escapeAttr(v='') { return escapeHtml(v); }
function safeHref(v='') { try { const u = new URL(v); return ['http:','https:'].includes(u.protocol) ? u.href : ''; } catch (_) { return ''; } }

loadProviders().catch(showFormError);
