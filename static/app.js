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

function stepLimit(amount) {
  let val = parseInt(limitInput.value) || 10;
  val += amount;
  if (val < 1) val = 1;
  if (val > 25) val = 25;
  limitInput.value = val;
}

function scrollToSection(id) {
  const el = document.getElementById(id);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    
    // Update active nav button
    document.querySelectorAll('.bottom-nav .nav-item').forEach(btn => {
      btn.classList.remove('active');
    });
    
    let btnId = '';
    if (id === 'generator-section') btnId = 'nav-generator';
    else if (id === 'browse-section') btnId = 'nav-browse';
    else if (id === 'result-area') btnId = 'nav-results';
    
    const activeBtn = document.getElementById(btnId);
    if (activeBtn) activeBtn.classList.add('active');
  }
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
    checkBtn.innerHTML = '<svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg><span class="btn-text">Generate Suggestions</span>';
  }
}

function renderSmartResult(data) {
  let html = '';

  // 1. Username format validation banner (user's exact username)
  if (data.check_result) {
    const r = data.check_result;
    const isValid = r.status === 'valid';
    const cls = isValid ? 'valid-format' : 'invalid';
    const icon = isValid
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>'
      : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
    const label = isValid
      ? 'Valid Format &mdash; Check availability in WhatsApp app'
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
      html += '    <div class="check-meta">Open WhatsApp &rarr; Settings &rarr; Account &rarr; Username to check if it\'s available</div>';
    }
    html += '  </div>';
    html += '</div>';
  }

  // 2. AI-generated suggestions
  if (data.suggestions && data.suggestions.length > 0) {
    html += '<div class="suggestion-block">';
    html += '  <div class="suggestion-header">';
    html += '    <div class="suggestion-title-wrapper">';
    html += '      <svg class="sparkle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>';
    html += '      <h3>AI SUGGESTIONS (' + data.suggestions.length + ')</h3>';
    html += '    </div>';
    if (data.suggestion_latency_ms) {
      html += '    <span class="latency-time">⏱️ ' + data.suggestion_latency_ms + 'ms</span>';
    }
    html += '  </div>';
    html += '  <div class="suggestions-grid">';
    data.suggestions.forEach(function(item) {
      html += "<div class='suggestion-chip' onclick=\"copyUsername('" + item.username + "', this)\" title='Copy @" + item.username + "'>";
      html += "  <span class='name'>" + item.username + "</span>";
      html += "  <span class='copy-btn'><svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><rect x='9' y='9' width='13' height='13' rx='2' ry='2'></rect><path d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1'></path></svg></span>";
      html += "</div>";
    });
    html += '  </div>';
    html += '  <div class="model-meta">MODEL: LLAMA-3.3-70B-VERSATILE</div>';
    html += '</div>';
  }

  // 3. Disclaimer under suggestions
  html += '<div class="disclaimer-alert">';
  html += '  <svg class="alert-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
  html += '  <p>These are AI-generated username ideas, <strong>not confirmed availability</strong>. Usernames may already be taken. Always verify in the <span class="wa-app-highlight">WhatsApp app</span> (Settings &rarr; Account &rarr; Username). Not affiliated with WhatsApp or Meta.</p>';
  html += '</div>';

  if (!data.suggestions?.length && !data.check_result) {
    html = '<div class="error-banner">&#9888; No results. Try a different username, niche, or prompt.</div>';
  }

  resultArea.innerHTML = html;
  resultArea.className = 'visible';

  // Auto-scroll to results
  setTimeout(() => {
    resultArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 100);
}

function copyUsername(username, el) {
  navigator.clipboard.writeText(username).then(function() {
    const copyBtn = el.querySelector('.copy-btn');
    const origHTML = copyBtn.innerHTML;
    copyBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="#34eb83" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    el.classList.add('copied');
    setTimeout(function() {
      copyBtn.innerHTML = origHTML;
      el.classList.remove('copied');
    }, 1500);
  });
}

function fillNiche(niche) {
  nicheInput.value = niche;
  usernameInput.value = '';
  // Scroll to generator form
  scrollToSection('generator-section');
  setTimeout(function() {
    doCheck();
  }, 400);
}

// Intersection Observer for Bottom Navigation
document.addEventListener('DOMContentLoaded', () => {
  const sections = [
    { id: 'generator-section', btn: 'nav-generator' },
    { id: 'browse-section', btn: 'nav-browse' },
    { id: 'result-area', btn: 'nav-results' }
  ];
  
  const observerOptions = {
    root: null,
    rootMargin: '-20% 0px -50% 0px',
    threshold: 0.1
  };
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      // result-area is only relevant when visible
      if (entry.target.id === 'result-area' && !entry.target.classList.contains('visible')) {
        return;
      }
      
      if (entry.isIntersecting) {
        const sectionConfig = sections.find(s => s.id === entry.target.id);
        if (sectionConfig) {
          document.querySelectorAll('.bottom-nav .nav-item').forEach(btn => {
            btn.classList.remove('active');
          });
          const activeBtn = document.getElementById(sectionConfig.btn);
          if (activeBtn) activeBtn.classList.add('active');
        }
      }
    });
  }, observerOptions);
  
  sections.forEach(s => {
    const el = document.getElementById(s.id);
    if (el) observer.observe(el);
  });
});
