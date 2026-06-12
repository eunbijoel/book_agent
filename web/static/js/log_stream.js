function connectLog(jobId) {
    const logEl = document.getElementById('log');
    const statusEl = document.getElementById('status-msg');
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/pipeline/ws/${jobId}`);

    ws.onmessage = function(event) {
        if (event.data === '[DONE]') {
            statusEl.innerHTML = '<mark>완료</mark>';
            ws.close();
            return;
        }
        logEl.textContent += event.data + '\n';
        logEl.scrollTop = logEl.scrollHeight;
    };

    ws.onerror = function() {
        statusEl.innerHTML = '<mark>연결 오류</mark>';
    };

    ws.onclose = function() {
        if (!statusEl.innerHTML) {
            statusEl.innerHTML = '<mark>연결 종료</mark>';
        }
    };
}
