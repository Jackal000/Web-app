// Загрузка Chart.js только на дашборде
if ((window.location.pathname === '/' || window.location.pathname === '/dashboard') && typeof Chart === 'undefined') {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1';
    script.onload = () => initCharts();
    document.head.appendChild(script);
} else if (typeof Chart !== 'undefined') {
    initCharts();
}

document.addEventListener('DOMContentLoaded', () => {
    const configEl = document.getElementById('app-config-data');
    const cfg = configEl ? JSON.parse(configEl.textContent) : {};

    try {
        // Плотность таблицы
        if (cfg.tableDensity === 'compact') {
            document.querySelectorAll('.table').forEach(t => t.classList.add('table-sm'));
        }
        if (cfg.showIp === 'false') document.querySelectorAll('.col-ip, .th-ip').forEach(e => e.classList.add('col-ip-hidden'));

        // Автообновление
        if (cfg.autoRefresh === true && typeof cfg.refreshInterval === 'number' && cfg.refreshInterval > 0) {
            if (window.location.pathname === '/' || window.location.pathname === '/dashboard') {
                setInterval(() => fetch('/api/simulate_action').finally(() => location.reload()), cfg.refreshInterval * 1000);
            }
        }

        // Системная инфо
        const sysEl = document.getElementById('sysInfo');
        if(sysEl) fetch('/api/system_info').then(r=>r.json()).then(d => sysEl.innerHTML = `<div>⏱ Аптайм: <b>${d.up}</b></div><div>📝 Записей: <b>${d.logs}</b></div><div>👥 Пользователей: <b>${d.users}</b></div>`);

        // Клики
        document.getElementById('logsBody')?.addEventListener('click', e => {
            const r = e.target.closest('tr'); if(r?.dataset.logId) showLogModal(r.dataset.logId);
        });
        document.querySelector('#page-content-wrapper')?.addEventListener('click', e => {
            if(e.target.closest('.interactive-card')) filterLogs(e.target.closest('.interactive-card').dataset.filter);
        });

        // Оповещения
        if (cfg.soundAlert === true && cfg.errorCount > 0) {
            try { const c = new (window.AudioContext||window.webkitAudioContext)(), o = c.createOscillator(); o.type='sine'; o.frequency.setValueAtTime(440,c.currentTime); o.connect(c.destination); o.start(); o.stop(c.currentTime+0.15); } catch(e){}
        }
        if (cfg.browserNotify === true && "Notification" in window && Notification.permission !== "granted") Notification.requestPermission();
        if (cfg.browserNotify === true && cfg.errorCount > 0 && "Notification" in window && Notification.permission === "granted") {
            new Notification("UserLog Dashboard", { body: `Обнаружено ${cfg.errorCount} критических ошибок!`, icon: "/static/favicon.ico" });
        }
    } catch (err) { console.error('❌ Init error:', err); }
});

function showLogModal(id) {
    fetch(`/api/logs/${id}`).then(r=>r.json()).then(d => {
        document.getElementById('logModalContent').innerHTML = `<div class="modal-header"><h5 class="modal-title">Детали лога #${id}</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><p><b>Пользователь:</b> ${d.user}</p><p><b>ФИО:</b> ${d.full_name}</p><p><b>Должность:</b> ${d.position}</p><hr><p><b>Время:</b> ${d.time}</p><p><b>Действие:</b> ${d.action}</p><p><b>Описание:</b> ${d.desc}</p><p><b>IP:</b> ${d.ip}</p></div><div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button></div>`;
        new bootstrap.Modal(document.getElementById('logModal')).show();
    });
}

function filterLogs(status) {
    fetch(`/api/logs/filter/${status}`).then(r=>r.json()).then(data => {
        const tb = document.getElementById('logsBody'); tb.innerHTML = '';
        data.forEach(r => {
            const isErr = r.type.includes('ERR')||r.type.includes('DENIED');
            const isWarn = r.type.includes('WARN');
            const bc = isErr ? 'bg-danger' : (isWarn ? 'bg-warning text-dark' : 'bg-success');
            const bt = isErr ? 'Ошибка' : (isWarn ? 'Внимание' : 'Успешно');
            tb.innerHTML += `<tr data-log-id="${r.id}" style="cursor:pointer"><td class="ps-4 text-muted">${r.time}</td><td>${r.user}</td><td>${r.desc}</td><td class="col-ip"><code>${r.ip || '—'}</code></td><td class="col-role"><span class="badge ${bc} rounded-pill">${bt}</span></td></tr>`;
        });
    });
}

function initCharts() {
    const configEl = document.getElementById('app-config-data');
    const cfg = configEl ? JSON.parse(configEl.textContent) : {};
    const isDark = cfg.theme === 'dark';
    const lc = isDark ? '#e0e0e0' : '#212529';
    const gc = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)';

    if (!window.CHART_TYPES || !window.CHART_TIMELINE) return;

    try {
        // 1. Круговая диаграмма
        const ctx1 = document.getElementById('chartTypes');
        if (ctx1 && typeof Chart !== 'undefined') {
            new Chart(ctx1, {
                type: 'doughnut',
                data: { // ✅ ВОТ ОНО, КЛЮЧОВОЕ СЛОВО
                    labels: window.CHART_TYPES.labels,
                    datasets: [{
                        data: window.CHART_TYPES.data,
                        backgroundColor: ['#0d6efd', '#198754', '#dc3545', '#ffc107', '#0dcaf0', '#6f42c1', '#fd7e14', '#20c997', '#6c757d', '#d63384', '#3d5a80', '#ee6c4d', '#98c1d9', '#293241', '#e0fbfc']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { boxWidth: 12, color: lc } } }
                }
            });
        }

        // 2. Линейный график
        const ctx2 = document.getElementById('chartTimeline');
        if (ctx2 && typeof Chart !== 'undefined') {
            new Chart(ctx2, {
                type: 'line',
                data: { // ✅ И ТУТ ТОЖЕ
                    labels: window.CHART_TIMELINE.labels,
                    datasets: [{
                        label: 'Записей',
                        data: window.CHART_TIMELINE.data,
                        borderColor: '#0d6efd',
                        backgroundColor: 'rgba(13,110,253,0.15)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, ticks: { stepSize: 1, color: lc }, grid: { color: gc } },
                        x: { ticks: { color: lc }, grid: { color: gc } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
    } catch (err) { console.error('❌ Chart error:', err); }
}