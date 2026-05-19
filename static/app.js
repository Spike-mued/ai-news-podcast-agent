// AI News Podcast — 24/7 continuous, auto-refresh, subtitle-synced

const $ = s => document.querySelector(s);
const API = '';

const STATE = {
  tab: 'news', page: 1, audioOn: false, connecting: false,
  lastStreamVersion: -1,  // 用于检测播放内容变化
  currentSubtitles: [],   // 当前播放的字幕元数据
};

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initAudio();
  initPipeline();
  initFilters();
  // 首次加载
  loadNews();
  loadCurrentSubtitles();
  // 自动轮询刷新（30 秒）
  setInterval(autoRefresh, 30000);
  wireModelAddBtns();
  loadModelConnections();
  loadSupportedServices();
  // 归档按钮
  const archiveBtn = document.getElementById('btnArchive');
  if (archiveBtn) archiveBtn.addEventListener('click', async () => {
    if (!confirm('归档昨天之前的新闻和已播播客？')) return;
    archiveBtn.textContent = '...'; archiveBtn.disabled = true;
    try {
      const r = await fetch(API + '/api/archive/all', { method: 'POST' });
      const d = await r.json();
      alert('已归档: ' + d.total + ' 条（新闻 ' + d.news_archived + '，播客 ' + d.podcasts_archived + '）');
      loadNews();
      loadCurrentSubtitles();
    } catch(e) { alert('归档失败'); }
    archiveBtn.textContent = '归档'; archiveBtn.disabled = false;
  });
});

// 自动刷新所有活跃 Tab 内容
async function autoRefresh() {
  try {
    // 检测是否有新的播客内容
    const status = await fetch(API + '/stream/status').then(r => r.json()).catch(() => null);
    const versionChanged = status && status.version !== STATE.lastStreamVersion;

    if (versionChanged) {
      STATE.lastStreamVersion = status.version;
      // 有新播客 → 刷新字幕
      await loadCurrentSubtitles();
    }

    // 刷新当前 tab 内容
    if (STATE.tab === 'news') loadNews();
    if (STATE.tab === 'podcasts') loadPodcasts();

    // 始终检查是否有新字幕（即使 version 没变，也定期更新）
    if (!versionChanged && !STATE.currentSubtitles.length) {
      await loadCurrentSubtitles();
    }
  } catch (e) { /* silent */ }
}

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
      if (STATE.tab === 'models') { loadModelConnections(); loadSupportedServices(); }
      if (STATE.tab === 'podcasts') loadPodcasts();
      if (STATE.tab === 'sources') loadSources();
      if (STATE.tab === 'chat') initChatTab();
    });
  });
}

// ---- Audio (24/7 continuous stream — mute/unmute toggle, no disconnect) ----
function initAudio() {
  const audio = $('audio');
  const btn = $('#btnAudio');
  let reconnectTimer = null;
  let streamLoaded = false;

  function connectStream() {
    if (STATE.connecting) return;
    STATE.connecting = true;
    btn.textContent = '⏳';
    btn.classList.add('loading');

    // 清除之前的 src 避免重复连接
    if (audio.src) {
      audio.removeAttribute('src');
      audio.load();
    }
    audio.src = API + '/stream';
    audio.load();
    streamLoaded = true;

    audio.play().then(() => {
      STATE.connecting = false;
      STATE.audioOn = true;
      btn.textContent = '🔊';
      btn.classList.add('on');
      btn.classList.remove('loading');
    }).catch(() => {
      STATE.connecting = false;
      btn.textContent = '🔇';
      btn.classList.remove('on', 'loading');
      reconnectTimer = setTimeout(connectStream, 5000);
    });
  }

  btn.addEventListener('click', () => {
    clearTimeout(reconnectTimer);

    if (STATE.connecting) return;

    if (STATE.audioOn) {
      // Mute — keep stream connection alive
      audio.pause();
      btn.textContent = '🔇';
      btn.classList.remove('on');
      STATE.audioOn = false;
    } else {
      // Unmute
      if (streamLoaded) {
        audio.play().then(() => {
          STATE.audioOn = true;
          btn.textContent = '🔊';
          btn.classList.add('on');
        }).catch(() => connectStream());
      } else {
        connectStream();
      }
    }
  });

  // Auto-start
  setTimeout(connectStream, 1500);

  // Fatal error → reconnect
  audio.addEventListener('error', () => {
    STATE.connecting = false;
    STATE.audioOn = false;
    streamLoaded = false;
    btn.textContent = '🔇';
    btn.classList.remove('on', 'loading');
    reconnectTimer = setTimeout(connectStream, 5000);
  });

  // Buffering feedback
  audio.addEventListener('waiting', () => {
    if (STATE.audioOn) { btn.textContent = '⏳'; btn.classList.add('loading'); }
  });
  audio.addEventListener('playing', () => {
    if (STATE.audioOn) { btn.textContent = '🔊'; btn.classList.remove('loading'); }
  });
}

// ---- Subtitle Ticker (匹配当前播放内容) ----
async function loadCurrentSubtitles() {
  try {
    // 方法1：从 stream status 获取当前播放的元数据
    const status = await fetch(API + '/stream/status').then(r => r.json()).catch(() => null);
    STATE.lastStreamVersion = status ? status.version : STATE.lastStreamVersion;

    // 方法2：从 /api/podcasts 获取最新一批播客脚本
    const r = await fetch(API + '/api/podcasts?page=1&page_size=30');
    const d = await r.json();
    const items = d.items || [];

    // 优先使用 stream 中的字幕元数据
    let subtitleScripts = [];
    if (status && status.current_metadata && status.current_metadata.scripts) {
      subtitleScripts = status.current_metadata.scripts;
    }

    // Fallback：用最新完成的播客脚本
    if (!subtitleScripts.length && items.length) {
      const withScripts = items.filter(i => i.script && i.script.length > 20);
      if (withScripts.length) {
        // 取最新 15 条
        subtitleScripts = withScripts.slice(0, 15).map(i => ({
          title: i.title,
          script: i.script,
          score: i.importance_level || 0,
        }));
      }
    }

    if (subtitleScripts.length) {
      STATE.currentSubtitles = subtitleScripts;
      renderTicker(subtitleScripts);
    } else if (status && status.queue_length > 0) {
      // 有队列但无字幕数据，显示等待
      $('#tickerItems').innerHTML = '<div class="ticker-item" style="text-align:center;color:var(--text-muted)">🎙 播客播放中，字幕加载中...</div><div class="ticker-item" style="text-align:center;color:var(--text-muted)">🎙 播客播放中，字幕加载中...</div>';
    } else {
      $('#tickerItems').innerHTML = '<div class="ticker-item" style="text-align:center;color:var(--text-muted)">等待播客生成...</div><div class="ticker-item" style="text-align:center;color:var(--text-muted)">等待播客生成...</div>';
    }
  } catch (e) {
    // 静默失败，下次轮询重试
  }
}

function renderTicker(scripts) {
  const html = scripts.map((item, i) => {
    const script = item.script || '';
    const title = item.title || '';
    // 适中的截取长度
    const display = script.length > 400 ? script.slice(0, 400) + '...' : script;
    return `<div class="ticker-item">
      <div class="ti-score">${title ? esc(title) : 'AI新闻播客'}</div>
      <div class="ti-script">${esc(display)}</div>
    </div>`;
  }).join('');
  // 复制一份用于无缝循环：内容少于 8 条时多复制几次确保填满
  const repeat = scripts.length < 8 ? Math.ceil(16 / scripts.length) : 2;
  $('#tickerItems').innerHTML = Array(repeat).fill(html).join('');
}

// ---- Pipeline Trigger with progress ----
function initPipeline() {
  $('#btnTrigger').addEventListener('click', async () => {
    const b = $('#btnTrigger');
    b.textContent = '采集中...'; b.disabled = true;

    const bar = $('#pipelineProgress') || createProgressBar();
    bar.style.width = '0%';
    bar.parentElement.style.display = 'block';

    let w = 0;
    const animate = setInterval(() => {
      w += Math.random() * 15;
      if (w > 90) w = 90;
      bar.style.width = w + '%';
    }, 400);

    try {
      const r = await fetch(API + '/api/pipeline/trigger', { method:'POST', headers:{'Content-Type':'application/json'}, body:'{"force":true}' });
      const data = await r.json();
      clearInterval(animate);
      bar.style.width = '100%';

      // 采集完成后立即刷新所有内容
      loadNews();
      loadCurrentSubtitles();
      updatePipelineStatus(data.success ? '✅ 采集完成' : '⚠️ ' + (data.error || '失败'));
    } catch(e) {
      clearInterval(animate);
      bar.style.width = '0%';
      bar.parentElement.style.display = 'none';
      updatePipelineStatus('❌ 网络错误');
    }

    b.textContent = '立即采集'; b.disabled = false;
    setTimeout(() => { bar.style.width = '0%'; bar.parentElement.style.display = 'none'; }, 2000);
  });
}

function createProgressBar() {
  const header = document.querySelector('.header');
  const wrap = document.createElement('div');
  wrap.id = 'pipelineProgressWrap';
  wrap.style.cssText = 'height:3px;background:var(--bg-card);width:100%;display:none;';
  const bar = document.createElement('div');
  bar.id = 'pipelineProgress';
  bar.style.cssText = 'height:100%;background:var(--accent);width:0%;transition:width 0.3s ease;';
  wrap.appendChild(bar);
  header.parentElement.insertBefore(wrap, header.nextSibling);
  return bar;
}

function updatePipelineStatus(msg) {
  let el = $('#pipelineStatus');
  if (!el) {
    el = document.createElement('span');
    el.id = 'pipelineStatus';
    el.style.cssText = 'font-size:12px;color:var(--green);margin-left:8px;transition:opacity 0.5s ease;';
    document.querySelector('.header-actions').appendChild(el);
  }
  el.textContent = msg;
  el.style.opacity = '1';
  setTimeout(() => { el.style.opacity = '0'; }, 3000);
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
          ${item.script ? '<div class="news-summary" style="-webkit-line-clamp:3">'+esc(item.script)+'</div>' : ''}
          <div class="news-meta">
            <span>${item.status==='completed'?'✓':'○'} ${esc(item.status)}</span>
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
    // 重新绑定添加按钮（避免重复绑定）
    const addBtn = $('#btnAddSource');
    if (addBtn) {
      addBtn.onclick = async () => {
        const name = $('#srcName').value.trim(), type = $('#srcType').value;
        const url = $('#srcUrl').value.trim(), kw = $('#srcKeywords').value.trim();
        if (!name||!url) return;
        await fetch(API+'/api/sources', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name,type,url,keywords:kw}) });
        $('#srcName').value=''; $('#srcUrl').value=''; $('#srcKeywords').value='';
        loadSources();
      };
    }
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

// ---- Model Connections ----
let _modelData = { items: [], active_llm: null, active_tts: null };
let _supportedServices = { llm: [], tts: [] };

async function loadModelConnections() {
  try {
    const r = await fetch(API + '/api/model-connections');
    _modelData = await r.json();
    renderModelSection('llm');
    renderModelSection('tts');
  } catch(e) {}
}

function renderModelSection(type) {
  const items = (_modelData.items || []).filter(i => i.service_type === type);
  const active = type === 'llm' ? _modelData.active_llm : _modelData.active_tts;

  const activeEl = document.getElementById('modelActive' + type.toUpperCase());
  if (activeEl) {
    activeEl.textContent = active
      ? '✅ 当前激活: ' + active.name + (active.model ? ' (' + active.model + ')' : '') + (active.provider ? ' [' + active.provider + ']' : '')
      : '⚠️ 未激活任何连接，使用 .env 默认配置';
  }

  const listEl = document.getElementById('modelList' + type.toUpperCase());
  if (!listEl) return;
  if (!items.length) {
    listEl.innerHTML = '<div class="empty-state" style="padding:20px">暂无连接，点击下方按钮添加</div>';
    return;
  }
  listEl.innerHTML = items.map(item => {
    const isActive = item.is_active;
    const detail = [
      item.provider ? 'Provider: ' + item.provider : '',
      item.model ? 'Model: ' + item.model : '',
      item.voice ? 'Voice: ' + item.voice : '',
      item.base_url ? 'URL: ' + item.base_url : '',
    ].filter(Boolean).join(' · ');
    return `<div class="model-card ${isActive ? 'active' : ''}" onclick="event.stopPropagation()">
      <div class="mc-name">${isActive ? '⭐ ' : ''}${esc(item.name)}</div>
      <div class="mc-detail">${detail || '(使用默认配置)'}</div>
      <div class="mc-actions">
        ${isActive ? '<button disabled style="color:var(--green)">已激活</button>'
          : `<button onclick="activateConnection(${item.id},'${item.service_type}')">激活</button>`}
        <button onclick="editConnectionForm(${item.id})">编辑</button>
        <button class="danger" onclick="deleteConnection(${item.id})">删除</button>
      </div>
      <div class="model-form" id="form-${item.id}"></div>
    </div>`;
  }).join('');
}

async function activateConnection(id, type) {
  try {
    await fetch(API + '/api/model-connections/' + id + '/activate', { method: 'POST' });
    loadModelConnections();
  } catch(e) {}
}

async function deleteConnection(id) {
  if (!confirm('确认删除此模型连接？')) return;
  try {
    await fetch(API + '/api/model-connections/' + id, { method: 'DELETE' });
    loadModelConnections();
  } catch(e) {}
}

function editConnectionForm(id) {
  const formEl = document.getElementById('form-' + id);
  if (!formEl) return;
  const item = (_modelData.items || []).find(i => i.id === id);
  if (!item) return;

  formEl.classList.toggle('show');
  if (!formEl.classList.contains('show')) { formEl.innerHTML = ''; return; }

  formEl.innerHTML = `<div class="model-form show">
      <input class="input" id="edName-${id}" value="${escAttr(item.name)}" placeholder="名称">
      <select class="input" id="edProvider-${id}">
        <option value="dashscope" ${item.provider==='dashscope'?'selected':''}>DashScope</option>
        <option value="openai" ${item.provider==='openai'?'selected':''}>OpenAI</option>
        <option value="edge_tts" ${item.provider==='edge_tts'?'selected':''}>Edge TTS</option>
        <option value="doubao" ${item.provider==='doubao'?'selected':''}>豆包 TTS</option>
        <option value="openai_tts" ${item.provider==='openai_tts'?'selected':''}>OpenAI TTS</option>
        <option value="custom_openai" ${item.provider==='custom_openai'?'selected':''}>自定义</option>
      </select>
      <input class="input" id="edURL-${id}" value="${escAttr(item.base_url)}" placeholder="API Base URL">
      <input class="input" id="edKey-${id}" value="${escAttr(item.api_key)}" placeholder="API Key (留空 = 用.env)" autocomplete="off">
      ${item.service_type === 'llm'
        ? '<input class="input" id="edModel-'+id+'" value="'+escAttr(item.model)+'" placeholder="Model 名称 (如 qwen-plus)">'
        : '<input class="input" id="edVoice-'+id+'" value="'+escAttr(item.voice)+'" placeholder="Voice (如 zh-CN-YunxiNeural)">'}
      <div class="btn-row">
        <button class="btn" onclick="saveConnection(${id})" style="border-color:var(--green);color:var(--green)">保存</button>
        <button class="btn" onclick="document.getElementById('form-${id}').classList.remove('show')">取消</button>
      </div>
    </div>`;
}

async function saveConnection(id) {
  const item = (_modelData.items || []).find(i => i.id === id);
  if (!item) return;
  const body = JSON.stringify({
    name: document.getElementById('edName-'+id).value.trim(),
    service_type: item.service_type,
    provider: document.getElementById('edProvider-'+id).value,
    base_url: document.getElementById('edURL-'+id).value.trim(),
    api_key: document.getElementById('edKey-'+id).value.trim(),
    model: item.service_type === 'llm' ? (document.getElementById('edModel-'+id)?.value.trim() || '') : '',
    voice: item.service_type === 'tts' ? (document.getElementById('edVoice-'+id)?.value.trim() || '') : '',
    is_active: item.is_active,
  });
  try {
    await fetch(API + '/api/model-connections/' + id, { method: 'PUT', headers: {'Content-Type':'application/json'}, body });
    loadModelConnections();
  } catch(e) {}
}

function showAddForm(type) {
  const formId = 'form-new-' + type;
  const existing = document.getElementById(formId);
  if (existing) { existing.remove(); return; }

  const section = document.getElementById('modelList' + type.toUpperCase());
  if (!section) return;

  const div = document.createElement('div');
  div.id = formId;
  div.className = 'model-form show';
  div.style.marginTop = '8px';
  div.innerHTML = `
    <input class="input" id="newName-${type}" placeholder="连接名称 (如: 我的通义千问)">
    <select class="input" id="newProvider-${type}">
      ${type === 'llm' ? `
        <option value="dashscope">DashScope (通义千问)</option>
        <option value="openai">OpenAI</option>
        <option value="custom_openai">自定义 OpenAI 兼容</option>
      ` : `
        <option value="edge_tts">Edge TTS (免费)</option>
        <option value="doubao">豆包 TTS</option>
        <option value="openai_tts">OpenAI TTS</option>
      `}
    </select>
    <input class="input" id="newURL-${type}" placeholder="API Base URL (留空=默认)">
    <input class="input" id="newKey-${type}" placeholder="API Key (留空=用.env)" autocomplete="off">
    ${type === 'llm'
      ? '<input class="input" id="newModel-'+type+'" placeholder="Model 名称, 如 qwen-plus / gpt-4o">'
      : '<input class="input" id="newVoice-'+type+'" placeholder="Voice, 如 zh-CN-YunxiNeural">'}
    <div class="btn-row">
      <button class="btn" onclick="saveNewConnection('${type}')" style="border-color:var(--green);color:var(--green)">创建</button>
      <button class="btn" onclick="document.getElementById('${formId}').remove()">取消</button>
    </div>`;
  section.parentElement.insertBefore(div, section.nextSibling);
}

async function saveNewConnection(type) {
  const nameEl = document.getElementById('newName-'+type);
  if (!nameEl) return;
  const name = nameEl.value.trim();
  if (!name) return;
  const body = JSON.stringify({
    name: name,
    service_type: type,
    provider: document.getElementById('newProvider-'+type).value,
    base_url: document.getElementById('newURL-'+type).value.trim(),
    api_key: document.getElementById('newKey-'+type).value.trim(),
    model: type === 'llm' ? (document.getElementById('newModel-'+type)?.value.trim() || '') : '',
    voice: type === 'tts' ? (document.getElementById('newVoice-'+type)?.value.trim() || '') : '',
    is_active: true,
  });
  try {
    await fetch(API + '/api/model-connections', { method: 'POST', headers: {'Content-Type':'application/json'}, body });
    document.getElementById('form-new-' + type)?.remove();
    loadModelConnections();
  } catch(e) {}
}

let _addBtnsWired = false;
function wireModelAddBtns() {
  if (_addBtnsWired) return;
  const llmBtn = document.getElementById('btnAddLLM');
  const ttsBtn = document.getElementById('btnAddTTS');
  if (llmBtn) llmBtn.addEventListener('click', () => showAddForm('llm'));
  if (ttsBtn) ttsBtn.addEventListener('click', () => showAddForm('tts'));
  if (llmBtn && ttsBtn) _addBtnsWired = true;
}

async function loadSupportedServices() {
  try {
    const r = await fetch(API + '/api/model-connections/supported');
    _supportedServices = await r.json();
    renderSupportedServices();
  } catch(e) {}
}

function renderSupportedServices() {
  const el = document.getElementById('supportedServices');
  if (!el) return;
  const llmSvcs = _supportedServices.llm || [];
  const ttsSvcs = _supportedServices.tts || [];

  const svcCard = s => `<div class="svc-card">
      <div class="svc-provider">${esc(s.display)}</div>
      ${s.models && s.models.length ? '<div class="svc-models">模型: ' + s.models.map(m => '<span class="tag">'+esc(m)+'</span>').join(' ') + '</div>' : ''}
      ${s.voices ? '<div class="svc-voices">语音: ' + Object.entries(s.voices).flatMap(([lang, voices]) => voices.map(v => '<span class="tag">'+esc(v)+'</span>')).join(' ') + '</div>' : ''}
      <div class="svc-note">${esc(s.base_url || '(无需 API URL)')} | ${s.requires_api_key ? '需要 API Key' : '免费'}</div>
    </div>`;

  el.innerHTML = `<h3>📋 已支持的模型服务</h3>
    <div class="svc-grid">
      <div><h4 style="font-size:13px;color:var(--accent);margin-bottom:8px;">🤖 LLM</h4>${llmSvcs.map(svcCard).join('')}</div>
      <div><h4 style="font-size:13px;color:var(--accent);margin-bottom:8px;">🔊 TTS</h4>${ttsSvcs.map(svcCard).join('')}</div>
    </div>`;
}

// ---- Chat Tab (SSE 流式 纯问答) ----
let _chatInited = false;
function initChatTab() {
  if (_chatInited) return;
  _chatInited = true;
  setTimeout(() => document.getElementById('chatInput')?.focus(), 200);
}

function chatSendHint(el) {
  const input = document.getElementById('chatInput');
  if (input) { input.value = el.textContent; chatSendMsg(); }
}

async function chatSendMsg() {
  const input = document.getElementById('chatInput');
  const btn = document.getElementById('chatSendBtn');
  const msg = input?.value.trim();
  if (!msg || !input) return;
  input.value = '';
  input.disabled = true;
  if (btn) btn.disabled = true;

  const msgs = document.getElementById('chatMsgs');
  if (!msgs) return;

  // 用户消息气泡
  msgs.innerHTML += `<div class="chat-bubble user">
    <div class="chat-avatar">👤</div>
    <div class="chat-bubble-body"><div>${esc(msg)}</div></div>
  </div>`;

  // AI 流式气泡
  const botBubble = document.createElement('div');
  botBubble.className = 'chat-bubble bot streaming';
  botBubble.innerHTML = `<div class="chat-avatar">🤖</div>
    <div class="chat-bubble-body">
      <div class="chat-bubble-name">AI 新闻助手</div>
      <div class="stream-content"><span class="stream-cursor">▌</span></div>
    </div>`;
  msgs.appendChild(botBubble);
  msgs.scrollTop = msgs.scrollHeight;

  let fullText = '';
  let sourcesList = null;

  try {
    const r = await fetch(API + '/api/chat/send', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: msg})
    });
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const lines = buf.split('\n');
      buf = lines.pop() || '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const d = JSON.parse(line.slice(6));
          if (d.type === 'sources') sourcesList = d.sources;
          else if (d.type === 'token') {
            fullText += d.content;
            const contentEl = botBubble.querySelector('.stream-content');
            if (contentEl) contentEl.innerHTML = esc(fullText).replace(/\n/g,'<br>') + '<span class="stream-cursor">▌</span>';
          }
          msgs.scrollTop = msgs.scrollHeight;
        } catch(e) {}
      }
    }
  } catch(e) {
    fullText = '网络错误，请稍后重试。';
  }

  // 完成：移除光标，追加来源
  let finalHtml = esc(fullText).replace(/\n/g, '<br>') || '暂无回答。';
  if (sourcesList?.length) {
    finalHtml += `<div class="chat-sources">📰 参考: ${sourcesList.map(s=>esc(s.title)).join(' · ')}</div>`;
  }
  const bodyEl = botBubble.querySelector('.chat-bubble-body');
  if (bodyEl) bodyEl.innerHTML = `<div class="chat-bubble-name">AI 新闻助手</div><div>${finalHtml}</div>`;
  botBubble.classList.remove('streaming');
  msgs.scrollTop = msgs.scrollHeight;

  input.disabled = false;
  if (btn) btn.disabled = false;
  input.focus();
}

// ---- Utils ----
function esc(s) { if (!s) return ''; const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function escAttr(s) { if (!s) return ''; return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function fmt(s) { const m=Math.floor(s/60); return m+':'+String(Math.floor(s%60)).padStart(2,'0'); }
