// AI News Podcast - 前端应用逻辑

const API_BASE = '';
const STATE = {
    currentTab: 'news',
    newsPage: 1,
    isPlaying: false,
    volume: 0.8,
    refreshInterval: null,
};

// === 初始化 ===
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initPlayer();
    initPipeline();
    initFilters();
    loadNews();
    startStatusPolling();
});

// === Tab 切换 ===
function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            STATE.currentTab = tab.dataset.tab;
            document.getElementById(`tab-${STATE.currentTab}`).classList.add('active');

            if (STATE.currentTab === 'news') loadNews();
            else if (STATE.currentTab === 'podcasts') loadPodcasts();
            else if (STATE.currentTab === 'playlists') loadPlaylists();
            else if (STATE.currentTab === 'sources') loadSources();
        });
    });
}

// === 播放器 ===
function initPlayer() {
    const audio = document.getElementById('audioPlayer');
    audio.volume = STATE.volume;

    document.getElementById('btnPlay').addEventListener('click', togglePlay);
    document.getElementById('volumeSlider').addEventListener('input', (e) => {
        STATE.volume = e.target.value / 100;
        audio.volume = STATE.volume;
    });

    // 监听音频事件
    audio.addEventListener('waiting', () => updatePlayState(true, '缓冲中...'));
    audio.addEventListener('playing', () => {
        updatePlayState(true, '正在播放');
        document.getElementById('visualizer').classList.add('active');
    });
    audio.addEventListener('pause', () => {
        document.getElementById('visualizer').classList.remove('active');
    });
    audio.addEventListener('error', () => {
        updatePlayState(false, '连接失败，请重试');
        document.getElementById('visualizer').classList.remove('active');
    });

    // 定期更新当前播放标题
    setInterval(updateCurrentTrack, 5000);
}

async function updateCurrentTrack() {
    if (!STATE.isPlaying) return;
    try {
        const resp = await fetch(`${API_BASE}/api/podcasts/current`);
        const data = await resp.json();
        if (data.podcast && data.podcast.title) {
            document.getElementById('playerTitle').textContent = data.podcast.title;
            document.getElementById('playerSource').textContent = data.playlist_name || '';
        }
        document.getElementById('queueLength').textContent = data.queue_length || '0';
    } catch (e) { /* ignore */ }
}

function togglePlay() {
    const audio = document.getElementById('audioPlayer');
    if (STATE.isPlaying) {
        audio.pause();
        updatePlayState(false, '已暂停');
    } else {
        // 先检查是否有可用内容
        fetch(`${API_BASE}/stream/status`).then(r => r.json()).then(status => {
            if (status.queue_length === 0 && status.queue_duration === 0) {
                document.getElementById('playerTitle').textContent = '队列为空，等待内容生成...';
                document.getElementById('playerSource').textContent = '流水线运行中，请稍候';
            }
        }).catch(() => {});

        audio.src = `${API_BASE}/stream`;
        updatePlayState(true, '正在连接...');
        audio.load();
        audio.play().then(() => {
            updatePlayState(true, '正在播放');
            document.getElementById('visualizer').classList.add('active');
        }).catch(err => {
            console.error('Stream play failed:', err);
            updatePlayState(false, '播放失败，请先触发采集生成内容');
        });
    }
}

function updatePlayState(playing, text) {
    STATE.isPlaying = playing;
    document.getElementById('playIcon').textContent = playing ? '⏸' : '▶';
    document.getElementById('statusText').textContent = text;
    const dot = document.getElementById('statusDot');
    dot.className = 'status-dot';
    if (playing) dot.classList.add('playing');
    else dot.classList.add('buffering');
}

// === 流水线控制 ===
function initPipeline() {
    document.getElementById('btnTrigger').addEventListener('click', async () => {
        const btn = document.getElementById('btnTrigger');
        btn.disabled = true;
        btn.textContent = '采集中...';
        try {
            const resp = await fetch(`${API_BASE}/api/pipeline/trigger`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ force: true }),
            });
            const data = await resp.json();
            if (data.success) {
                btn.textContent = '采集完成 ✓';
                setTimeout(() => { btn.textContent = '立即采集'; btn.disabled = false; }, 3000);
                loadNews();
            } else {
                btn.textContent = '采集失败, 重试';
                btn.disabled = false;
            }
        } catch (err) {
            btn.textContent = '网络错误';
            btn.disabled = false;
        }
    });
}

function startStatusPolling() {
    STATE.refreshInterval = setInterval(async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/news/stats`);
            const stats = await resp.json();
            document.getElementById('newsCount').textContent = stats.total_news || '--';
            document.getElementById('todayCount').textContent = stats.today_news || '--';
        } catch (e) { /* ignore */ }

        try {
            const resp = await fetch(`${API_BASE}/stream/status`);
            const status = await resp.json();
            document.getElementById('queueLength').textContent = status.queue_length || '0';
            document.getElementById('listenerCount').textContent = status.listeners || '0';
        } catch (e) { /* ignore */ }
    }, 10000);
}

// === 筛选器 ===
function initFilters() {
    document.getElementById('sourceFilter').addEventListener('change', () => {
        STATE.newsPage = 1;
        loadNews();
    });
    document.getElementById('scoreFilter').addEventListener('change', () => {
        STATE.newsPage = 1;
        loadNews();
    });

    // 动态填充来源下拉菜单
    fetch(`${API_BASE}/api/sources`).then(r => r.json()).then(data => {
        const sel = document.getElementById('sourceFilter');
        if (data.items) {
            data.items.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.name;
                opt.textContent = s.name;
                sel.appendChild(opt);
            });
        }
    }).catch(() => {});
}

// === 新闻源管理 ===
async function loadSources() {
    try {
        const resp = await fetch(`${API_BASE}/api/sources`);
        const data = await resp.json();
        renderSourceList(data.items || []);
    } catch (err) {
        document.getElementById('sourceList').innerHTML = '<div class="empty-state">加载失败</div>';
    }

    document.getElementById('btnAddSource').onclick = async () => {
        const name = document.getElementById('srcName').value.trim();
        const type = document.getElementById('srcType').value;
        const url = document.getElementById('srcUrl').value.trim();
        const lang = document.getElementById('srcLang').value;
        const keywords = document.getElementById('srcKeywords').value.trim();
        if (!name || !url) { alert('请填写名称和URL'); return; }

        try {
            const resp = await fetch(`${API_BASE}/api/sources`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, type, url, language: lang, keywords }),
            });
            if (resp.ok) {
                document.getElementById('srcName').value = '';
                document.getElementById('srcUrl').value = '';
                document.getElementById('srcKeywords').value = '';
                loadSources();
            } else {
                const err = await resp.json();
                alert(err.detail || '添加失败');
            }
        } catch (e) { alert('网络错误'); }
    };
}

function renderSourceList(items) {
    const container = document.getElementById('sourceList');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无新闻源，请添加</div>';
        return;
    }
    container.innerHTML = items.map(s => `
        <div class="news-item source-item">
            <div class="news-content">
                <div class="news-title">
                    ${s.is_enabled ? '🟢' : '⚫'} ${escapeHtml(s.name)}
                    <span style="font-size:12px;color:var(--text-muted)">[${s.type}] ${s.language}</span>
                </div>
                <div class="news-summary" style="font-size:11px;word-break:break-all">${escapeHtml(s.url)}</div>
                <div class="news-meta">
                    <span>优先级: ${s.priority}</span>
                    ${s.keywords ? `<span>关键词: ${escapeHtml(s.keywords)}</span>` : ''}
                    <button class="btn-small" onclick="toggleSource('${escapeHtml(s.name)}', ${s.is_enabled ? 0 : 1})">
                        ${s.is_enabled ? '禁用' : '启用'}
                    </button>
                    <button class="btn-small btn-danger" onclick="deleteSource('${escapeHtml(s.name)}')">删除</button>
                </div>
            </div>
        </div>
    `).join('');
}

async function toggleSource(name, enable) {
    await fetch(`${API_BASE}/api/sources/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_enabled: !!enable }),
    });
    loadSources();
}

async function deleteSource(name) {
    if (!confirm(`确定删除新闻源 "${name}"？`)) return;
    await fetch(`${API_BASE}/api/sources/${encodeURIComponent(name)}`, { method: 'DELETE' });
    loadSources();
}

// === 加载新闻列表 ===
async function loadNews(page = 1) {
    const source = document.getElementById('sourceFilter').value;
    const minScore = document.getElementById('scoreFilter').value;
    STATE.newsPage = page;

    const params = new URLSearchParams({ page, page_size: 20 });
    if (source) params.set('source', source);
    if (minScore) params.set('min_score', minScore);

    try {
        const resp = await fetch(`${API_BASE}/api/news?${params}`);
        const data = await resp.json();
        renderNewsList(data.items);
        renderPagination(data.total, data.page, data.page_size, 'news');
    } catch (err) {
        document.getElementById('newsList').innerHTML = '<div class="empty-state">加载失败，请检查后端服务</div>';
    }
}

function renderNewsList(items) {
    const container = document.getElementById('newsList');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无新闻，点击「立即采集」获取最新AI新闻</div>';
        return;
    }

    container.innerHTML = items.map(item => {
        const score = item.importance_score || 0;
        const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-medium' : 'score-low';
        const sourceLabel = item.source || 'Unknown';
        const timeLabel = item.collected_at ? new Date(item.collected_at).toLocaleString('zh-CN') : '';

        return `
        <div class="news-item" onclick="window.open('${escapeHtml(item.url)}', '_blank')">
            <div class="news-score ${scoreClass}">${score}</div>
            <div class="news-content">
                <div class="news-title">${escapeHtml(item.title)}</div>
                ${item.summary ? `<div class="news-summary">${escapeHtml(item.summary)}</div>` : ''}
                <div class="news-meta">
                    <span>📰 ${escapeHtml(sourceLabel)}</span>
                    ${timeLabel ? `<span>🕐 ${timeLabel}</span>` : ''}
                    ${item.importance_reason ? `<span>💡 ${escapeHtml(item.importance_reason)}</span>` : ''}
                </div>
            </div>
        </div>`;
    }).join('');
}

// === 加载播客列表 ===
async function loadPodcasts(page = 1) {
    try {
        const resp = await fetch(`${API_BASE}/api/podcasts?page=${page}&page_size=20`);
        const data = await resp.json();
        renderPodcastList(data.items);
    } catch (err) {
        document.getElementById('podcastList').innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

function renderPodcastList(items) {
    const container = document.getElementById('podcastList');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无播客历史</div>';
        return;
    }

    container.innerHTML = items.map(item => {
        const statusIcon = item.status === 'completed' ? '✅' : item.status === 'pending' ? '⏳' : '❌';
        const duration = item.audio_duration ? formatDuration(item.audio_duration) : '--';
        return `
        <div class="news-item">
            <div class="news-score ${item.importance_level >= 7 ? 'score-high' : item.importance_level >= 5 ? 'score-medium' : 'score-low'}">${item.importance_level}</div>
            <div class="news-content">
                <div class="news-title">${escapeHtml(item.title)}</div>
                <div class="news-meta">
                    <span>${statusIcon} ${item.status}</span>
                    <span>⏱ ${duration}</span>
                    ${item.audio_path ? `<a href="/api/podcasts/${item.id}/audio" class="download-link">⬇ 下载</a>` : ''}
                </div>
            </div>
        </div>`;
    }).join('');
}

// === 加载播单列表 ===
async function loadPlaylists() {
    try {
        const resp = await fetch(`${API_BASE}/api/podcasts/current`);
        const data = await resp.json();
        document.getElementById('playlistList').innerHTML = `
            <div class="news-item">
                <div class="news-content">
                    <div class="news-title">当前播放队列</div>
                    <div class="news-meta">
                        <span>队列长度: ${data.queue_length || 0}</span>
                        <span>状态: ${data.status || 'idle'}</span>
                    </div>
                </div>
            </div>
        `;
    } catch (err) {
        document.getElementById('playlistList').innerHTML = '<div class="empty-state">暂无播单</div>';
    }
}

// === 分页 ===
function renderPagination(total, page, pageSize, type) {
    const totalPages = Math.ceil(total / pageSize);
    const container = document.getElementById('newsPagination');
    if (totalPages <= 1) { container.innerHTML = ''; return; }

    let html = '';
    for (let i = 1; i <= Math.min(totalPages, 10); i++) {
        html += `<button class="${i === page ? 'active' : ''}" onclick="loadNews(${i})">${i}</button>`;
    }
    container.innerHTML = html;
}

// === 工具函数 ===
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatDuration(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}
