const usernameInput = document.getElementById('username-input');
const nicheInput    = document.getElementById('niche-input');
const limitInput    = document.getElementById('limit-input');
const promptInput   = document.getElementById('prompt-input');
const checkBtn      = document.getElementById('check-btn');
const resultArea    = document.getElementById('result-area');

usernameInput.addEventListener('keydown', e => { if (e.key === 'Enter') doCheck(); });
nicheInput.addEventListener('keydown', e => { if (e.key === 'Enter') doCheck(); });

function togglePrompt() {
  const toggle = document.getElementById('prompt-toggle');
  const box = document.getElementById('prompt-box');
  toggle.classList.toggle('open');
  box.classList.toggle('visible');
}

async function doCheck(overrideUsername) {
  const username = (overrideUsername || usernameInput.value).trim().toLowerCase();
  const niche    = nicheInput.value.trim().toLowerCase();
  const limit    = Math.max(1, Math.min(25, parseInt(limitInput.value) || 10));
  const prompt   = promptInput.value.trim();

  if (!username && !niche && !prompt) {
    usernameInput.focus();
    usernameInput.style.borderColor = 'var(--danger)';
    nicheInput.style.borderColor = 'var(--danger)';
    setTimeout(() => {
      usernameInput.style.borderColor = '';
      nicheInput.style.borderColor = '';
    }, 1500);
    return;
  }

  if (overrideUsername) usernameInput.value = username;

  checkBtn.disabled = true;
  checkBtn.innerHTML = '<span class="spinner"></span> Generating suggestions\u2026';
  resultArea.className = '';
  resultArea.innerHTML = '';

  try {
    const params = new URLSearchParams();
    if (username) params.set('username', username);
    if (niche) params.set('niche', niche);
    params.set('limit', limit);
    if (prompt) params.set('prompt', prompt);

    const resp = await fetch('/smart-check?' + params.toString());
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || 'HTTP ' + resp.status);
    }
    const data = await resp.json();
    renderSmartResult(data);
  } catch (err) {
    resultArea.innerHTML = '<div class="error-banner">\u26a0\ufe0f ' + err.message + '</div>';
    resultArea.className = 'visible';
  } finally {
    checkBtn.disabled = false;
    checkBtn.innerHTML = '\ud83d\udd0d\u00a0\u00a0Generate Suggestions';
  }
}

function renderSmartResult(data) {
  let html = '';

  // 1. Username format validation banner (user's exact username)
  if (data.check_result) {
    const r = data.check_result;
    const isValid = r.status === 'valid';
    const cls = isValid ? 'valid-format' : 'invalid';
    const icon = isValid ? '\u2705' : '\u26a0\ufe0f';
    const label = isValid
      ? 'Valid Format \u2014 Check availability in WhatsApp app'
      : 'Invalid Format';

    html += '<div class="check-banner ' + cls + '">';
    html += '  <div class="status-icon">' + icon + '</div>';
    html += '  <div class="check-info">';
    html += '    <div class="check-username">@' + r.username + '</div>';
    html += '    <div class="check-status">' + label + '</div>';
    if (r.error) {
      html += '    <div class="check-meta">' + r.error + '</div>';
    }
    if (isValid) {
      html += '    <div class="check-meta">Open WhatsApp \u2192 Settings \u2192 Account \u2192 Username to check if it\'s available</div>';
    }
    html += '  </div>';
    html += '</div>';
  }

  // 2. AI-generated suggestions
  if (data.suggestions && data.suggestions.length > 0) {
    html += '<div class="suggestion-block">';
    html += '  <h3>\u2728 AI Suggestions (' + data.suggestions.length + ')</h3>';
    html += '  <div class="suggestions-grid">';
    data.suggestions.forEach(function(item) {
      html += "<div class='suggestion-chip' onclick=\"copyUsername('" + item.username + "', this)\" title='Copy @" + item.username + "'>";
      html += "  <span class='name'>" + item.username + "</span>";
      html += "  <span class='copy-btn'>\ud83d\udccb COPY</span>";
      html += "</div>";
    });
    html += '  </div>';
    html += '</div>';
  }

  // Latency info
  if (data.suggestion_latency_ms) {
    html += '<div class="latency-note">AI generation: ' + data.suggestion_latency_ms + 'ms</div>';
  }

  // Disclaimer
  html += '<div class="disclaimer">\u26a0\ufe0f These are AI-generated username <strong>ideas</strong>, not confirmed availability. Usernames may already be taken. Always verify in the <strong>WhatsApp app</strong> (Settings \u2192 Account \u2192 Username). Not affiliated with WhatsApp or Meta.</div>';

  if (!data.suggestions?.length && !data.check_result) {
    html = '<div class="error-banner">No results. Try a different username, niche, or prompt.</div>';
  }

  resultArea.innerHTML = html;
  resultArea.className = 'visible';
}

function copyUsername(username, el) {
  navigator.clipboard.writeText(username).then(function() {
    const copyBtn = el.querySelector('.copy-btn');
    const origText = copyBtn.textContent;
    copyBtn.textContent = '\u2705 Copied!';
    el.classList.add('copied');
    setTimeout(function() {
      copyBtn.textContent = origText;
      el.classList.remove('copied');
    }, 1500);
  });
}

function fillNiche(niche) {
  nicheInput.value = niche;
  usernameInput.value = '';
  // Scroll to the tool section smoothly
  document.querySelector('.search-card').scrollIntoView({ behavior: 'smooth', block: 'center' });
  // Brief delay so user sees the scroll, then trigger generation
  setTimeout(function() {
    doCheck();
  }, 400);
}
