(() => {
  const chat = document.getElementById('chat');
  const welcome = document.getElementById('welcome');
  const form = document.getElementById('form');
  const input = document.getElementById('input');
  const sendBtn = document.getElementById('send');
  const metaEl = document.getElementById('meta');
  const healthDot = document.getElementById('health-dot');
  const healthText = document.getElementById('health-text');

  let threadId = null;

  /* ---------- Minimal markdown rendering (HTML-safe) ---------- */
  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function renderTable(rows) {
    const cells = rows.map((r) => {
      let s = r.trim();
      if (s.startsWith('|')) s = s.slice(1);
      if (s.endsWith('|')) s = s.slice(0, -1);
      return s.split('|').map((c) => c.trim());
    });

    let sepIdx = -1;
    for (let i = 0; i < cells.length; i++) {
      if (cells[i].length && cells[i].every((c) => /^:?-+:?$/.test(c))) {
        sepIdx = i;
        break;
      }
    }

    let html = '<div class="table-wrap"><table>';
    if (sepIdx >= 0) {
      html += '<thead><tr>' + cells.slice(0, sepIdx)
        .map((row) => row.map((c) => `<th>${c}</th>`).join(''))
        .join('</tr><tr>') + '</tr></thead>';
      const body = cells.slice(sepIdx + 1);
      if (body.length) {
        html += '<tbody>' + body
          .map((row) => '<tr>' + row.map((c) => `<td>${c}</td>`).join('') + '</tr>')
          .join('') + '</tbody>';
      }
    } else {
      html += '<tbody>' + cells
        .map((row) => '<tr>' + row.map((c) => `<td>${c}</td>`).join('') + '</tr>')
        .join('') + '</tbody>';
    }
    html += '</table></div>';
    return html;
  }

  function renderMarkdown(text) {
    const lines = escapeHtml(text).split('\n');
    let html = '';
    let inList = false;
    let inCode = false;
    let tableRows = null;

    const closeList = () => { if (inList) { html += '</ul>'; inList = false; } };
    const closeCode = () => { if (inCode) { html += '</pre>'; inCode = false; } };

    for (const raw of lines) {
      const line = raw.trimEnd();

      if (line.trim().startsWith('```')) {
        closeList();
        if (inCode) { closeCode(); } else { html += '<pre>'; inCode = true; }
        continue;
      }

      if (inCode) { html += line + '\n'; continue; }

      // GFM tables
      if (/^\s*\|/.test(line)) {
        closeList();
        if (!tableRows) tableRows = [];
        tableRows.push(line);
        continue;
      }
      if (tableRows) {
        html += renderTable(tableRows);
        tableRows = null;
      }

      if (/^#{1,3}\s/.test(line.trim())) {
        closeList();
        const level = line.trim().match(/^(#+)/)[1].length;
        const content = line.trim().replace(/^#+\s*/, '');
        html += `<h${level}>${content}</h${level}>`;
        continue;
      }

      if (/^\s*[-*]\s+/.test(line)) {
        if (!inList) { html += '<ul>'; inList = true; }
        html += `<li>${line.trim().replace(/^\s*[-*]\s+/, '')}</li>`;
        continue;
      }

      if (/^\s*\d+\.\s+/.test(line)) {
        if (!inList) { html += '<ul>'; inList = true; }
        html += `<li>${line.trim().replace(/^\s*\d+\.\s+/, '')}</li>`;
        continue;
      }

      closeList();

      if (line.trim() === '') {
        html += '<p></p>';
        continue;
      }

      const inline = line
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
      html += `<p>${inline}</p>`;
    }

    closeList();
    closeCode();
    if (tableRows) { html += renderTable(tableRows); }
    return html;
  }

  /* ---------- Message helpers ---------- */
  function addUserMessage(text) {
    const el = document.createElement('div');
    el.className = 'msg user';
    el.innerHTML = `<div class="bubble"></div>`;
    el.querySelector('.bubble').textContent = text;
    chat.appendChild(el);
    scrollDown();
    return el;
  }

  function addTyping() {
    const el = document.createElement('div');
    el.className = 'msg assistant typing';
    el.innerHTML = `<div class="bubble"><span></span><span></span><span></span></div>`;
    chat.appendChild(el);
    scrollDown();
    return el;
  }

  function addAssistantMessage(data) {
    const el = document.createElement('div');
    el.className = 'msg assistant';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = renderMarkdown(data.answer);

    const details = [];
    if (data.flight_results) details.push(['✈️ Flight results', data.flight_results]);
    if (data.hotel_results) details.push(['🏨 Hotel results', data.hotel_results]);
    if (data.itinerary) details.push(['📅 Itinerary', data.itinerary]);

    for (const [label, content] of details) {
      const det = document.createElement('details');
      det.className = 'detail';
      det.innerHTML = `<summary>${label}<span class="caret">▸</span></summary><div class="detail-body"></div>`;
      det.querySelector('.detail-body').textContent = content;
      bubble.appendChild(det);
    }

    el.appendChild(bubble);

    const parts = [];
    if (data.thread_id) parts.push(`thread ${data.thread_id.slice(0, 8)}…`);
    if (typeof data.llm_calls === 'number') parts.push(`${data.llm_calls} LLM calls`);
    if (parts.length) {
      const meta = document.createElement('div');
      meta.className = 'msg-meta';
      meta.textContent = parts.join(' · ');
      el.appendChild(meta);
    }

    chat.appendChild(el);
    scrollDown();
    return el;
  }

  function addError(message) {
    const el = document.createElement('div');
    el.className = 'msg assistant';
    el.innerHTML = `<div class="bubble" style="color:#b91c1c"></div>`;
    el.querySelector('.bubble').textContent = `Something went wrong: ${message}`;
    chat.appendChild(el);
    scrollDown();
  }

  function scrollDown() {
    chat.scrollTop = chat.scrollHeight;
  }

  function setMeta(text, isError = false) {
    metaEl.textContent = text;
    metaEl.classList.toggle('error-meta', isError);
  }

  /* ---------- API ---------- */
  async function sendMessage(text) {
    welcome.style.display = 'none';
    addUserMessage(text);
    const typing = addTyping();
    sendBtn.disabled = true;
    setMeta('Planning your trip…');

    try {
      const res = await fetch('/api/travel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: threadId }),
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || `Request failed (${res.status})`);
      }

      threadId = data.thread_id || threadId;
      typing.remove();
      addAssistantMessage(data);
      setMeta('');
    } catch (err) {
      typing.remove();
      addError(err.message);
      setMeta(err.message, true);
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  /* ---------- Auto-grow textarea ---------- */
  function autoGrow() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  }
  input.addEventListener('input', autoGrow);

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  });

  function submit() {
    const text = input.value.trim();
    if (!text || sendBtn.disabled) return;
    input.value = '';
    autoGrow();
    sendMessage(text);
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    submit();
  });

  /* Suggestion chips */
  document.querySelectorAll('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      input.value = chip.textContent.trim();
      autoGrow();
      submit();
    });
  });

  /* ---------- Health check ---------- */
  async function checkHealth() {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        healthDot.className = 'dot ok';
        healthText.textContent = 'online';
      } else {
        throw new Error();
      }
    } catch {
      healthDot.className = 'dot bad';
      healthText.textContent = 'offline';
    }
  }

  checkHealth();
  setInterval(checkHealth, 15000);
  input.focus();
})();
