// AI News Podcast — frontend logic

const $ = (s) => document.querySelector(s);
const API = '';

const STATE = { tab:'news', page:1, playing:false, vol:0.8, progressTimer:null };

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initPlayer();
  initPipeline();
  initFilters();
  loadNews();
  pollSources();
  setInterval(pollStatus, 8000);
});

// ---- Tabs ----
function initTabs() {
  document.querySelectorAll('.nav-tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      STATE.tab = t.dataset.tab;
      document.getElementById('panel-' + STATE.tab).classList.add('active');
      if (STATE.tab === 'news') loadNews();
      if (STATE.tab === 'podcasts') loadPodcasts();
      if (STATE.tab === 'sources') loadSources();
    });
  });
}

// ---- Player ----
function initPlayer() {
  const a = $('audio');
  a.volume = STATE.vol;

  $('#btnPlay').addEventListener('click', togglePlay);
  $('#progressTrack').addEventListener('click', e => {
    if (!STATE.playing) return;
    const pct = e.offsetX / e.target.clientWidth;
    a.currentTime = pct * (a.duration || 0);
  });

  a.addEventListener('timeupdate', () => {
    if (a.duration) {
      const pct = (a.currentTime / a.duration) * 100;
      $('#progressFill').style.width = pct + '%';
      $('#timeCurrent').textContent = fmt(a.currentTime);
    }
  });
  a.addEventListener('play', () => { $('#statusDot').className = 'status-dot live'; });
  a.addEventListener('pause', () => { $('#statusDot').className = 'status-dot wait'; });
  a.addEventListener('error', () => { STATE.playing = false; updatePlayBtn(); });

  setInterval(updateCurrentTrack, 5000);
}

function togglePlay() {
  const a = $('audio');
  if (STATE.playing) {
    a.pause(); STATE.playing = false; updatePlayBtn();
  } else {
    a.src = API + '/stream'; a.load();
    a.play().then(() => { STATE.playing = true; updatePlayBtn(); }).catch(() => {});
  }
}

function updatePlayBtn() {
  $('#playIcon').textContent = STATE.playing ? '⏸' : '▶';
  $('#timeStatus').textContent = STATE.playing ? '直播中' : '就绪';
}

async function updateCurrentTrack() {
  if (!STATE.playing) return;
  try {
    const r = await fetch(API + '/api/podcasts/current');
    const d = await r.json();
    if (d.podcast && d.podcast.title) {
      $('#playerTitle').textContent = d.podcast.title;
    }
  } catch (e) {}
}

function fmt(s) { const m = Math.floor(s/60); return m + ':' + String(Math.floor(s%60)).padStart(2,'0'); }

// ---- Pipeline ----
function initPipeline() {
  $('#btnTrigger').addEventListener('click', async () => {
    const b = $('#btnTrigger');
    b.textContent = '...'; b.disabled = true;
    try {
      await fetch(API + '/api/pipeline/trigger', { method:'POST', headers:{'Content-Type':'application/json'}, body:'{"force":true}' });
      b.textContent = '✓';
    } catch(e) { b.textContent = '✗'; }
    setTimeout(() => { b.textContent = '采集'; b.disabled = false; }, 2000);
  });
}

async function pollStatus() {
  try {
    const r = await fetch(API + '/stream/status');
    const d = await r.json();
    $('#queueLength').textContent = d.queue_length || '0';
  } catch(e) {}
}

async function pollSources() {
  try {
    const r = await fetch(API + '/api/sources');
    const d = await r.json();
    const sel = $('#sourceFilter');
    if (d.items) d.items.forEach(s => {
      if (![...sel.options].some(o => o.value === s.name)) {
        const o = document.createElement('option');
        o.value = s.name; o.textContent = s.name;
        sel.appendChild(o);
      }
    });
  } catch(e) {}
}

// ---- Filters ----
function initFilters() {
  $('#sourceFilter').addEventListener('change', () => { STATE.page=1; loadNews(); });
  $('#scoreFilter').addEventListener('change', () => { STATE.page=1; loadNews(); });
}

// ---- News ----
async function loadNews(page) {
  STATE.page = page || 1;
  const src = $('#sourceFilter').value;
  const sc = $('#scoreFilter').value;
  const params = new URLSearchParams({ page: STATE.page, page_size: 20 });
  if (src) params.set('source', src);
  if (sc && sc !== '0') params.set('min_score', sc);
  try {
    const r = await fetch(API + '/api/news?' + params);
    const d = await r.json();
    renderNews(d.items || []);
    renderPagination(d.total, d.page, d.page_size);
  } catch(e) {
    $('#newsList').innerHTML = '<div class="empty-state">加载失败</div>';
  }
}

function renderNews(items) {
  const el = $('#newsList');
  if (!items.length) { el.innerHTML = '<div class="empty-state">暂无新闻，点击「采集」开始获取</div>'; return; }
  el.innerHTML = items.map(item => {
    const s = item.importance_score || 0;
    const sc = s>=7 ? 'score-hi' : s>=5 ? 'score-md' : 'score-lo';
    const src = item.source || '';
    const time = item.collected_at ? new Date(item.collected_at).toLocaleString('zh-CN') : '';
    return `<div class="news-item" data-url="${esc(item.url)}" onclick="openNews(this)">
      <div class="news-score ${sc}">${s}</div>
      <div class="news-body">
        <div class="news-title">${esc(item.title)}</div>
        ${item.summary ? '<div class="news-summary">'+esc(item.summary)+'</div>' : ''}
        <div class="news-meta">
          <span>${esc(src)}</span>
          ${time ? '<span>'+time+'</span>' : ''}
          ${item.importance_reason ? '<span>'+esc(item.importance_reason)+'</span>' : ''}
        </div>
      </div>
    </div>`;
  }).join('');
}

function openNews(el) {
  const url = el.dataset.url;
  if (url) window.open(url, '_blank');
}

function renderPagination(total, page, size) {
  const pages = Math.ceil(total / size);
  const el = $('#newsPagination');
  if (pages <= 1) { el.innerHTML = ''; return; }
  let html = '';
  for (let i=1; i<=Math.min(pages,8); i++) {
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
      const ok = item.status === 'completed';
      return `<div class="news-item">
        <div class="news-score ${sc}">${s}</div>
        <div class="news-body">
          <div class="news-title">${esc(item.title)}</div>
          <div class="news-meta">
            <span>${ok ? '✓' : '○'} ${item.status}</span>
            <span>${dur}</span>
            ${item.audio_path ? '<a href="/api/podcasts/'+item.id+'/audio" style="color:var(--accent)">下载</a>' : ''}
          </div>
        </div>
      </div>`;
    }).join('');
  } catch(e) { $('#podcastList').innerHTML = '<div class="empty-state">加载失败</div>'; }
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
        <div class="news-summary" style="font-size:11px;word-break:break-all">${esc(s.url)}</div>
        <div class="news-meta">
          <span>优先级 ${s.priority}</span>
          <button class="btn-small" onclick="toggleSrc('${esc(s.name)}',${s.is_enabled?0:1})">${s.is_enabled?'禁用':'启用'}</button>
          <button class="btn-small" onclick="delSrc('${esc(s.name)}')" style="color:#c06060">删除</button>
        </div>
      </div>
    </div>`).join('');

    $('#btnAddSource').onclick = async () => {
      const name = $('#srcName').value.trim();
      const type = $('#srcType').value;
      const url = $('#srcUrl').value.trim();
      const kw = $('#srcKeywords').value.trim();
      if (!name||!url) return;
      await fetch(API+'/api/sources', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name,type,url,keywords:kw}) });
      $('#srcName').value=''; $('#srcUrl').value=''; $('#srcKeywords').value='';
      loadSources(); pollSources();
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
  loadSources(); pollSources();
}

function esc(s) { if (!s) return ''; const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
