/* ===== Sidebar section switching ===== */
const sidebarLinks = document.querySelectorAll('.sidebar nav a[data-section]');
const sections = document.querySelectorAll('.dash-section');

function showSection(name) {
    sections.forEach(s => s.style.display = 'none');
    sidebarLinks.forEach(a => a.classList.remove('active'));

    const target = document.getElementById('section-' + name);
    const link = document.querySelector(`a[data-section="${name}"]`);
    if (target) target.style.display = 'block';
    if (link) link.classList.add('active');
}

sidebarLinks.forEach(link => {
    link.addEventListener('click', e => {
        e.preventDefault();
        const section = link.dataset.section;
        window.location.hash = section;
        showSection(section);
    });
});

// Hash routing on load
const hash = window.location.hash.replace('#', '') || 'generate';
showSection(hash);
window.addEventListener('hashchange', () => {
    showSection(window.location.hash.replace('#', '') || 'generate');
});

/* ===== Input mode toggle (topic / url / toc) ===== */
const modeRadios = document.querySelectorAll('input[name="input_mode"]');
const topicFields = document.getElementById('topic-fields');
const urlFields = document.getElementById('url-fields');
const tocFields = document.getElementById('toc-fields');

function updateInputMode() {
    const mode = document.querySelector('input[name="input_mode"]:checked')?.value;
    topicFields.style.display = mode === 'topic' ? 'block' : 'none';
    urlFields.style.display = mode === 'url' ? 'block' : 'none';
    tocFields.style.display = mode === 'toc' ? 'block' : 'none';
}

modeRadios.forEach(r => r.addEventListener('change', updateInputMode));
updateInputMode();

/* ===== Provider/model dynamic select ===== */
const providerSelect = document.getElementById('provider-select');
const modelSelect = document.getElementById('model-select');

function updateModels() {
    const provider = providerSelect.value;
    const models = providerModels[provider] || [];
    modelSelect.innerHTML = models.map(m =>
        `<option value="${m}">${m}</option>`
    ).join('');
    if (!models.length && provider === 'ollama') {
        modelSelect.innerHTML = '<option value="">Ollama 서버 확인 필요</option>';
    }
}

providerSelect.addEventListener('change', updateModels);
updateModels();

/* ===== Generate form submission via fetch ===== */
const generateForm = document.getElementById('generate-form');
const generateResult = document.getElementById('generate-result');
const generateMsg = document.getElementById('generate-msg');

generateForm.addEventListener('submit', async e => {
    e.preventDefault();
    const formData = new FormData(generateForm);

    const mode = formData.get('input_mode');
    if (mode === 'topic' && !formData.get('topic')?.trim()) {
        alert('주제를 입력해주세요.');
        return;
    }
    if (mode === 'url' && !formData.get('input_url')?.trim()) {
        alert('URL을 입력해주세요.');
        return;
    }
    if (mode === 'url') {
        const urlTopic = formData.get('url_topic')?.trim();
        if (urlTopic) formData.set('topic', urlTopic);
    }
    if (mode === 'toc' && !formData.get('toc_file')) {
        alert('목차 파일을 선택해주세요.');
        return;
    }

    generateForm.querySelector('button[type="submit"]').setAttribute('aria-busy', 'true');

    try {
        const res = await fetch('/pipeline/run', {
            method: 'POST',
            body: formData,
            headers: { 'Accept': 'application/json' },
        });
        const data = await res.json();
        if (data.job_id) {
            generateResult.style.display = 'block';
            generateMsg.innerHTML = `작업이 시작되었습니다. <a href="#jobs" onclick="showJob('${data.job_id}')">로그 보기</a>`;
            loadJobs();
        }
    } catch (err) {
        alert('오류: ' + err.message);
    } finally {
        generateForm.querySelector('button[type="submit"]').removeAttribute('aria-busy');
    }
});

/* ===== Jobs list ===== */
async function loadJobs() {
    const res = await fetch('/pipeline/jobs');
    const jobs = await res.json();
    const el = document.getElementById('jobs-list');
    if (!jobs.length) {
        el.innerHTML = '<p>실행 기록 없음</p>';
        return;
    }
    el.innerHTML = '<table><thead><tr><th>모델</th><th>입력</th><th>상태</th><th>시작</th><th></th></tr></thead><tbody>' +
        jobs.map(j => `<tr>
            <td>${j.model}</td>
            <td>${j.source || j.toc_file}</td>
            <td><mark>${j.status}</mark></td>
            <td>${new Date(j.started_at).toLocaleString('ko')}</td>
            <td><a href="#jobs" onclick="showJob('${j.id}')">로그</a></td>
        </tr>`).join('') +
        '</tbody></table>';
}

loadJobs();

/* ===== Job log viewer (inline) ===== */
let currentWs = null;

function showJob(jobId) {
    showSection('jobs');
    window.location.hash = 'jobs';
    const viewer = document.getElementById('job-viewer');
    const title = document.getElementById('job-viewer-title');
    const logEl = document.getElementById('log');
    const statusMsg = document.getElementById('status-msg');

    viewer.style.display = 'block';
    title.textContent = '작업 로그: ' + jobId;
    logEl.textContent = '';
    statusMsg.textContent = '';

    if (currentWs) {
        currentWs.close();
        currentWs = null;
    }

    connectLog(jobId);
}

/* ===== TOC delete ===== */
async function deleteToc(filename) {
    if (!confirm(`"${filename}" 을(를) 삭제하시겠습니까?`)) return;
    await fetch(`/toc/${filename}`, { method: 'DELETE' });
    location.reload();
}

/* ===== Book delete ===== */
async function deleteBook(slug, title) {
    if (!confirm(`"${title}" 을(를) 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return;
    await fetch(`/outputs/${slug}`, { method: 'DELETE' });
    location.reload();
}
