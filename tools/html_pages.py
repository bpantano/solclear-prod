"""
HTML page templates for Solclear.
Extracted from live_server.py to reduce file size.
"""

# ── Login HTML ────────────────────────────────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta property="og:title" content="Solclear">
  <meta property="og:description" content="Solar installation compliance, simplified.">
  <meta property="og:image" content="https://app.solclear.co/og-image.svg">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://app.solclear.co">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <title>Solclear — Sign In</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a; color: #e2e8f0; font-size: 14px; line-height: 1.5;
      min-height: 100dvh; display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 20px;
    }
    .login-card {
      width: 100%; max-width: 380px; background: #1e293b; border-radius: 16px;
      padding: 32px 28px; text-align: center;
    }
    .login-logo { margin-bottom: 6px; text-align: center; }
    .login-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
    .login-sub { font-size: 12px; color: #64748b; margin-bottom: 24px; }
    .login-input {
      width: 100%; padding: 14px 16px; border: 2px solid #334155; border-radius: 10px;
      background: #0f172a; color: #e2e8f0; font-size: 15px; outline: none;
      margin-bottom: 12px; -webkit-appearance: none;
    }
    .login-input:focus { border-color: #3b82f6; }
    .login-input::placeholder { color: #475569; }
    .login-btn {
      width: 100%; padding: 14px; border: none; border-radius: 10px;
      background: #3b82f6; color: #fff; font-size: 15px; font-weight: 600;
      cursor: pointer; min-height: 50px; margin-top: 8px;
    }
    .login-btn:disabled { background: #475569; cursor: not-allowed; }
    .login-error {
      background: #7f1d1d; color: #fca5a5; border-radius: 8px; padding: 10px 14px;
      font-size: 13px; margin-bottom: 12px; display: none;
    }
    .login-footer { margin-top: 24px; font-size: 11px; color: #334155; }
  </style>
</head>
<body>
  <div class="login-card">
    <div class="login-logo">
      <div style="position:relative;display:inline-block;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="36" height="36" style="position:absolute;left:-44px;top:50%;transform:translateY(-50%);">
          <circle cx="60" cy="54" r="14" fill="#F59E0B"/>
          <path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="#e2e8f0" stroke-width="8" stroke-linecap="round"/>
        </svg>
        <span style="font-size:36px;font-weight:600;letter-spacing:-1.5px;color:#e2e8f0;">solclear</span>
      </div>
    </div>
    <div class="login-title">Welcome back</div>
    <div class="login-sub">Sign in to your account</div>

    <div class="login-error" id="loginError"></div>

    <form onsubmit="doLogin(event)">
      <input class="login-input" id="loginEmail" type="email" placeholder="Email" autocomplete="email" required>
      <div style="position:relative;">
        <input class="login-input" id="loginPassword" type="password" placeholder="Password" autocomplete="current-password" required style="padding-right:44px;">
        <button type="button" onclick="togglePw(this)" style="position:absolute;right:12px;top:50%;transform:translateY(-50%);background:none;border:none;color:#64748b;cursor:pointer;padding:4px;"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>
      </div>
      <button class="login-btn" type="submit" id="loginBtn">Sign In</button>
    </form>
    <div style="margin-top:16px;"><a href="/forgot-password" style="color:#3b82f6;text-decoration:none;font-size:13px;">Forgot password?</a></div>
    <div style="margin-top:24px;padding-top:16px;border-top:1px solid #334155;">
      <div style="font-size:12px;color:#64748b;margin-bottom:6px;">Don't have an account?</div>
      <a href="/request-demo" style="color:#F59E0B;text-decoration:none;font-size:14px;font-weight:600;">Request a Demo &rarr;</a>
    </div>
  </div>
  <div class="login-footer">&copy; 2026 Solclear. All rights reserved.</div>

  <script>
    function togglePw(btn) {
      const inp = btn.parentElement.querySelector('input');
      if (inp.type === 'password') { inp.type = 'text'; btn.style.color = '#3b82f6'; }
      else { inp.type = 'password'; btn.style.color = '#64748b'; }
    }
    async function doLogin(e) {
      e.preventDefault();
      const btn = document.getElementById('loginBtn');
      const err = document.getElementById('loginError');
      btn.disabled = true;
      btn.textContent = 'Signing in...';
      err.style.display = 'none';

      try {
        const r = await fetch('/api/login', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            email: document.getElementById('loginEmail').value.trim(),
            password: document.getElementById('loginPassword').value,
          })
        });
        const data = await r.json();
        if (data.ok) {
          window.location.href = '/';
        } else {
          err.textContent = data.error || 'Login failed';
          err.style.display = 'block';
        }
      } catch (ex) {
        err.textContent = 'Connection error';
        err.style.display = 'block';
      }
      btn.disabled = false;
      btn.textContent = 'Sign In';
    }
  </script>
</body>
</html>"""

# ── Auth page shared styles ───────────────────────────────────────────────────

_AUTH_PAGE_STYLE = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a; color: #e2e8f0; font-size: 14px; line-height: 1.5;
      min-height: 100dvh; display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 20px;
    }
    .card { width: 100%; max-width: 380px; background: #1e293b; border-radius: 16px; padding: 32px 28px; text-align: center; }
    .logo { margin-bottom: 24px; text-align: center; }
    .title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
    .sub { font-size: 12px; color: #64748b; margin-bottom: 24px; }
    .pw-wrap { position: relative; }
    .pw-toggle {
      position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
      background: none; border: none; color: #64748b; cursor: pointer; padding: 4px;
      display: flex; align-items: center;
    }
    .pw-toggle:hover { color: #94a3b8; }
    .pw-toggle svg { width: 20px; height: 20px; }
    .input {
      width: 100%; padding: 14px 16px; border: 2px solid #334155; border-radius: 10px;
      background: #0f172a; color: #e2e8f0; font-size: 15px; outline: none;
      margin-bottom: 12px; -webkit-appearance: none;
    }
    .input:focus { border-color: #3b82f6; }
    .input::placeholder { color: #475569; }
    .btn {
      width: 100%; padding: 14px; border: none; border-radius: 10px;
      background: #3b82f6; color: #fff; font-size: 15px; font-weight: 600;
      cursor: pointer; min-height: 50px; margin-top: 8px;
    }
    .btn:disabled { background: #475569; cursor: not-allowed; }
    .error { background: #7f1d1d; color: #fca5a5; border-radius: 8px; padding: 10px 14px; font-size: 13px; margin-bottom: 12px; display: none; }
    .success { background: #064e3b; color: #6ee7b7; border-radius: 8px; padding: 10px 14px; font-size: 13px; margin-bottom: 12px; display: none; }
    .link { color: #3b82f6; text-decoration: none; font-size: 13px; }
    .link:hover { text-decoration: underline; }
    .footer { margin-top: 24px; font-size: 11px; color: #334155; }
"""

_AUTH_PAGE_LOGO = """
      <div style="display:inline-flex;align-items:center;gap:10px;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="36" height="36" style="flex-shrink:0;">
          <circle cx="60" cy="54" r="14" fill="#F59E0B"/>
          <path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="#e2e8f0" stroke-width="8" stroke-linecap="round"/>
        </svg>
        <span style="font-size:28px;font-weight:600;letter-spacing:-1px;color:#e2e8f0;">solclear</span>
      </div>
"""

# ── Forgot Password HTML ─────────────────────────────────────────────────────

FORGOT_PASSWORD_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta property="og:title" content="Solclear">
  <meta property="og:description" content="Solar installation compliance, simplified.">
  <meta property="og:image" content="https://app.solclear.co/og-image.svg">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://app.solclear.co">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <title>Solclear — Forgot Password</title>
  <style>{_AUTH_PAGE_STYLE}</style>
</head>
<body>
  <div class="card">
    <div class="logo">{_AUTH_PAGE_LOGO}</div>
    <div class="title">Forgot your password?</div>
    <div class="sub">Enter your email and we'll send you a reset link.</div>
    <div class="error" id="errMsg"></div>
    <div class="success" id="okMsg"></div>
    <form onsubmit="doForgot(event)" id="forgotForm">
      <input class="input" id="forgotEmail" type="email" placeholder="Email" autocomplete="email" required>
      <button class="btn" type="submit" id="forgotBtn">Send Reset Link</button>
    </form>
    <div style="margin-top:16px;"><a class="link" href="/login">&larr; Back to sign in</a></div>
  </div>
  <div class="footer">&copy; 2026 Solclear. All rights reserved.</div>
  <script>
    async function doForgot(e) {{
      e.preventDefault();
      const btn = document.getElementById('forgotBtn');
      const err = document.getElementById('errMsg');
      const ok = document.getElementById('okMsg');
      btn.disabled = true; btn.textContent = 'Sending...';
      err.style.display = 'none'; ok.style.display = 'none';
      try {{
        const r = await fetch('/api/forgot-password', {{
          method: 'POST', credentials: 'same-origin',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{ email: document.getElementById('forgotEmail').value.trim() }})
        }});
        const data = await r.json();
        if (data.ok) {{
          ok.textContent = data.message;
          ok.style.display = 'block';
          document.getElementById('forgotForm').style.display = 'none';
        }} else {{
          err.textContent = data.error || 'Something went wrong';
          err.style.display = 'block';
        }}
      }} catch (ex) {{ err.textContent = 'Connection error'; err.style.display = 'block'; }}
      btn.disabled = false; btn.textContent = 'Send Reset Link';
    }}
  </script>
</body>
</html>"""

# ── Reset Password HTML ──────────────────────────────────────────────────────

RESET_PASSWORD_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta property="og:title" content="Solclear">
  <meta property="og:description" content="Solar installation compliance, simplified.">
  <meta property="og:image" content="https://app.solclear.co/og-image.svg">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://app.solclear.co">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <title>Solclear — Reset Password</title>
  <style>{_AUTH_PAGE_STYLE}</style>
</head>
<body>
  <div class="card">
    <div class="logo">{_AUTH_PAGE_LOGO}</div>
    <div class="title">Set a new password</div>
    <div class="sub">Must be at least 8 characters.</div>
    <div class="error" id="errMsg"></div>
    <div class="success" id="okMsg"></div>
    <form onsubmit="doReset(event)" id="resetForm">
      <div class="pw-wrap"><input class="input" id="newPass" type="password" placeholder="New password" autocomplete="new-password" required minlength="8" style="padding-right:44px;"><button type="button" class="pw-toggle" onclick="togglePw(this)"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button></div>
      <div class="pw-wrap"><input class="input" id="confirmPass" type="password" placeholder="Confirm password" autocomplete="new-password" required minlength="8" style="padding-right:44px;"><button type="button" class="pw-toggle" onclick="togglePw(this)"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button></div>
      <button class="btn" type="submit" id="resetBtn">Reset Password</button>
    </form>
    <div id="successLinks" style="display:none;margin-top:16px;"><a class="link" href="/login">Sign in with your new password &rarr;</a></div>
  </div>
  <div class="footer">&copy; 2026 Solclear. All rights reserved.</div>
  <script>
    function togglePw(btn) {{
      const inp = btn.parentElement.querySelector('input');
      if (inp.type === 'password') {{ inp.type = 'text'; btn.style.color = '#3b82f6'; }}
      else {{ inp.type = 'password'; btn.style.color = '#64748b'; }}
    }}
    async function doReset(e) {{
      e.preventDefault();
      const btn = document.getElementById('resetBtn');
      const err = document.getElementById('errMsg');
      const ok = document.getElementById('okMsg');
      const pw = document.getElementById('newPass').value;
      const confirm = document.getElementById('confirmPass').value;
      if (pw !== confirm) {{ err.textContent = 'Passwords do not match'; err.style.display = 'block'; return; }}
      btn.disabled = true; btn.textContent = 'Resetting...';
      err.style.display = 'none'; ok.style.display = 'none';
      try {{
        const r = await fetch('/api/reset-password', {{
          method: 'POST', credentials: 'same-origin',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{ token: '{{{{TOKEN}}}}', password: pw }})
        }});
        const data = await r.json();
        if (data.ok) {{
          ok.textContent = data.message;
          ok.style.display = 'block';
          document.getElementById('resetForm').style.display = 'none';
          document.getElementById('successLinks').style.display = 'block';
        }} else {{
          err.textContent = data.error || 'Something went wrong';
          err.style.display = 'block';
        }}
      }} catch (ex) {{ err.textContent = 'Connection error'; err.style.display = 'block'; }}
      btn.disabled = false; btn.textContent = 'Reset Password';
    }}
  </script>
</body>
</html>"""

# ── Change Password HTML ─────────────────────────────────────────────────────

CHANGE_PASSWORD_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta property="og:title" content="Solclear">
  <meta property="og:description" content="Solar installation compliance, simplified.">
  <meta property="og:image" content="https://app.solclear.co/og-image.svg">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://app.solclear.co">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <title>Solclear — Change Password</title>
  <style>{_AUTH_PAGE_STYLE}</style>
</head>
<body>
  <div class="card">
    <div class="logo">{_AUTH_PAGE_LOGO}</div>
    <div class="title">Change your password</div>
    <div class="sub">Enter your current password and choose a new one.</div>
    <div class="error" id="errMsg"></div>
    <div class="success" id="okMsg"></div>
    <form onsubmit="doChange(event)" id="changeForm">
      <div class="pw-wrap"><input class="input" id="currentPass" type="password" placeholder="Current password" autocomplete="current-password" required style="padding-right:44px;"><button type="button" class="pw-toggle" onclick="togglePw(this)"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button></div>
      <div class="pw-wrap"><input class="input" id="newPass" type="password" placeholder="New password" autocomplete="new-password" required minlength="8" style="padding-right:44px;"><button type="button" class="pw-toggle" onclick="togglePw(this)"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button></div>
      <div class="pw-wrap"><input class="input" id="confirmPass" type="password" placeholder="Confirm new password" autocomplete="new-password" required minlength="8" style="padding-right:44px;"><button type="button" class="pw-toggle" onclick="togglePw(this)"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button></div>
      <button class="btn" type="submit" id="changeBtn">Change Password</button>
    </form>
    <div style="margin-top:16px;"><a class="link" href="/">&larr; Back to home</a></div>
  </div>
  <div class="footer">&copy; 2026 Solclear. All rights reserved.</div>
  <script>
    function togglePw(btn) {{
      const inp = btn.parentElement.querySelector('input');
      if (inp.type === 'password') {{ inp.type = 'text'; btn.style.color = '#3b82f6'; }}
      else {{ inp.type = 'password'; btn.style.color = '#64748b'; }}
    }}
    async function doChange(e) {{
      e.preventDefault();
      const btn = document.getElementById('changeBtn');
      const err = document.getElementById('errMsg');
      const ok = document.getElementById('okMsg');
      const newPw = document.getElementById('newPass').value;
      const confirm = document.getElementById('confirmPass').value;
      if (newPw !== confirm) {{ err.textContent = 'Passwords do not match'; err.style.display = 'block'; return; }}
      btn.disabled = true; btn.textContent = 'Updating...';
      err.style.display = 'none'; ok.style.display = 'none';
      try {{
        const r = await fetch('/api/change-password', {{
          method: 'POST', credentials: 'same-origin',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{ current_password: document.getElementById('currentPass').value, new_password: newPw }})
        }});
        const data = await r.json();
        if (data.ok) {{
          ok.textContent = data.message;
          ok.style.display = 'block';
          document.getElementById('changeForm').reset();
        }} else {{
          err.textContent = data.error || 'Something went wrong';
          err.style.display = 'block';
        }}
      }} catch (ex) {{ err.textContent = 'Connection error'; err.style.display = 'block'; }}
      btn.disabled = false; btn.textContent = 'Change Password';
    }}
  </script>
</body>
</html>"""

# ── Request Demo HTML ─────────────────────────────────────────────────────────

REQUEST_DEMO_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <meta property="og:title" content="Solclear">
  <meta property="og:description" content="Solar installation compliance, simplified.">
  <meta property="og:image" content="https://app.solclear.co/og-image.svg">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://app.solclear.co">
  <meta name="twitter:card" content="summary">
  <title>Solclear — Request a Demo</title>
  <style>{_AUTH_PAGE_STYLE}
    .card {{{{ max-width: 440px; }}}}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">{_AUTH_PAGE_LOGO}</div>
    <div class="title">Request a Demo</div>
    <div class="sub">See how Solclear can streamline your solar compliance workflow.</div>
    <div class="error" id="errMsg"></div>
    <div class="success" id="okMsg"></div>
    <form onsubmit="doRequest(event)" id="demoForm">
      <input class="input" id="demoName" type="text" placeholder="Your name" required>
      <input class="input" id="demoEmail" type="email" placeholder="Email address" required>
      <input class="input" id="demoCompany" type="text" placeholder="Company name (optional)">
      <textarea class="input" id="demoMessage" rows="3" placeholder="Tell us about your needs (optional)" style="resize:vertical;font-family:inherit;"></textarea>
      <button class="btn" type="submit" id="demoBtn">Request Demo</button>
    </form>
    <div id="successMsg" style="display:none;margin-top:16px;">
      <a class="link" href="/login">&larr; Back to sign in</a>
    </div>
    <div id="backLink" style="margin-top:16px;"><a class="link" href="/login">&larr; Back to sign in</a></div>
  </div>
  <div class="footer">&copy; 2026 Solclear. All rights reserved.</div>
  <script>
    async function doRequest(e) {{{{
      e.preventDefault();
      const btn = document.getElementById('demoBtn');
      const err = document.getElementById('errMsg');
      const ok = document.getElementById('okMsg');
      btn.disabled = true; btn.textContent = 'Sending...';
      err.style.display = 'none'; ok.style.display = 'none';
      try {{{{
        const r = await fetch('/api/request-demo', {{{{
          method: 'POST', credentials: 'same-origin',
          headers: {{{{'Content-Type': 'application/json'}}}},
          body: JSON.stringify({{{{
            name: document.getElementById('demoName').value.trim(),
            email: document.getElementById('demoEmail').value.trim(),
            company: document.getElementById('demoCompany').value.trim(),
            message: document.getElementById('demoMessage').value.trim(),
          }}}})
        }}}});
        const data = await r.json();
        if (data.ok) {{{{
          ok.textContent = data.message;
          ok.style.display = 'block';
          document.getElementById('demoForm').style.display = 'none';
          document.getElementById('backLink').style.display = 'none';
          document.getElementById('successMsg').style.display = 'block';
        }}}} else {{{{
          err.textContent = data.error || 'Something went wrong';
          err.style.display = 'block';
        }}}}
      }}}} catch (ex) {{{{ err.textContent = 'Connection error'; err.style.display = 'block'; }}}}
      btn.disabled = false; btn.textContent = 'Request Demo';
    }}}}
  </script>
</body>
</html>"""

# ── Embedded HTML ─────────────────────────────────────────────────────────────

EMBEDDED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta property="og:title" content="Solclear">
  <meta property="og:description" content="Solar installation compliance, simplified.">
  <meta property="og:image" content="https://app.solclear.co/og-image.svg">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://app.solclear.co">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <title>Solclear Compliance</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: #f8f9fb; --bg-card: #fff; --bg-input: #fff;
      --text: #1a1a2e; --text-secondary: #6b7280; --text-muted: #9ca3af;
      --border: #e5e7eb; --border-light: #f3f4f6;
      --header-bg: #111827;
      --badge-pass-bg: #ecfdf5; --badge-pass-text: #065f46;
      --badge-fail-bg: #fef2f2; --badge-fail-text: #991b1b;
      --badge-missing-bg: #fffbeb; --badge-missing-text: #92400e;
    }

    [data-theme="dark"] {
      --bg: #0f172a; --bg-card: #1e293b; --bg-input: #1e293b;
      --text: #e2e8f0; --text-secondary: #94a3b8; --text-muted: #64748b;
      --border: #334155; --border-light: #1e293b;
      --header-bg: #020617;
      --badge-pass-bg: #064e3b; --badge-pass-text: #6ee7b7;
      --badge-fail-bg: #7f1d1d; --badge-fail-text: #fca5a5;
      --badge-missing-bg: #78350f; --badge-missing-text: #fcd34d;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      min-height: 100dvh;
      transition: background 0.2s, color 0.2s;
    }

    /* ── Header ── */
    .top-bar {
      background: var(--header-bg); color: #fff; padding: 12px 20px;
      display: grid; grid-template-columns: 44px 1fr 44px; align-items: center;
    }
    .top-bar .sub { font-size: 11px; color: var(--text-secondary); }
    .theme-toggle {
      background: none; border: none; color: #fff; cursor: pointer;
      width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
      padding: 0; -webkit-tap-highlight-color: transparent;
    }
    .theme-toggle svg { width: 20px; height: 20px; }
    .hamburger {
      background: none; border: none; color: #fff; cursor: pointer;
      width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
      padding: 0; -webkit-tap-highlight-color: transparent;
    }
    .hamburger svg { width: 24px; height: 24px; }
    .logo-center { display: flex; justify-content: center; }
    .header-spacer { width: 44px; }

    /* ── Nav drawer ── */
    .nav-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 200;
      display: none; opacity: 0; transition: opacity 0.2s ease;
    }
    .nav-overlay.open { display: block; opacity: 1; }
    .nav-drawer {
      position: fixed; top: 0; left: -280px; width: 280px; height: 100%;
      background: #111827; z-index: 201; transition: left 0.25s ease;
      padding: 20px; overflow-y: auto;
    }
    .nav-drawer.open { left: 0; }
    .nav-drawer-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #1f2937;
    }
    .nav-close {
      background: none; border: none; color: #9ca3af; cursor: pointer;
      width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;
      font-size: 20px;
    }
    .nav-item {
      display: block; width: 100%; padding: 14px 12px; border-radius: 8px;
      color: #d1d5db; text-decoration: none; font-size: 14px; font-weight: 500;
      margin-bottom: 4px; cursor: pointer; border: none; background: none; text-align: left;
    }
    .nav-item:hover, .nav-item:active { background: #1f2937; color: #fff; }

    /* ── Steps ── */
    .step { display: none; padding: 20px; }
    .step.active { display: block; }
    .step-label {
      font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em;
      color: var(--text-muted); font-weight: 600; margin-bottom: 12px;
    }

    /* ── Search ── */
    .search-input {
      width: 100%; padding: 12px 14px; font-size: 16px; border: 2px solid var(--border);
      border-radius: 8px; outline: none; -webkit-appearance: none; background: var(--bg-input); color: var(--text);
    }
    .search-input:focus { border-color: #3b82f6; }

    /* ── List items ── */
    .list-item {
      background: var(--bg-card); border-radius: 8px; padding: 14px 16px; margin-top: 8px;
      border: 2px solid transparent; cursor: pointer; transition: border-color 0.1s;
      min-height: 44px; display: flex; flex-direction: column; justify-content: center;
    }
    .list-item:hover, .list-item:active { border-color: #3b82f6; }
    .list-item .name { font-weight: 600; font-size: 14px; color: var(--text); }
    .list-item .detail { font-size: 12px; color: var(--text-secondary); }

    /* ── Toggles ── */
    .param-group { margin-bottom: 16px; }
    .param-group label {
      display: block; font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.06em; color: var(--text-secondary); margin-bottom: 6px; font-weight: 600;
    }
    .toggle-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .toggle-btn {
      padding: 10px 20px; border-radius: 8px; border: 2px solid var(--border);
      background: var(--bg-card); color: var(--text); font-size: 14px; font-weight: 500; cursor: pointer;
      min-height: 44px; transition: all 0.1s; flex: 1; text-align: center;
    }
    .toggle-btn.selected { border-color: #3b82f6; background: #eff6ff; color: #1d4ed8; }

    /* ── Run button ── */
    .run-btn {
      width: 100%; padding: 16px; border: none; border-radius: 10px;
      background: #3b82f6; color: #fff; font-size: 16px; font-weight: 600;
      cursor: pointer; min-height: 52px; margin-top: 20px;
    }
    .run-btn:disabled { background: #9ca3af; cursor: not-allowed; }

    /* ── Progress ── */
    .progress-wrap { padding: 20px; }
    .progress-bar-bg {
      width: 100%; height: 8px; background: var(--border); border-radius: 4px;
      overflow: hidden; margin-bottom: 8px;
    }
    .progress-bar-fill {
      height: 100%; background: #3b82f6; border-radius: 4px;
      transition: width 0.3s ease; width: 0%;
    }
    .progress-text { font-size: 12px; color: var(--text-secondary); margin-bottom: 16px; }

    /* ── Status message ── */
    .status-msg {
      background: #eff6ff; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;
      font-size: 13px; color: #1d4ed8; display: none;
    }

    /* ── Result rows ── */
    .result-row {
      background: var(--bg-card); border-radius: 6px; padding: 10px 14px; margin-bottom: 6px;
      border-left: 3px solid var(--border); animation: fadeIn 0.2s ease;
    }
    .result-row.pass { border-left-color: #10b981; }
    .result-row.fail { border-left-color: #ef4444; }
    .result-row.missing { border-left-color: #f59e0b; }
    .result-row.error { border-left-color: #8b5cf6; }

    .result-header { display: flex; align-items: center; gap: 8px; }
    .result-detail { transition: max-height 0.2s ease; }
    .result-row.collapsed .result-detail { display: none; }
    .result-row.collapsed .collapse-arrow { transform: rotate(-90deg); }
    .collapse-arrow { transition: transform 0.2s ease; display: inline-block; }
    .badge {
      font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 3px;
      letter-spacing: 0.04em; text-transform: uppercase; white-space: nowrap;
    }
    .badge-pass { background: var(--badge-pass-bg); color: var(--badge-pass-text); }
    .badge-fail { background: var(--badge-fail-bg); color: var(--badge-fail-text); }
    .badge-missing { background: var(--badge-missing-bg); color: var(--badge-missing-text); }
    .badge-error { background: #f5f3ff; color: #5b21b6; }
    .result-id { font-size: 10px; font-weight: 700; color: var(--text-muted); }
    .result-title { font-size: 13px; font-weight: 500; flex: 1; color: var(--text); }
    .result-reason { font-size: 12px; color: var(--text-secondary); margin-top: 6px; padding-left: 10px; border-left: 2px solid var(--border-light); }
    .expand-btn {
      margin-top: 4px; background: none; border: none; color: #3b82f6;
      font-size: 11px; font-weight: 500; cursor: pointer; padding: 2px 0;
    }
    .expand-btn:hover { text-decoration: underline; }
    .expand-btn .arrow { font-size: 10px; margin-left: 2px; }

    /* ── Done banner ── */
    .done-banner {
      padding: 16px 20px; display: none; align-items: center; justify-content: space-between;
      flex-wrap: wrap; gap: 10px;
    }
    .done-pass { background: #ecfdf5; border-bottom: 2px solid #10b981; }
    .done-fail { background: #fef2f2; border-bottom: 2px solid #ef4444; }
    .done-label { font-size: 13px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }
    .done-pass .done-label { color: #065f46; }
    .done-fail .done-label { color: #991b1b; }
    .done-stats { font-size: 12px; color: var(--text-secondary); }
    .cc-link {
      display: inline-block; margin-top: 8px; padding: 10px 16px; background: #3b82f6;
      color: #fff; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600;
      min-height: 44px; line-height: 24px;
    }

    /* ── Back button ── */
    .back-btn {
      background: none; border: none; color: #3b82f6; font-size: 13px;
      font-weight: 500; cursor: pointer; padding: 4px 0; margin-bottom: 12px;
    }

    /* ── Loader animation ── */
    .loader-anim {
      display: flex; justify-content: center; padding: 20px 0 8px;
    }
    .loader-anim.hidden { display: none; }

    /* ── Universal spinner ── */
    .spinner {
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 32px 0; gap: 12px;
    }
    .spinner-text { font-size: 12px; color: var(--text-muted); }

    /* ── Project cards ── */
    .project-card {
      background: var(--bg-card); border-radius: 10px; margin-top: 8px;
      border: 2px solid transparent; cursor: pointer; transition: border-color 0.1s;
      display: flex; overflow: hidden;
    }
    .project-card:hover, .project-card:active { border-color: #3b82f6; }
    .project-card-img {
      width: 80px; height: 80px; object-fit: cover; flex-shrink: 0; background: var(--border);
    }
    .project-card-info { padding: 12px 14px; flex: 1; display: flex; flex-direction: column; justify-content: center; }
    .project-card-name { font-weight: 600; font-size: 13px; color: var(--text); }
    .project-card-addr { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
    .project-card-meta { font-size: 10px; color: var(--text-muted); margin-top: 4px; display: flex; align-items: center; gap: 6px; }
    .project-card-dot { width: 6px; height: 6px; border-radius: 50%; background: #10b981; }

    /* ── Home cards ── */
    .home-cards { display: flex; flex-direction: column; gap: 8px; }
    .home-card {
      background: var(--bg-card); border-radius: 10px; padding: 16px; cursor: pointer;
      display: flex; align-items: center; gap: 14px;
      border: 2px solid transparent; transition: border-color 0.1s;
    }
    .home-card:hover, .home-card:active { border-color: #3b82f6; }
    .home-card-icon {
      width: 44px; height: 44px; border-radius: 10px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
    }
    .home-card-text { flex: 1; }
    .home-card-title { font-size: 14px; font-weight: 600; color: var(--text); }
    .home-card-desc { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>
<body>

  <!-- Nav drawer -->
  <div class="nav-overlay" id="navOverlay" onclick="closeNav()"></div>
  <div class="nav-drawer" id="navDrawer">
    <div class="nav-drawer-header">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 160" height="28">
        <g transform="translate(24,36)"><circle cx="44" cy="40" r="12" fill="#F59E0B"/><path d="M16 76 A 28 28 0 0 1 72 76" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/></g>
        <text x="116" y="104" font-family="Inter,Helvetica,Arial,sans-serif" font-weight="600" font-size="80" fill="#ffffff" letter-spacing="-2.5">solclear</text>
      </svg>
      <button class="nav-close" onclick="closeNav()">&times;</button>
    </div>
    <button class="nav-item" onclick="closeNav();showStep('home')">Home</button>
    <button class="nav-item" onclick="closeNav();showStep('reports')">Recent Reports</button>
    <button class="nav-item" onclick="closeNav();showStep(1)">New Compliance Check</button>
    <div style="border-top:1px solid #1f2937;margin:16px 0 8px;"></div>
    <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.1em;color:#4b5563;padding:0 12px 8px;font-weight:600;">Admin</div>
    <button class="nav-item" onclick="closeNav();showStep('orgs')">Organizations</button>
    <button class="nav-item" onclick="closeNav();showStep('reqs')">Requirements</button>
    <div style="border-top:1px solid #1f2937;margin:16px 0 8px;"></div>
    <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.1em;color:#4b5563;padding:0 12px 8px;font-weight:600;">Account</div>
    <a class="nav-item" href="/change-password" style="text-decoration:none;">Change Password</a>
    <a class="nav-item" href="/logout" style="color:#ef4444;text-decoration:none;">Sign Out</a>
  </div>

  <div class="top-bar">
    <button class="hamburger" onclick="openNav()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>
    <div class="logo-center">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 160" height="42" style="flex-shrink:0;">
        <g transform="translate(24,36)"><circle cx="44" cy="40" r="12" fill="#F59E0B"/><path d="M16 76 A 28 28 0 0 1 72 76" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/></g>
        <text x="116" y="104" font-family="Inter,Helvetica,Arial,sans-serif" font-weight="600" font-size="80" fill="#ffffff" letter-spacing="-2.5">solclear</text>
      </svg>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()" id="themeBtn" title="Toggle dark mode">
      <svg id="themeIconSun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
      <svg id="themeIconMoon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="display:none;"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    </button>
  </div>

  <!-- Landing page -->
  <div id="homePage" class="step active" style="display:block;">
    <div style="padding:4px 0 20px;">
      <div style="font-size:15px;font-weight:600;color:var(--text);">Welcome to Solclear</div>
      <div style="font-size:12px;color:var(--text-muted);">Solar compliance, simplified.</div>
    </div>

    <!-- Action cards -->
    <div class="home-cards">
      <div class="home-card" onclick="showStep(1)">
        <div class="home-card-icon" style="background:#eff6ff;color:#3b82f6;">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </div>
        <div class="home-card-text">
          <div class="home-card-title">New Compliance Check</div>
          <div class="home-card-desc">Run a photo compliance check on a project</div>
        </div>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#9ca3af" stroke-width="2" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>
      </div>

      <div class="home-card" onclick="showStep('reports')">
        <div class="home-card-icon" style="background:#ecfdf5;color:#10b981;">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
        </div>
        <div class="home-card-text">
          <div class="home-card-title">Recent Reports</div>
          <div class="home-card-desc">View and share previous compliance results</div>
        </div>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#9ca3af" stroke-width="2" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>
      </div>

      <div class="home-card" onclick="showStep('orgs')">
        <div class="home-card-icon" style="background:#fffbeb;color:#f59e0b;">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 21h18M9 8h1M9 12h1M9 16h1M14 8h1M14 12h1M14 16h1"/><rect x="5" y="3" width="14" height="18" rx="1"/></svg>
        </div>
        <div class="home-card-text">
          <div class="home-card-title">Organizations</div>
          <div class="home-card-desc">Manage companies, users, and settings</div>
        </div>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#9ca3af" stroke-width="2" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>
      </div>
    </div>

    <!-- Recent reports preview -->
    <div style="margin-top:28px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:#9ca3af;font-weight:600;">Latest Reports</div>
        <button onclick="showStep('reports')" style="background:none;border:none;color:#3b82f6;font-size:12px;font-weight:500;cursor:pointer;">View all</button>
      </div>
      <div id="homeRecentList"></div>
    </div>
  </div>

  <!-- Full reports list -->
  <div id="reportsPage" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">All Reports</div>

    <!-- Filters -->
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
      <input class="search-input" id="reportSearch" type="text" placeholder="Search by project name..." style="flex:1;min-width:160px;font-size:13px;" oninput="filterReports()">
      <select id="reportStatusFilter" onchange="filterReports()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;">
        <option value="all">All Status</option>
        <option value="passed">Passed Only</option>
        <option value="failed">Has Failures</option>
      </select>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;align-items:center;">
      <div style="display:flex;align-items:center;gap:6px;flex:1;min-width:200px;">
        <input type="date" id="reportDateFrom" onchange="filterReports()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;flex:1;">
        <span style="color:var(--text-muted);font-size:12px;">to</span>
        <input type="date" id="reportDateTo" onchange="filterReports()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;flex:1;">
      </div>
      <button onclick="clearDateFilter()" style="background:var(--border-light);border:none;border-radius:8px;padding:10px 14px;font-size:12px;color:var(--text-muted);cursor:pointer;min-height:44px;font-weight:500;">Clear dates</button>
    </div>
    <div id="reportCount" style="font-size:11px;color:var(--text-muted);margin-bottom:8px;"></div>

    <div id="recentList"></div>
  </div>

  <!-- Step 1: Select project -->
  <div id="step1" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">Step 1 — Select Project</div>
    <input class="search-input" id="projectSearch" type="text" placeholder="Search by name or address..." autocomplete="off">

    <!-- Date filter -->
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center;">
      <select id="projectDateField" onchange="filterProjects()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:12px;background:var(--bg-input);color:var(--text);min-height:44px;">
        <option value="updated_at">Last Updated</option>
        <option value="created_at">Date Created</option>
      </select>
      <div style="display:flex;align-items:center;gap:6px;flex:1;min-width:180px;">
        <input type="date" id="projectDateFrom" onchange="filterProjects()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;flex:1;">
        <span style="color:var(--text-muted);font-size:12px;">to</span>
        <input type="date" id="projectDateTo" onchange="filterProjects()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;flex:1;">
      </div>
      <button onclick="clearProjectDateFilter()" style="background:var(--border-light);border:none;border-radius:8px;padding:10px 14px;font-size:12px;color:var(--text-muted);cursor:pointer;min-height:44px;font-weight:500;">Clear</button>
    </div>
    <div id="projectCount" style="font-size:11px;color:var(--text-muted);margin:8px 0;"></div>

    <div id="projectListLoading"></div>
    <div id="projectList"></div>
  </div>

  <!-- Step 2: Select checklist -->
  <div id="step2" class="step">
    <button class="back-btn" onclick="showStep(1)">&larr; Back to projects</button>
    <div class="step-label">Step 2 — Select Checklist</div>
    <div id="selectedProject" style="font-weight:600; margin-bottom:12px;"></div>
    <div id="checklistList"></div>
  </div>

  <!-- Step 3: Manufacturer selection -->
  <div id="step3" class="step">
    <button class="back-btn" onclick="showStep(2)">&larr; Back to checklists</button>
    <div class="step-label">Step 3 — Select Manufacturer</div>
    <div id="selectedProjectName2" style="font-weight:600; margin-bottom:4px;"></div>
    <div id="selectedChecklistName" style="font-size:12px; color:#6b7280; margin-bottom:16px;"></div>

    <div class="param-group">
      <label>Inverter / Equipment Manufacturer</label>
      <div class="toggle-row">
        <button class="toggle-btn" data-param="manufacturer" data-value="SolarEdge" onclick="selectMfg(this)">SolarEdge</button>
        <button class="toggle-btn" data-param="manufacturer" data-value="Tesla" onclick="selectMfg(this)">Tesla</button>
        <button class="toggle-btn" data-param="manufacturer" data-value="Enphase" onclick="selectMfg(this)">Enphase</button>
      </div>
    </div>

    <div id="derivedInfo" style="background:#f0fdf4; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:12px; color:#065f46; display:none;">
      Battery, backup, incentive state, and portal access will be auto-detected from the checklist.
    </div>

    <button class="run-btn" id="runBtn" onclick="startCheck()" disabled>Select a manufacturer to continue</button>
  </div>

  <!-- Step 4: Live results -->
  <div id="step4" class="step">
    <div class="done-banner" id="doneBanner"></div>
    <div class="progress-wrap">
      <div class="loader-anim" id="loaderAnim">
        <svg viewBox="0 0 120 120" width="64" height="64">
          <path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="#e5e7eb" stroke-width="8" stroke-linecap="round"/>
          <circle cx="0" cy="0" r="10" fill="#F59E0B">
            <animateMotion dur="1.4s" repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.45 0 0.55 1">
              <mpath href="#sunPath"/>
            </animateMotion>
          </circle>
          <path id="sunPath" d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="none"/>
        </svg>
      </div>
      <div class="status-msg" id="statusMsg"></div>
      <div class="progress-bar-bg"><div class="progress-bar-fill" id="progressFill"></div></div>
      <div class="progress-text" id="progressText">Preparing...</div>
      <div id="resultsToggle" style="display:none;text-align:right;margin-bottom:8px;">
        <button onclick="toggleAllResults()" id="toggleAllBtn" style="background:none;border:1px solid var(--border);border-radius:6px;padding:6px 12px;font-size:11px;color:var(--text-secondary);cursor:pointer;font-weight:500;">Collapse All</button>
      </div>
      <div id="resultsList"></div>
    </div>
  </div>

  <!-- Organizations list -->
  <div id="adminOrgs" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">Organizations</div>
    <button class="run-btn" onclick="showCreateOrg()" style="margin-bottom:16px;background:#3b82f6;">+ Create Organization</button>
    <div id="orgsList"></div>
  </div>

  <!-- Create org form -->
  <div id="adminOrgCreate" class="step">
    <button class="back-btn" onclick="showStep('orgs')">&larr; Back to organizations</button>
    <div class="step-label">Create Organization</div>
    <div class="param-group">
      <label>Organization Name</label>
      <input class="search-input" id="newOrgName" type="text" placeholder="e.g. Independent Solar" autocomplete="off">
    </div>
    <div class="param-group">
      <label>Initial Status</label>
      <div class="toggle-row">
        <button class="toggle-btn selected" data-param="org-status" data-value="onboarding" onclick="selectToggle(this)">Onboarding</button>
        <button class="toggle-btn" data-param="org-status" data-value="demo" onclick="selectToggle(this)">Demo</button>
        <button class="toggle-btn" data-param="org-status" data-value="active" onclick="selectToggle(this)">Active</button>
      </div>
    </div>
    <button class="run-btn" onclick="createOrg()">Create Organization</button>
  </div>

  <!-- Org detail -->
  <div id="adminOrgDetail" class="step">
    <button class="back-btn" onclick="showStep('orgs')">&larr; Back to organizations</button>
    <div class="step-label" id="orgDetailLabel">Organization</div>

    <!-- Org info -->
    <div style="background:var(--bg-card);border-radius:8px;padding:16px;margin-bottom:16px;">
      <div class="param-group">
        <label>Name</label>
        <input class="search-input" id="orgEditName" type="text" style="font-size:14px;">
      </div>
      <div class="param-group">
        <label>Status</label>
        <div class="toggle-row" id="orgStatusToggles">
          <button class="toggle-btn" data-param="org-edit-status" data-value="onboarding" onclick="selectToggle(this)">Onboarding</button>
          <button class="toggle-btn" data-param="org-edit-status" data-value="demo" onclick="selectToggle(this)">Demo</button>
          <button class="toggle-btn" data-param="org-edit-status" data-value="active" onclick="selectToggle(this)">Active</button>
          <button class="toggle-btn" data-param="org-edit-status" data-value="inactive" onclick="selectToggle(this)">Inactive</button>
        </div>
      </div>
      <div class="param-group">
        <label>CompanyCam API Key</label>
        <div style="display:flex;gap:8px;align-items:center;">
          <input class="search-input" id="orgCcKey" type="password" style="font-size:13px;font-family:monospace;flex:1;" placeholder="Not set">
          <button onclick="toggleKeyVis('orgCcKey')" style="background:var(--border-light);border:none;border-radius:6px;padding:8px 12px;cursor:pointer;font-size:12px;min-height:44px;color:var(--text);">Show</button>
        </div>
      </div>
      <div class="param-group">
        <label>Anthropic API Key</label>
        <div style="display:flex;gap:8px;align-items:center;">
          <input class="search-input" id="orgAnthKey" type="password" style="font-size:13px;font-family:monospace;flex:1;" placeholder="Not set">
          <button onclick="toggleKeyVis('orgAnthKey')" style="background:var(--border-light);border:none;border-radius:6px;padding:8px 12px;cursor:pointer;font-size:12px;min-height:44px;color:var(--text);">Show</button>
        </div>
      </div>
      <button class="run-btn" onclick="saveOrg()" style="background:#10b981;">Save Changes</button>
    </div>

    <!-- Users -->
    <div style="background:var(--bg-card);border-radius:8px;padding:16px;margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <label style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-secondary);font-weight:600;margin:0;">Users</label>
        <span id="orgUserCount" style="font-size:11px;color:var(--text-muted);"></span>
      </div>
      <div id="orgUsersList"></div>

      <!-- Add user form -->
      <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border-light);">
        <div style="font-size:11px;color:var(--text-secondary);font-weight:600;margin-bottom:8px;">ADD USER</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <input class="search-input" id="addUserFirst" type="text" placeholder="First Name" style="flex:1;min-width:100px;font-size:13px;">
          <input class="search-input" id="addUserLast" type="text" placeholder="Last Name" style="flex:1;min-width:100px;font-size:13px;">
          <input class="search-input" id="addUserEmail" type="email" placeholder="Email" style="flex:1;min-width:160px;font-size:13px;">
          <input class="search-input" id="addUserPhone" type="tel" placeholder="Phone (optional)" style="flex:1;min-width:120px;font-size:13px;">
          <input class="search-input" id="addUserPassword" type="text" placeholder="Initial password" style="flex:1;min-width:120px;font-size:13px;">
          <select id="addUserRole" style="padding:8px;border:2px solid var(--border);border-radius:8px;font-size:13px;min-height:44px;">
            <option value="crew">Crew</option>
            <option value="reviewer">Reviewer</option>
            <option value="admin">Admin</option>
          </select>
          <button onclick="addUser()" style="background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer;min-height:44px;">Add</button>
        </div>
      </div>

      <!-- CSV upload -->
      <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border-light);">
        <div style="font-size:11px;color:var(--text-secondary);font-weight:600;margin-bottom:8px;">BULK IMPORT (CSV)</div>
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">Format: email, first_name, last_name, role, phone (one per line)</div>
        <input type="file" id="csvUpload" accept=".csv" onchange="uploadCsv()" style="font-size:12px;">
        <div id="csvResult" style="margin-top:8px;font-size:12px;"></div>
      </div>
    </div>
  </div>

  <!-- User detail/edit -->
  <div id="adminUserDetail" class="step">
    <button class="back-btn" id="userDetailBack">&larr; Back to organization</button>
    <div class="step-label" id="userDetailLabel">Edit User</div>

    <div style="background:var(--bg-card);border-radius:8px;padding:16px;margin-bottom:16px;">
      <div style="display:flex;gap:12px;flex-wrap:wrap;">
        <div class="param-group" style="flex:1;min-width:140px;">
          <label>First Name</label>
          <input class="search-input" id="editUserFirst" type="text" style="font-size:14px;">
        </div>
        <div class="param-group" style="flex:1;min-width:140px;">
          <label>Last Name</label>
          <input class="search-input" id="editUserLast" type="text" style="font-size:14px;">
        </div>
      </div>
      <div class="param-group">
        <label>Email</label>
        <input class="search-input" id="editUserEmail" type="email" style="font-size:14px;">
      </div>
      <div class="param-group">
        <label>Phone</label>
        <input class="search-input" id="editUserPhone" type="tel" style="font-size:14px;" placeholder="Optional">
      </div>
      <div class="param-group">
        <label>Role</label>
        <div class="toggle-row" id="editUserRoleToggles">
          <button class="toggle-btn" data-param="edit-user-role" data-value="crew" onclick="selectToggle(this)">Crew</button>
          <button class="toggle-btn" data-param="edit-user-role" data-value="reviewer" onclick="selectToggle(this)">Reviewer</button>
          <button class="toggle-btn" data-param="edit-user-role" data-value="admin" onclick="selectToggle(this)">Admin</button>
        </div>
      </div>
      <button class="run-btn" onclick="saveUser()" style="background:#10b981;">Save Changes</button>
    </div>

    <div id="userStatusInfo" style="background:var(--bg-card);border-radius:8px;padding:16px;font-size:12px;color:var(--text-secondary);"></div>
  </div>

  <!-- Requirements list -->
  <div id="adminReqs" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">Palmetto M1 Requirements</div>

    <!-- Change alert banner (hidden by default) -->
    <div id="changeAlert" style="display:none;background:#fef2f2;border:2px solid #ef4444;border-radius:10px;padding:16px;margin-bottom:16px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <div style="font-size:14px;font-weight:700;color:#991b1b;">Requirements Changed</div>
        <button onclick="dismissAlert()" style="margin-left:auto;background:none;border:none;color:#991b1b;cursor:pointer;font-size:16px;">&times;</button>
      </div>
      <div id="changeSummary" style="font-size:13px;color:#991b1b;line-height:1.6;margin-bottom:12px;"></div>
      <div id="changeDiff" style="display:none;">
        <button onclick="toggleDiff()" id="diffToggleBtn" class="expand-btn" style="color:#991b1b;">Show raw diff <span class="arrow">&#9662;</span></button>
        <pre id="changeDiffContent" style="display:none;margin-top:8px;padding:10px;background:#fff;border-radius:6px;font-size:11px;overflow-x:auto;max-height:250px;color:#374151;border:1px solid #fecaca;"></pre>
      </div>
    </div>

    <!-- Monitor status -->
    <div id="monitorCard" style="background:var(--bg-card);border-radius:8px;padding:14px 16px;margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="font-size:12px;font-weight:600;color:var(--text);">Palmetto M1 Change Detection</div>
          <div id="monitorBadge" style="display:none;"></div>
        </div>
        <button onclick="checkRequirementsNow()" id="checkNowBtn" style="background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:6px 14px;font-size:11px;font-weight:600;cursor:pointer;min-height:32px;">Check Now</button>
      </div>
      <div id="monitorStatus" style="font-size:12px;color:var(--text-muted);"></div>
    </div>

    <!-- Requirements by section -->
    <div id="reqsList"></div>
  </div>

  <!-- Requirement detail/edit -->
  <div id="adminReqDetail" class="step">
    <button class="back-btn" onclick="showStep('reqs')">&larr; Back to requirements</button>
    <div class="step-label" id="reqDetailLabel">Requirement</div>

    <div style="background:var(--bg-card);border-radius:8px;padding:16px;margin-bottom:16px;">
      <div class="param-group">
        <label>ID</label>
        <div id="reqEditId" style="font-size:14px;font-weight:600;color:var(--text);"></div>
      </div>
      <div class="param-group">
        <label>Section</label>
        <div id="reqEditSection" style="font-size:13px;color:var(--text-secondary);"></div>
      </div>
      <div class="param-group">
        <label>Title</label>
        <input class="search-input" id="reqEditTitle" type="text" style="font-size:14px;">
      </div>
      <div class="param-group">
        <label>Validation Prompt</label>
        <textarea class="search-input" id="reqEditPrompt" rows="5" style="font-size:13px;resize:vertical;font-family:inherit;"></textarea>
      </div>
      <div class="param-group">
        <label>CompanyCam Task Titles (comma-separated)</label>
        <input class="search-input" id="reqEditTaskTitles" type="text" style="font-size:13px;" placeholder="e.g. Main Breaker, Breaker Rating">
      </div>
      <div class="param-group">
        <label>Keywords (comma-separated)</label>
        <input class="search-input" id="reqEditKeywords" type="text" style="font-size:13px;" placeholder="e.g. main breaker, ampere">
      </div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:12px;">Changes are saved in memory. They will reset on server restart until requirements are migrated to the database.</div>
      <button class="run-btn" onclick="saveRequirement()" style="background:#10b981;">Save Changes</button>
    </div>
  </div>

  <script>
    let selectedProjectId = null;
    let selectedProjectName = '';
    let selectedProjectState = '';
    let selectedChecklistId = null;
    let selectedChecklistName = '';
    let selectedManufacturer = null;
    let searchTimer = null;
    let currentOrgId = null;
    let currentUserId = null;

    // ── Nav drawer ──
    function openNav() {
      document.getElementById('navDrawer').classList.add('open');
      document.getElementById('navOverlay').classList.add('open');
    }
    function closeNav() {
      document.getElementById('navDrawer').classList.remove('open');
      document.getElementById('navOverlay').classList.remove('open');
    }

    // ── Theme toggle ──
    function toggleTheme() {
      const html = document.documentElement;
      const isDark = html.getAttribute('data-theme') === 'dark';
      html.setAttribute('data-theme', isDark ? 'light' : 'dark');
      localStorage.setItem('solclear-theme', isDark ? 'light' : 'dark');
      updateThemeIcon();
    }
    function updateThemeIcon() {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      document.getElementById('themeIconSun').style.display = isDark ? 'block' : 'none';
      document.getElementById('themeIconMoon').style.display = isDark ? 'none' : 'block';
    }
    // Apply saved theme on load
    (function() {
      const saved = localStorage.getItem('solclear-theme');
      if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.setAttribute('data-theme', 'dark');
      }
      updateThemeIcon();
    })();

    // ── Step navigation ──
    function showStep(n) {
      document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
      document.getElementById('homePage').style.display = 'none';
      if (n === 'home') {
        document.getElementById('homePage').style.display = 'block';
        loadHomeReports();
        return;
      }
      if (n === 'reports') {
        document.getElementById('reportsPage').classList.add('active');
        loadAllReports();
        return;
      }
      if (n === 'reqs') {
        document.getElementById('adminReqs').classList.add('active');
        loadRequirements();
        loadMonitorStatus();
        return;
      }
      if (n === 'reqDetail') {
        document.getElementById('adminReqDetail').classList.add('active');
        return;
      }
      if (n === 'orgs') {
        document.getElementById('adminOrgs').classList.add('active');
        loadOrgs();
        return;
      }
      if (n === 'orgCreate') {
        document.getElementById('adminOrgCreate').classList.add('active');
        return;
      }
      if (n === 'orgDetail') {
        document.getElementById('adminOrgDetail').classList.add('active');
        return;
      }
      if (n === 'userDetail') {
        document.getElementById('adminUserDetail').classList.add('active');
        return;
      }
      document.getElementById('step' + n).classList.add('active');
      if (n === 1 && !projectsLoaded) loadRecentProjects();
    }

    // ── Generic toggle helper ──
    function selectToggle(btn) {
      btn.parentElement.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    }

    function toggleKeyVis(inputId) {
      const inp = document.getElementById(inputId);
      const btn = inp.nextElementSibling;
      if (inp.type === 'password') { inp.type = 'text'; btn.textContent = 'Hide'; }
      else { inp.type = 'password'; btn.textContent = 'Show'; }
    }

    function statusBadgeHtml(status) {
      const colors = {active:'#10b981',demo:'#3b82f6',inactive:'#9ca3af',onboarding:'#f59e0b'};
      const bg = {active:'#ecfdf5',demo:'#eff6ff',inactive:'#f3f4f6',onboarding:'#fffbeb'};
      return '<span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;background:'+
        (bg[status]||'#f3f4f6')+';color:'+(colors[status]||'#6b7280')+';">'+status.toUpperCase()+'</span>';
    }

    function roleBadgeHtml(role) {
      const colors = {superadmin:'#7c3aed',admin:'#2563eb',reviewer:'#0891b2',crew:'#059669'};
      const bg = {superadmin:'#f5f3ff',admin:'#eff6ff',reviewer:'#ecfeff',crew:'#ecfdf5'};
      return '<span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;background:'+
        (bg[role]||'#f3f4f6')+';color:'+(colors[role]||'#6b7280')+';">'+role+'</span>';
    }

    // ── Organizations ──
    async function loadOrgs() {
      const list = document.getElementById('orgsList');
      list.innerHTML = spinnerHtml('Loading organizations...');
      try {
        const r = await fetch('/api/organizations');
        const orgs = await r.json();
        if (!orgs.length) {
          list.innerHTML = '<div style="color:#9ca3af;padding:12px;font-size:13px;">No organizations yet.</div>';
          return;
        }
        list.innerHTML = orgs.map(o => `
          <div class="list-item" onclick="openOrg(${o.id})" style="border-left:3px solid ${
            {active:'#10b981',demo:'#3b82f6',inactive:'#9ca3af',onboarding:'#f59e0b'}[o.status] || '#e5e7eb'
          };">
            <div style="display:flex;align-items:center;gap:8px;">
              <span class="name">${esc(o.name)}</span>
              ${statusBadgeHtml(o.status)}
            </div>
            <div class="detail">${o.user_count} user${o.user_count!==1?'s':''} · ${o.report_count} report${o.report_count!==1?'s':''}</div>
          </div>
        `).join('');
      } catch (e) { list.innerHTML = '<div style="color:#ef4444;padding:12px;">Error loading organizations</div>'; }
    }

    function showCreateOrg() {
      document.getElementById('newOrgName').value = '';
      showStep('orgCreate');
    }

    async function createOrg() {
      const name = document.getElementById('newOrgName').value.trim();
      if (!name) { alert('Name is required'); return; }
      const statusBtn = document.querySelector('[data-param="org-status"].selected');
      const status = statusBtn ? statusBtn.dataset.value : 'onboarding';
      try {
        const r = await fetch('/api/organizations', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name, status})
        });
        const org = await r.json();
        if (org.error) { alert(org.error); return; }
        openOrg(org.id);
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function openOrg(orgId) {
      currentOrgId = orgId;
      showStep('orgDetail');
      const detail = document.getElementById('adminOrgDetail');
      try {
        const r = await fetch('/api/organizations/' + orgId);
        const org = await r.json();
        document.getElementById('orgDetailLabel').textContent = org.name;
        document.getElementById('orgEditName').value = org.name || '';
        document.getElementById('orgCcKey').value = '';
        document.getElementById('orgCcKey').placeholder = org.companycam_api_key_set ? 'Key is set (enter new value to change)' : 'Not set';
        document.getElementById('orgAnthKey').value = '';
        document.getElementById('orgAnthKey').placeholder = org.anthropic_api_key_set ? 'Key is set (enter new value to change)' : 'Not set';
        // Set status toggle
        document.querySelectorAll('[data-param="org-edit-status"]').forEach(b => {
          b.classList.toggle('selected', b.dataset.value === org.status);
        });
        // Render users
        renderOrgUsers(org.users || []);
      } catch (e) { alert('Error loading org: ' + e.message); }
    }

    function renderOrgUsers(users) {
      document.getElementById('orgUserCount').textContent = users.length + ' user' + (users.length !== 1 ? 's' : '');
      const list = document.getElementById('orgUsersList');
      if (!users.length) { list.innerHTML = '<div style="color:#9ca3af;font-size:12px;">No users yet.</div>'; return; }
      list.innerHTML = users.map(u => `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border-light);${u.is_active ? '' : 'opacity:0.5;'}">
          <div style="flex:1;cursor:pointer;" onclick="openUser(${u.id})">
            <div style="font-weight:500;font-size:13px;color:#3b82f6;">${esc(u.full_name || (u.first_name + ' ' + u.last_name))}${u.is_active ? '' : ' <span style="font-size:10px;color:#ef4444;font-weight:700;">INACTIVE</span>'}</div>
            <div style="font-size:11px;color:var(--text-muted)">${esc(u.email)}${u.phone ? ' · ' + esc(u.phone) : ''}</div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            ${roleBadgeHtml(u.role)}
            <button onclick="toggleUser(${u.id})" style="background:none;border:1px solid ${u.is_active ? '#ef4444' : '#10b981'};color:${u.is_active ? '#ef4444' : '#10b981'};border-radius:6px;padding:4px 10px;font-size:10px;font-weight:600;cursor:pointer;min-height:28px;">
              ${u.is_active ? 'Deactivate' : 'Activate'}
            </button>
          </div>
        </div>
      `).join('');
    }

    async function saveOrg() {
      const statusBtn = document.querySelector('[data-param="org-edit-status"].selected');
      const data = {
        name: document.getElementById('orgEditName').value.trim(),
        status: statusBtn ? statusBtn.dataset.value : 'onboarding',
      };
      // Only send API keys if user entered a new value (don't clear existing keys)
      const ccKey = document.getElementById('orgCcKey').value.trim();
      const anthKey = document.getElementById('orgAnthKey').value.trim();
      if (ccKey) data.companycam_api_key = ccKey;
      if (anthKey) data.anthropic_api_key = anthKey;
      try {
        const r = await fetch('/api/organizations/' + currentOrgId, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(data)
        });
        const org = await r.json();
        if (org.error) { alert(org.error); return; }
        document.getElementById('orgDetailLabel').textContent = org.name;
        alert('Saved!');
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function addUser() {
      const first_name = document.getElementById('addUserFirst').value.trim();
      const last_name = document.getElementById('addUserLast').value.trim();
      const email = document.getElementById('addUserEmail').value.trim();
      const phone = document.getElementById('addUserPhone').value.trim() || null;
      const password = document.getElementById('addUserPassword').value.trim();
      const role = document.getElementById('addUserRole').value;
      if (!email || !first_name || !last_name) { alert('First name, last name, and email required'); return; }
      try {
        const r = await fetch('/api/organizations/' + currentOrgId + '/users', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({email, first_name, last_name, phone, password, role})
        });
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        document.getElementById('addUserFirst').value = '';
        document.getElementById('addUserLast').value = '';
        document.getElementById('addUserEmail').value = '';
        document.getElementById('addUserPhone').value = '';
        document.getElementById('addUserPassword').value = '';
        openOrg(currentOrgId);  // refresh
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function openUser(userId) {
      currentUserId = userId;
      // Set back button to return to the current org
      document.getElementById('userDetailBack').onclick = () => openOrg(currentOrgId);
      showStep('userDetail');
      try {
        const r = await fetch('/api/users/' + userId);
        const u = await r.json();
        document.getElementById('userDetailLabel').textContent = u.full_name || (u.first_name + ' ' + u.last_name);
        document.getElementById('editUserFirst').value = u.first_name || '';
        document.getElementById('editUserLast').value = u.last_name || '';
        document.getElementById('editUserEmail').value = u.email || '';
        document.getElementById('editUserPhone').value = u.phone || '';
        document.querySelectorAll('[data-param="edit-user-role"]').forEach(b => {
          b.classList.toggle('selected', b.dataset.value === u.role);
        });
        // Status info
        const info = document.getElementById('userStatusInfo');
        let statusHtml = '<strong>Status:</strong> ' + (u.is_active ? '<span style="color:#10b981;">Active</span>' : '<span style="color:#ef4444;">Inactive</span>');
        if (u.deactivated_at) statusHtml += ' · Deactivated: ' + new Date(u.deactivated_at).toLocaleDateString();
        if (u.created_at) statusHtml += ' · Created: ' + new Date(u.created_at).toLocaleDateString();
        info.innerHTML = statusHtml;
      } catch (e) { alert('Error loading user: ' + e.message); }
    }

    async function saveUser() {
      const roleBtn = document.querySelector('[data-param="edit-user-role"].selected');
      const data = {
        first_name: document.getElementById('editUserFirst').value.trim(),
        last_name: document.getElementById('editUserLast').value.trim(),
        email: document.getElementById('editUserEmail').value.trim(),
        phone: document.getElementById('editUserPhone').value.trim() || null,
        role: roleBtn ? roleBtn.dataset.value : 'crew',
      };
      if (!data.first_name || !data.last_name || !data.email) { alert('First name, last name, and email are required'); return; }
      try {
        const r = await fetch('/api/users/' + currentUserId, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(data)
        });
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        document.getElementById('userDetailLabel').textContent = result.full_name || (result.first_name + ' ' + result.last_name);
        alert('User updated!');
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function toggleUser(userId) {
      try {
        const r = await fetch('/api/users/' + userId + '/toggle', {method: 'POST'});
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        openOrg(currentOrgId);  // refresh
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function uploadCsv() {
      const file = document.getElementById('csvUpload').files[0];
      if (!file) return;
      const text = await file.text();
      try {
        const r = await fetch('/api/organizations/' + currentOrgId + '/users/csv', {
          method: 'POST',
          headers: {'Content-Type': 'text/csv'},
          body: text
        });
        const result = await r.json();
        const div = document.getElementById('csvResult');
        let html = '<span style="color:#10b981;font-weight:600;">' + result.total + ' users created</span>';
        if (result.errors && result.errors.length) {
          html += '<br><span style="color:#ef4444;">' + result.errors.join('<br>') + '</span>';
        }
        div.innerHTML = html;
        document.getElementById('csvUpload').value = '';
        openOrg(currentOrgId);  // refresh
      } catch (e) { alert('Error: ' + e.message); }
    }

    // ── Recent reports ──
    // ── Requirements ──
    let reqsData = [];

    async function loadRequirements() {
      const list = document.getElementById('reqsList');
      list.innerHTML = spinnerHtml('Loading requirements...');
      try {
        const r = await fetch('/api/requirements');
        reqsData = await r.json();
        // Group by section
        const sections = {};
        reqsData.forEach(req => {
          (sections[req.section] = sections[req.section] || []).push(req);
        });
        let html = '';
        for (const [section, reqs] of Object.entries(sections)) {
          html += `<div style="margin-bottom:16px;">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:var(--text-muted);font-weight:600;padding:8px 0;border-bottom:2px solid var(--border);">${esc(section)}</div>`;
          reqs.forEach(req => {
            let changeBadge = '';
            let borderColor = req.optional ? 'var(--border)' : '#3b82f6';
            if (req.change_status === 'new') {
              changeBadge = '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:#ecfdf5;color:#065f46;">+ NEW</span>';
              borderColor = '#10b981';
            } else if (req.change_status === 'changed') {
              changeBadge = '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:#fffbeb;color:#92400e;">UPDATED</span>';
              borderColor = '#f59e0b';
            } else if (req.change_status === 'removed') {
              changeBadge = '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:#fef2f2;color:#991b1b;">REMOVED</span>';
              borderColor = '#ef4444';
            }
            const stubNote = req.is_stub ? '<div style="font-size:11px;color:#f59e0b;margin-top:4px;font-weight:600;">Needs configuration before use in checks</div>' : '';
            html += `
              <div class="list-item" onclick="openRequirement('${req.id}')" style="margin-top:6px;border-left:3px solid ${borderColor};">
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                  <span style="font-size:10px;font-weight:700;color:var(--text-muted);min-width:28px;">${req.id}</span>
                  <span style="font-size:13px;font-weight:500;color:var(--text);">${esc(req.title)}</span>
                  ${changeBadge}
                  ${req.optional ? '<span style="font-size:9px;background:var(--border-light);color:var(--text-muted);padding:1px 5px;border-radius:3px;font-weight:600;">OPTIONAL</span>' : ''}
                </div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">Tasks: ${req.task_titles.length ? req.task_titles.join(', ') : 'none mapped'}</div>
                ${stubNote}
              </div>`;
          });
          html += '</div>';
        }
        list.innerHTML = html;
      } catch (e) {
        list.innerHTML = '<div style="color:#ef4444;">Error loading requirements</div>';
      }
    }

    async function loadMonitorStatus() {
      const el = document.getElementById('monitorStatus');
      try {
        const r = await fetch('/api/requirements/monitor/status');
        const data = await r.json();
        if (data.status === 'no_baseline') {
          el.innerHTML = 'No baseline saved yet. Click "Check Now" to create one.';
        } else {
          const date = new Date(data.saved_at).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'});
          el.innerHTML = `Last checked: ${date} · Hash: ${data.hash}...`;
        }
      } catch (e) {
        el.innerHTML = 'Could not load monitor status';
      }
    }

    async function checkRequirementsNow() {
      const btn = document.getElementById('checkNowBtn');
      const el = document.getElementById('monitorStatus');
      const badge = document.getElementById('monitorBadge');
      btn.disabled = true;
      btn.textContent = 'Checking...';
      el.innerHTML = 'Fetching Palmetto requirements page...';
      document.getElementById('changeAlert').style.display = 'none';
      try {
        const r = await fetch('/api/requirements/check', {method: 'POST'});
        const data = await r.json();
        // Coverage gap alert (applies to all statuses)
        if (data.missing_ids && data.missing_ids.length) {
          const alert = document.getElementById('changeAlert');
          alert.style.display = 'block';
          alert.style.background = '#fffbeb';
          alert.style.borderColor = '#f59e0b';
          document.getElementById('changeSummary').innerHTML =
            '<div style="color:#92400e;"><strong>Coverage gap:</strong> ' + data.missing_ids.length + ' requirement(s) found on Palmetto\\'s page that are not configured in our system:</div>' +
            '<div style="margin-top:6px;">' + data.missing_ids.map(id =>
              '<span style="display:inline-block;font-size:11px;font-weight:700;padding:3px 8px;border-radius:4px;background:#fef2f2;color:#991b1b;margin:2px 4px 2px 0;">' + esc(id) + '</span>'
            ).join('') + '</div>' +
            '<div style="margin-top:8px;font-size:12px;color:#92400e;">Click "Check Now" again after the page has changed to auto-create stubs, or add these manually in the requirements editor.</div>';
          document.getElementById('changeDiff').style.display = 'none';
        }

        if (data.status === 'baseline_created') {
          el.innerHTML = `<span style="color:#3b82f6;font-weight:600;">Baseline created.</span> ${data.message} Hash: ${data.hash}...`;
          badge.style.display = 'inline-block';
          badge.innerHTML = '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:#eff6ff;color:#3b82f6;">BASELINE SET</span>';
        } else if (data.status === 'no_changes') {
          const hasMissing = data.missing_ids && data.missing_ids.length;
          el.innerHTML = `<span style="color:${hasMissing ? '#f59e0b' : '#10b981'};font-weight:600;">${hasMissing ? 'Page unchanged, but coverage gaps found.' : 'No changes detected.'}</span> Hash: ${data.hash}...`;
          badge.style.display = 'inline-block';
          badge.innerHTML = hasMissing
            ? '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:#fffbeb;color:#92400e;">GAPS FOUND</span>'
            : '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:var(--badge-pass-bg);color:var(--badge-pass-text);">UP TO DATE</span>';
        } else if (data.status === 'changes_detected') {
          const isMaterial = data.material !== false;
          if (isMaterial) {
            el.innerHTML = `<span style="color:#ef4444;font-weight:600;">Material changes detected</span> · ${data.added} added, ${data.removed} removed`;
            badge.style.display = 'inline-block';
            badge.innerHTML = '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:var(--badge-fail-bg);color:var(--badge-fail-text);">CHANGED</span>';
          } else {
            el.innerHTML = `<span style="color:#10b981;font-weight:600;">No material changes.</span> Minor metadata updates only.`;
            badge.style.display = 'inline-block';
            badge.innerHTML = '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:var(--badge-pass-bg);color:var(--badge-pass-text);">UP TO DATE</span>';
          }
          // Only show alert banner for material changes
          const alert = document.getElementById('changeAlert');
          if (!isMaterial) { alert.style.display = 'none'; } else { alert.style.display = 'block'; }
          let rawSummary = data.summary || '';
          // Clean up any JSON/markdown artifacts from AI response
          rawSummary = rawSummary.replace(/^```(?:json)?/gm, '').replace(/```$/gm, '').trim();
          let summaryHtml = esc(rawSummary).replace(/\\n/g, '<br>');
          // Add structured badges
          const parts = [];
          if (data.new_ids && data.new_ids.length) {
            parts.push('<div style="margin-top:8px;"><span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;background:#ecfdf5;color:#065f46;">NEW</span> ' +
              data.new_ids.map(n => '<strong>' + esc(n.id) + '</strong> — ' + esc(n.title)).join(', ') + '</div>');
          }
          if (data.changed_ids && data.changed_ids.length) {
            parts.push('<div style="margin-top:4px;"><span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;background:#fffbeb;color:#92400e;">UPDATED</span> ' +
              data.changed_ids.map(c => '<strong>' + esc(c) + '</strong>').join(', ') + '</div>');
          }
          if (data.removed_ids && data.removed_ids.length) {
            parts.push('<div style="margin-top:4px;"><span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;background:#fef2f2;color:#991b1b;">REMOVED</span> ' +
              data.removed_ids.map(r => '<strong>' + esc(r) + '</strong>').join(', ') + '</div>');
          }
          document.getElementById('changeSummary').innerHTML = summaryHtml + parts.join('');
          document.getElementById('changeDiff').style.display = 'block';
          document.getElementById('changeDiffContent').textContent = data.diff_preview || '';
          document.getElementById('changeDiffContent').style.display = 'none';
          // Refresh requirements list to show badges
          loadRequirements();
        } else if (data.status === 'no_baseline') {
          el.innerHTML = data.message;
        } else if (data.error) {
          el.innerHTML = `<span style="color:#ef4444;">Error: ${esc(data.error)}</span>`;
        }
      } catch (e) {
        el.innerHTML = `<span style="color:#ef4444;">Error: ${e.message}</span>`;
      }
      btn.disabled = false;
      btn.textContent = 'Check Now';
    }

    function dismissAlert() {
      document.getElementById('changeAlert').style.display = 'none';
    }

    function toggleDiff() {
      const content = document.getElementById('changeDiffContent');
      const btn = document.getElementById('diffToggleBtn');
      if (content.style.display === 'none') {
        content.style.display = 'block';
        btn.innerHTML = 'Hide raw diff <span class="arrow">&#9652;</span>';
      } else {
        content.style.display = 'none';
        btn.innerHTML = 'Show raw diff <span class="arrow">&#9662;</span>';
      }
    }

    let currentReqId = null;

    function openRequirement(reqId) {
      currentReqId = reqId;
      const req = reqsData.find(r => r.id === reqId);
      if (!req) return;
      document.getElementById('reqDetailLabel').textContent = req.id + ' — ' + req.title;
      document.getElementById('reqEditId').textContent = req.id;
      document.getElementById('reqEditSection').textContent = req.section;
      document.getElementById('reqEditTitle').value = req.title;
      document.getElementById('reqEditPrompt').value = req.validation_prompt;
      document.getElementById('reqEditTaskTitles').value = req.task_titles.join(', ');
      document.getElementById('reqEditKeywords').value = req.keywords.join(', ');
      showStep('reqDetail');
    }

    async function saveRequirement() {
      const data = {
        title: document.getElementById('reqEditTitle').value.trim(),
        validation_prompt: document.getElementById('reqEditPrompt').value.trim(),
        task_titles: document.getElementById('reqEditTaskTitles').value.split(',').map(s => s.trim()).filter(Boolean),
        keywords: document.getElementById('reqEditKeywords').value.split(',').map(s => s.trim()).filter(Boolean),
      };
      try {
        const r = await fetch('/api/requirements/' + currentReqId, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(data)
        });
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        alert('Requirement updated (in memory).');
        showStep('reqs');
      } catch (e) { alert('Error: ' + e.message); }
    }

    // ── Reports ──
    function renderReportList(reports) {
      return reports.map(rpt => {
        const isPass = rpt.failed === 0;
        const date = new Date(rpt.timestamp * 1000).toLocaleDateString('en-US', {month:'short', day:'numeric', hour:'numeric', minute:'2-digit'});
        const img = rpt.featured_image
          ? `<img class="project-card-img" src="${rpt.featured_image}" alt="" loading="lazy">`
          : `<div class="project-card-img"></div>`;
        return `
          <a href="/report/${rpt.db_report_id || rpt.project_id}" class="project-card" style="text-decoration:none;color:inherit;border-left:3px solid ${isPass ? '#10b981' : '#ef4444'};">
            ${img}
            <div class="project-card-info">
              <div class="project-card-name">${esc(rpt.name)}${rpt.is_test ? ' <span style="font-size:9px;background:#eff6ff;color:#3b82f6;padding:1px 5px;border-radius:3px;font-weight:600;">TEST</span>' : ''}</div>
              <div class="project-card-addr">${rpt.passed}/${rpt.total} passed · ${date}</div>
            </div>
          </a>`;
      }).join('');
    }

    async function loadHomeReports() {
      const list = document.getElementById('homeRecentList');
      list.innerHTML = spinnerHtml();
      try {
        const r = await fetch('/api/reports');
        const reports = await r.json();
        if (!reports.length) {
          list.innerHTML = '<div style="color:#9ca3af;font-size:12px;">No reports yet. Run your first compliance check!</div>';
          return;
        }
        list.innerHTML = renderReportList(reports.slice(0, 3));
      } catch (e) {
        list.innerHTML = '<div style="color:#ef4444;font-size:12px;">Error loading reports</div>';
      }
    }

    let _allReports = [];

    async function loadAllReports() {
      const list = document.getElementById('recentList');
      list.innerHTML = spinnerHtml('Loading reports...');
      try {
        const r = await fetch('/api/reports');
        _allReports = await r.json();
        // Reset filters
        document.getElementById('reportSearch').value = '';
        document.getElementById('reportStatusFilter').value = 'all';
        document.getElementById('reportDateFrom').value = '';
        document.getElementById('reportDateTo').value = '';
        filterReports();
      } catch (e) {
        list.innerHTML = '<div style="color:#ef4444;padding:12px;">Error loading reports</div>';
      }
    }

    function clearDateFilter() {
      document.getElementById('reportDateFrom').value = '';
      document.getElementById('reportDateTo').value = '';
      filterReports();
    }

    function filterReports() {
      const search = (document.getElementById('reportSearch').value || '').trim().toLowerCase();
      const status = document.getElementById('reportStatusFilter').value;
      const fromVal = document.getElementById('reportDateFrom').value;
      const toVal = document.getElementById('reportDateTo').value;
      const fromTs = fromVal ? new Date(fromVal + 'T00:00:00').getTime() / 1000 : 0;
      const toTs = toVal ? new Date(toVal + 'T23:59:59').getTime() / 1000 : Infinity;

      const filtered = _allReports.filter(rpt => {
        // Search filter
        if (search && !(rpt.name || '').toLowerCase().includes(search)) return false;
        // Status filter
        if (status === 'passed' && rpt.failed > 0) return false;
        if (status === 'failed' && rpt.failed === 0) return false;
        // Date range filter
        if (rpt.timestamp < fromTs || rpt.timestamp > toTs) return false;
        return true;
      });

      const list = document.getElementById('recentList');
      const countEl = document.getElementById('reportCount');

      if (!_allReports.length) {
        list.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:13px;">No reports yet.</div>';
        countEl.textContent = '';
        return;
      }

      if (!filtered.length) {
        list.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:13px;">No reports match your filters.</div>';
        countEl.textContent = '0 of ' + _allReports.length + ' reports';
        return;
      }

      countEl.textContent = filtered.length === _allReports.length
        ? filtered.length + ' report' + (filtered.length !== 1 ? 's' : '')
        : filtered.length + ' of ' + _allReports.length + ' reports';
      list.innerHTML = renderReportList(filtered);
    }

    // Check for rerun parameter, otherwise load home page
    (function checkRerun() {
      const url = new URL(window.location.href);
      const rerunQs = url.searchParams.get('rerun');
      if (rerunQs) {
        // Auto-start a rerun of failed items
        const params = new URLSearchParams(rerunQs);
        showStep(4);
        document.getElementById('resultsList').innerHTML = '';
        document.getElementById('doneBanner').style.display = 'none';
        document.getElementById('loaderAnim').classList.remove('hidden');
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('progressText').textContent = 'Re-checking failed items...';
        document.getElementById('statusMsg').style.display = 'none';

        fetch('/start?' + params).then(r => r.json()).then(data => {
          if (!data.ok) { alert(data.error); showStep('home'); return; }
          document.getElementById('progressText').textContent = `Checking 0 / ${data.total}...`;
          listenSSE(data.total);
        }).catch(e => { alert('Failed: ' + e.message); showStep('home'); });

        // Clean up URL
        window.history.replaceState({}, '', '/');
        return;
      }
      loadHomeReports();
    })();

    // ── Step 1: Project search ──
    const searchInput = document.getElementById('projectSearch');
    let projectsLoaded = false;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => searchProjects(searchInput.value), 300);
    });

    function renderProjectCard(p) {
      const img = p.featured_image
        ? `<img class="project-card-img" src="${p.featured_image}" alt="" loading="lazy">`
        : `<div class="project-card-img" id="thumb-${p.id}"></div>`;
      const addr = [p.address, p.city, p.state].filter(Boolean).join(', ');
      return `
        <div class="project-card" onclick="selectProject('${p.id}', '${esc(p.name)}', '${esc(p.state)}')">
          ${img}
          <div class="project-card-info">
            <div class="project-card-name">${esc(p.name)}</div>
            <div class="project-card-addr">${esc(addr)}</div>
            ${p.checklist_count !== undefined ? `<div class="project-card-meta"><span class="project-card-dot"></span>${p.checklist_count} checklist${p.checklist_count !== 1 ? 's' : ''}</div>` : ''}
          </div>
        </div>`;
    }

    function loadThumbnails(projects) {
      // Lazy-load thumbnails for projects without a featured_image
      projects.forEach(p => {
        if (p.featured_image) return;
        const el = document.getElementById('thumb-' + p.id);
        if (!el) return;
        fetch('/api/projects/' + p.id + '/thumbnail')
          .then(r => r.json())
          .then(data => {
            if (data.url) {
              const img = document.createElement('img');
              img.className = 'project-card-img';
              img.src = data.url;
              img.loading = 'lazy';
              el.replaceWith(img);
            }
          })
          .catch(() => {});
      });
    }

    let _allProjects = [];

    async function loadRecentProjects() {
      // Load recent projects and async-check for checklists
      const list = document.getElementById('projectList');
      const loading = document.getElementById('projectListLoading');
      loading.innerHTML = spinnerHtml('Loading projects...');
      loading.style.display = 'block';
      list.innerHTML = '';
      // Reset filters
      document.getElementById('projectDateFrom').value = '';
      document.getElementById('projectDateTo').value = '';
      document.getElementById('projectDateField').value = 'updated_at';
      try {
        const r = await fetch('/api/projects');
        const projects = await r.json();
        if (!projects.length) { loading.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:13px;">No projects found</div>'; return; }
        loading.style.display = 'none';

        // Show all projects immediately, then async-enrich with checklist counts
        list.innerHTML = projects.map(p => renderProjectCard(p)).join('');
        loadThumbnails(projects);

        // Async check checklists for each project and re-render with counts
        const enriched = await Promise.all(projects.map(async p => {
          try {
            const cr = await fetch('/api/projects/' + p.id + '/checklists');
            const cls = await cr.json();
            p.checklist_count = cls.length;
          } catch (e) { p.checklist_count = 0; }
          return p;
        }));

        // Re-render sorted: projects with checklists first
        _allProjects = enriched.sort((a, b) => b.checklist_count - a.checklist_count);
        filterProjects();
        projectsLoaded = true;
      } catch (e) {
        loading.innerHTML = '<div style="color:#ef4444;padding:12px;">Error loading projects</div>';
      }
    }

    function clearProjectDateFilter() {
      document.getElementById('projectDateFrom').value = '';
      document.getElementById('projectDateTo').value = '';
      filterProjects();
    }

    function filterProjects() {
      const field = document.getElementById('projectDateField').value;
      const fromVal = document.getElementById('projectDateFrom').value;
      const toVal = document.getElementById('projectDateTo').value;
      const fromTs = fromVal ? new Date(fromVal + 'T00:00:00').getTime() / 1000 : 0;
      const toTs = toVal ? new Date(toVal + 'T23:59:59').getTime() / 1000 : Infinity;

      const filtered = _allProjects.filter(p => {
        const ts = p[field] || 0;
        return ts >= fromTs && ts <= toTs;
      });

      const list = document.getElementById('projectList');
      const countEl = document.getElementById('projectCount');

      if (!filtered.length && _allProjects.length) {
        list.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:13px;">No projects match your date filter.</div>';
        countEl.textContent = '0 of ' + _allProjects.length + ' projects';
        return;
      }

      countEl.textContent = (fromVal || toVal)
        ? filtered.length + ' of ' + _allProjects.length + ' projects'
        : '';
      list.innerHTML = filtered.map(p => renderProjectCard(p)).join('');
      loadThumbnails(filtered);
    }

    async function searchProjects(query) {
      const list = document.getElementById('projectList');
      const loading = document.getElementById('projectListLoading');
      if (!query && projectsLoaded) return;  // don't re-fetch if clearing search
      loading.innerHTML = spinnerHtml('Searching...');
      loading.style.display = 'block';
      list.innerHTML = '';
      try {
        const r = await fetch('/api/projects?query=' + encodeURIComponent(query));
        const projects = await r.json();
        loading.style.display = 'none';
        if (!projects.length) { loading.style.display = 'block'; loading.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:13px;">No projects found</div>'; return; }
        list.innerHTML = projects.map(p => renderProjectCard(p)).join('');
        loadThumbnails(projects);
      } catch (e) { loading.textContent = 'Error loading projects'; }
    }

    function selectProject(id, name, state) {
      selectedProjectId = id;
      selectedProjectName = name;
      selectedProjectState = state || '';
      document.getElementById('selectedProject').textContent = name;
      showStep(2);
      loadChecklists(id);
    }

    // ── Step 2: Checklists ──
    async function loadChecklists(projectId) {
      const list = document.getElementById('checklistList');
      list.innerHTML = spinnerHtml('Loading checklists...');
      try {
        const r = await fetch('/api/projects/' + projectId + '/checklists');
        const cls = await r.json();
        if (!cls.length) { list.innerHTML = '<div style="color:#9ca3af;padding:12px;font-size:13px;">No checklists on this project</div>'; return; }
        list.innerHTML = cls.map(c => `
          <div class="list-item" onclick="selectChecklist('${c.id}', '${esc(c.name)}')">
            <div class="name">${esc(c.name)}</div>
            <div class="detail">${c.completed_at ? 'Completed' : 'In progress'}</div>
          </div>
        `).join('');
      } catch (e) { list.innerHTML = '<div style="color:#ef4444;padding:12px;">Error loading checklists</div>'; }
    }

    function selectChecklist(id, name) {
      selectedChecklistId = id;
      selectedChecklistName = name;
      document.getElementById('selectedProjectName2').textContent = selectedProjectName;
      document.getElementById('selectedChecklistName').textContent = name;
      document.getElementById('derivedInfo').style.display = 'block';
      selectedManufacturer = null;
      document.querySelectorAll('#step3 .toggle-btn').forEach(b => b.classList.remove('selected'));
      const btn = document.getElementById('runBtn');
      btn.disabled = true;
      btn.textContent = 'Select a manufacturer to continue';
      showStep(3);
    }

    // ── Step 3: Manufacturer selection ──
    function selectMfg(btn) {
      btn.parentElement.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedManufacturer = btn.dataset.value;
      const runBtn = document.getElementById('runBtn');
      runBtn.disabled = false;
      runBtn.textContent = 'Run Compliance Check';
    }

    // ── Step 4: Run check ──
    async function startCheck() {
      const btn = document.getElementById('runBtn');
      btn.disabled = true;
      btn.textContent = 'Starting...';

      const qs = new URLSearchParams({
        project_id: selectedProjectId,
        checklist_id: selectedChecklistId,
        manufacturer: selectedManufacturer,
        project_state: selectedProjectState,
      });

      try {
        const r = await fetch('/start?' + qs);
        const data = await r.json();
        if (!data.ok) { alert(data.error); btn.disabled = false; btn.textContent = 'Run Compliance Check'; return; }

        showStep(4);
        document.getElementById('resultsList').innerHTML = '';
        document.getElementById('doneBanner').style.display = 'none';
        document.getElementById('loaderAnim').classList.remove('hidden');
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('progressText').textContent = `Checking 0 / ${data.total}...`;
        document.getElementById('statusMsg').style.display = 'none';

        listenSSE(data.total);
      } catch (e) {
        alert('Failed to start: ' + e.message);
        btn.disabled = false;
        btn.textContent = 'Run Compliance Check';
      }
    }

    function listenSSE(total) {
      const es = new EventSource('/stream');
      let count = 0;

      es.onmessage = (e) => {
        const data = JSON.parse(e.data);

        if (data.type === 'status') {
          const msg = document.getElementById('statusMsg');
          msg.textContent = data.message;
          msg.style.display = 'block';
          return;
        }

        if (data.type === 'progress') {
          count = data.index;
          const pct = Math.round((count / data.total) * 100);
          document.getElementById('progressFill').style.width = pct + '%';
          document.getElementById('progressText').textContent = `Checking ${count} / ${data.total}...`;
          document.getElementById('statusMsg').style.display = 'none';
          document.getElementById('resultsToggle').style.display = 'block';
          appendResult(data.requirement);
          return;
        }

        if (data.type === 'done') {
          es.close();
          document.getElementById('loaderAnim').classList.add('hidden');
          const s = data.summary;
          const pct = Math.round((s.passed / s.total) * 100);
          document.getElementById('progressFill').style.width = '100%';
          document.getElementById('progressText').textContent = `Complete — ${s.passed}/${s.total} passed`;

          const banner = document.getElementById('doneBanner');
          const isPass = s.failed === 0 && s.missing === 0;
          banner.className = 'done-banner ' + (isPass ? 'done-pass' : 'done-fail');
          let ccLink = '';
          if (s.checklist_ids && s.checklist_ids.length) {
            ccLink = `<a class="cc-link" href="https://app.companycam.com/projects/${s.project_id}/todos/${s.checklist_ids[0]}" target="_blank">Open in CompanyCam</a>`;
          }
          const reportLink = `<a class="cc-link" href="/report/${s.db_report_id || s.project_id}" style="background:#111827;">View Full Report</a>`;
          banner.innerHTML = `
            <div>
              <div class="done-label">${isPass ? 'READY FOR SUBMISSION' : 'ACTION REQUIRED'}</div>
              <div class="done-stats">${s.passed} passed · ${s.failed} failed · ${s.missing} missing · ${s.total} required</div>
              <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
                ${reportLink}
                ${ccLink}
              </div>
            </div>
          `;
          banner.style.display = 'flex';

          document.getElementById('runBtn').disabled = false;
          document.getElementById('runBtn').textContent = 'Run Compliance Check';
          return;
        }

        if (data.type === 'error') {
          es.close();
          document.getElementById('loaderAnim').classList.add('hidden');
          document.getElementById('progressText').textContent = 'Error: ' + data.message;
          document.getElementById('runBtn').disabled = false;
          document.getElementById('runBtn').textContent = 'Run Compliance Check';
        }
      };

      es.onerror = () => {
        // EventSource auto-reconnects on most errors
      };
    }

    function appendResult(req) {
      const list = document.getElementById('resultsList');
      const status = req.status.toLowerCase();
      const badgeCls = 'badge-' + status;
      let reason = '';
      if (status !== 'pass' && req.reason) {
        let full = esc(req.reason);
        // Replace "Photo(s) N", "Photos N and M", "Photos N, M, and O" with clickable links
        const urls = req.photo_urls || {};
        function linkPhoto(num) {
          const url = urls[num];
          return url ? `<a href="${url}" target="_blank" style="color:#3b82f6;font-weight:500;">${num}</a>` : num;
        }
        full = full.replace(/Photos?\\s+(\\d+(?:\\s*(?:,\\s*(?:and\\s+)?|and\\s+|&amp;\\s*)\\d+)*)/gi, (match) => {
          return match.replace(/(\\d+)/g, (m, num) => linkPhoto(num));
        });
        const plainShort = esc(req.reason);
        const short = plainShort.length > 120 ? plainShort.substring(0, 120).replace(/\\s+\\S*$/, '') + '...' : null;
        if (short) {
          // Short version also gets links
          let shortLinked = esc(req.reason).substring(0, 120).replace(/\\s+\\S*$/, '') + '...';
          shortLinked = shortLinked.replace(/Photos?\\s+(\\d+(?:\\s*(?:,|and|&amp;)\\s*\\d+)*)/gi, (match) => {
            return match.replace(/(\\d+)/g, (m, num) => linkPhoto(num));
          });
          reason = `
            <div class="result-reason result-reason-short">${shortLinked}</div>
            <div class="result-reason result-reason-full" style="display:none">${full}</div>
            <button class="expand-btn" onclick="toggleResultReason(this)">Show more <span class="arrow">&#9662;</span></button>`;
        } else {
          reason = `<div class="result-reason">${full}</div>`;
        }
      }

      // Show the photo that was evaluated (key 1 in photo_urls is the selected winner)
      const evalUrl = (req.photo_urls || {})[1] || (req.photo_urls || {})['1'];
      const photoThumb = evalUrl
        ? `<a href="${evalUrl}" target="_blank" onclick="event.stopPropagation()" style="display:block;margin-top:8px;"><img src="${evalUrl}" style="width:100%;max-width:280px;border-radius:6px;border:2px solid var(--border);" loading="lazy"></a>`
        : '';

      list.insertAdjacentHTML('beforeend', `
        <div class="result-row ${status}" style="cursor:pointer;" onclick="this.classList.toggle('collapsed')">
          <div class="result-header">
            <span class="badge ${badgeCls}">${req.status}</span>
            <span class="result-id">${req.id}</span>
            <span class="result-title">${esc(req.title)}</span>
            <span class="collapse-arrow" style="margin-left:auto;color:var(--text-muted);font-size:10px;">&#9662;</span>
          </div>
          <div class="result-detail">
            ${photoThumb}
            ${reason}
          </div>
        </div>
      `);

      // No auto-scroll — let the user control their own scroll position
    }

    let _allCollapsed = false;
    function toggleAllResults() {
      _allCollapsed = !_allCollapsed;
      document.querySelectorAll('#resultsList .result-row').forEach(row => {
        if (_allCollapsed) row.classList.add('collapsed');
        else row.classList.remove('collapsed');
      });
      document.getElementById('toggleAllBtn').textContent = _allCollapsed ? 'Expand All' : 'Collapse All';
    }

    function toggleResultReason(btn) {
      event.stopPropagation();
      const full = btn.previousElementSibling;
      const short = full.previousElementSibling;
      if (full.style.display === 'none') {
        full.style.display = 'block';
        short.style.display = 'none';
        btn.innerHTML = 'Show less <span class="arrow">&#9652;</span>';
      } else {
        full.style.display = 'none';
        short.style.display = 'block';
        btn.innerHTML = 'Show more <span class="arrow">&#9662;</span>';
      }
    }

    let _spinId = 0;
    function spinnerHtml(msg) {
      const id = 'sp' + (++_spinId);
      return '<div class="spinner">' +
        '<svg viewBox="0 0 120 120" width="40" height="40">' +
        '<path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="var(--border)" stroke-width="8" stroke-linecap="round"/>' +
        '<circle cx="0" cy="0" r="7" fill="#F59E0B"><animateMotion dur="1.4s" repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.45 0 0.55 1"><mpath href="#' + id + '"/></animateMotion></circle>' +
        '<path id="' + id + '" d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="none"/>' +
        '</svg>' +
        (msg ? '<div class="spinner-text">' + esc(msg) + '</div>' : '') +
        '</div>';
    }

    function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
  </script>

  <div style="text-align:center;padding:32px 20px;font-size:11px;color:var(--text-muted);opacity:0.5;">&copy; 2026 Solclear. All rights reserved.</div>

</body>
</html>"""
