"""
Auth-flow HTML pages: login, forgot password, reset password, change password,
and the request-demo lead form.

These render before the user is logged in (or are simple standalone forms) and
don't use the main app shell. Styles come from tools/html/styles.py.
"""

from tools.html.styles import _AUTH_PAGE_STYLE, _AUTH_PAGE_LOGO


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

REQUEST_DEMO_HTML = ("""<!DOCTYPE html>
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
  <style>%%STYLE%%
    .card { max-width: 440px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">%%LOGO%%</div>
    <div class="title">Request a Demo</div>
    <div class="sub">See how Solclear can streamline your solar compliance workflow.</div>
    <div class="error" id="errMsg"></div>
    <div class="success" id="okMsg"></div>
    <form onsubmit="doRequest(event)" id="demoForm">
      <input class="input" id="demoName" type="text" placeholder="Your name *" required>
      <input class="input" id="demoEmail" type="email" placeholder="Email address">
      <input class="input" id="demoCompany" type="text" placeholder="Company name (optional)">
      <input class="input" id="demoPhone" type="tel" placeholder="Phone number">
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
    async function doRequest(e) {
      e.preventDefault();
      const btn = document.getElementById('demoBtn');
      const err = document.getElementById('errMsg');
      const ok = document.getElementById('okMsg');
      const email = document.getElementById('demoEmail').value.trim();
      const phone = document.getElementById('demoPhone').value.trim();
      if (!email && !phone) {
        err.textContent = 'Please provide either an email address or phone number.';
        err.style.display = 'block';
        return;
      }
      btn.disabled = true; btn.textContent = 'Sending...';
      err.style.display = 'none'; ok.style.display = 'none';
      try {
        const r = await fetch('/api/request-demo', {
          method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            name: document.getElementById('demoName').value.trim(),
            email: email,
            phone: phone,
            company: document.getElementById('demoCompany').value.trim(),
            message: document.getElementById('demoMessage').value.trim(),
          })
        });
        const data = await r.json();
        if (data.ok) {
          ok.textContent = data.message;
          ok.style.display = 'block';
          document.getElementById('demoForm').style.display = 'none';
          document.getElementById('backLink').style.display = 'none';
          document.getElementById('successMsg').style.display = 'block';
        } else {
          err.textContent = data.error || 'Something went wrong';
          err.style.display = 'block';
        }
      } catch (ex) { err.textContent = 'Connection error'; err.style.display = 'block'; }
      btn.disabled = false; btn.textContent = 'Request Demo';
    }
  </script>
</body>
</html>""").replace("%%STYLE%%", _AUTH_PAGE_STYLE).replace("%%LOGO%%", _AUTH_PAGE_LOGO)
