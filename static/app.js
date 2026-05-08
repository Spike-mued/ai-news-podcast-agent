// AI News Podcast — 24/7 continuous

const $ = s => document.querySelector(s);
const API = '';

const STATE = { tab:'news', page:1, audioOn:false };

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initAudio();
  initPipeline();
  initFilters();
  loadNews();
  loadTicker();
  setInterval(loadTicker, 60000);  // refresh ticker every minute
});

// ---- Tabs ----
function initTabs() {
  document.querySelectorAll('.nav-tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      STATE.tab = t.dataset.tab;
      const panel = document.getElementById('panel-' + STATE.tab);
      if (panel) panel.classList.add('active');
      if (STATE.tab === 'news') loadNews();
      if (STATE.tab === 'podcasts') loadPodcasts();
      if (STATE.tab === 'sources') loadSources();
    });
  });
}

// ---- Audio (background, no UI bar) ----
function initAudio() {
  const btn = $('#btnAudio');
  btn.addEventListener('click', () => {
    const a = $('audio');
    if (STATE.audioOn) {
      a.pause();
      btn.textContent = '🔇';
      btn.classList.remove('on');
      STATE.audioOn = false;
    } else {
      a.src = API + '/stream';
      a.load();
      a.play().then(() => {
        STATE.audioOn = true;
        btn.textContent = '🔊';
        btn.classList.add('on');
      }).catch(() => {
        btn.textContent = '🔇';
      });
    }
  });
}

// ---- Pipeline ----
function initPipeline() {
  $('#btnTrigger').addEventListener('click', async () => {
    const b = $('#btnTrigger');
    b.textContent = '...'; b.disabled = true;
    try {
      await fetch(API + '/api/pipeline/trigger', { method:'POST', headers:{'Content-Type':'application/json'}, body:'{"force":true}' });
    } catch(e) {}
    setTimeout(() => { b.textContent = '立即采集'; b.disabled = false; }, 3000);
  });
}

// ---- Filters ----
function initFilters() {
  $('#sourceFilter').addEventListener('change', () => { STATE.page=1; loadNews(); });
  fetch(API + '/api/sources').then(r => r.json()).then(d => {
    if (d.items) d.items.forEach(s => {
      const sel = $('#sourceFilter');
      if (![...sel.options].some(o => o.value === s.name)) {
        sel.appendChild(new Option(s.name, s.name));
      }
    });
  }).catch(()=>{});
}

// ---- Ticker ----
async function loadTicker() {
  try {
    const r = await fetch(API + '/api/news?page=1&page_size=20');
    const d = await r.json();
    if (!d.items || !d.items.length) return;
    const html = d.items.map(item => {
      const s = item.importance_score || 0;
      return `<div class="ticker-item" onclick="window.open('${esc(item.url)}','_blank')">
        <div class="ti-score">${'●'.repeat(Math.min(5, Math.ceil(s/2)))} ${s}/10</div>
        <div class="ti-title">${esc(item.title)}</div>
        <div class="ti-source">${esc(item.source || '')}</div>
      </div>`;
    }).join('');
    // 复制一份用于无缝循环
    $('#tickerItems').innerHTML = html + html;
  } catch(e) {}
}

// ---- News ----
async function loadNews(page) {
  STATE.page = page || 1;
  const src = $('#sourceFilter').value;
  const params = new URLSearchParams({ page: STATE.page, page_size: 20 });
  if (src) params.set('source', src);
  try {
    const r = await fetch(API + '/api/news?' + params);
    const d = await r.json();
    renderNews(d.items || []);
    renderPagination(d.total, d.page, d.page_size);
  } catch(e) { $('#newsList').innerHTML = '<div class="empty-state">加载失败</div>'; }
}

function renderNews(items) {
  const el = $('#newsList');
  if (!items.length) { el.innerHTML = '<div class="empty-state">暂无新闻，点击「立即采集」</div>'; return; }
  el.innerHTML = items.map(item => {
    const s = item.importance_score || 0;
    const sc = s>=7 ? 'score-hi' : s>=5 ? 'score-md' : 'score-lo';
    const time = item.collected_at ? new Date(item.collected_at).toLocaleString('zh-CN') : '';
    return `<div class="news-item" onclick="window.open('${esc(item.url)}','_blank')">
      <div class="news-score ${sc}">${s}</div>
      <div class="news-body">
        <div class="news-title">${esc(item.title)}</div>
        ${item.summary ? '<div class="news-summary">'+esc(item.summary)+'</div>' : ''}
        <div class="news-meta">
          <span>${esc(item.source || '')}</span>
          ${time ? '<span>'+time+'</span>' : ''}
          ${item.importance_reason ? '<span>'+esc(item.importance_reason)+'</span>' : ''}
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderPagination(total, page, size) {
  const pages = Math.ceil(total / size);
  const el = $('#newsPagination');
  if (pages <= 1) { el.innerHTML = ''; return; }
  let html = '';
  for (let i=1; i<=Math.min(pages,6); i++) {
    html += `<button class="${i===page?'active':''}" onclick="loadNews(${i})">${i}</button>`;
  }
  el.innerHTML = html;
}

// ---- Podcasts ----
async function loadPodcasts() {
  try {
    const r = await fetch(API + '/api/podcasts?page=1&page_size=50');
    const d = await r.json();
    const el = $('#podcastList');
    if (!d.items || !d.items.length) { el.innerHTML = '<div class="empty-state">暂无播客</div>'; return; }
    el.innerHTML = d.items.map(item => {
      const s = item.importance_level || 0;
      const sc = s>=7 ? 'score-hi' : s>=5 ? 'score-md' : 'score-lo';
      const dur = item.audio_duration ? fmt(item.audio_duration) : '--';
      return `<div class="news-item">
        <div class="news-score ${sc}">${s}</div>
        <div class="news-body">
          <div class="news-title">${esc(item.title)}</div>
          <div class="news-meta">
            <span>${item.status==='completed'?'✓':'○'} ${item.status}</span>
            <span>${dur}</span>
            ${item.audio_path ? `<a href="/api/podcasts/${item.id}/audio" style="color:var(--accent)">下载</a>` : ''}
          </div>
        </div>
      </div>`;
    }).join('');
  } catch(e) {}
}

// ---- Sources ----
async function loadSources() {
  try {
    const r = await fetch(API + '/api/sources');
    const d = await r.json();
    const el = $('#sourceList');
    if (!d.items || !d.items.length) { el.innerHTML = '<div class="empty-state">暂无源</div>'; return; }
    el.innerHTML = d.items.map(s => `<div class="news-item">
      <div class="news-body">
        <div class="news-title">${s.is_enabled?'●':'○'} ${esc(s.name)} <span style="font-size:11px;color:var(--text-muted)">[${s.type}]</span></div>
        <div style="font-size:11px;color:var(--text-muted);word-break:break-all;margin-bottom:4px">${esc(s.url)}</div>
        <div class="news-meta">
          <button class="btn" onclick="toggleSrc('${esc(s.name)}',${s.is_enabled?0:1})">${s.is_enabled?'禁用':'启用'}</button>
          <button class="btn" onclick="delSrc('${esc(s.name)}')" style="color:#c06060">删除</button>
        </div>
      </div>
    </div>`).join('');
    $('#btnAddSource').onclick = async () => {
      const name = $('#srcName').value.trim(), type = $('#srcType').value;
      const url = $('#srcUrl').value.trim(), kw = $('#srcKeywords').value.trim();
      if (!name||!url) return;
      await fetch(API+'/api/sources', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name,type,url,keywords:kw}) });
      $('#srcName').value=''; $('#srcUrl').value=''; $('#srcKeywords').value='';
      loadSources();
    };
  } catch(e) {}
}

async function toggleSrc(name, en) {
  await fetch(API+'/api/sources/'+encodeURIComponent(name), { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({is_enabled:!!en}) });
  loadSources();
}

async function delSrc(name) {
  if (!confirm('删除 '+name+'？')) return;
  await fetch(API+'/api/sources/'+encodeURIComponent(name), { method:'DELETE' });
  loadSources();
}

// ---- Utils ----
function esc(s) { if (!s) return ''; const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function fmt(s) { const m=Math.floor(s/60); return m+':'+String(Math.floor(s%60)).padStart(2,'0'); }
