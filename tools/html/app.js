    let selectedProjectId = null;
    let selectedProjectName = '';
    let selectedProjectState = '';
    let selectedChecklistId = null;
    let selectedChecklistName = '';
    let selectedManufacturer = null;
    let searchTimer = null;
    let currentOrgId = null;
    let currentUserId = null;

    // ── Account sheet (mobile) ──
    function openAccountSheet() {
      document.getElementById('accountSheet').classList.add('open');
      document.getElementById('sheetOverlay').classList.add('open');
      setActiveTab('account');
    }
    function closeAccountSheet() {
      document.getElementById('accountSheet').classList.remove('open');
      document.getElementById('sheetOverlay').classList.remove('open');
    }

    // Legacy aliases — some inline handlers may still call closeNav/openNav.
    function closeNav() { closeAccountSheet(); }
    function openNav() { openAccountSheet(); }

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
      const show = (elId, v) => { const el = document.getElementById(elId); if (el) el.style.display = v; };
      show('themeIconSun', isDark ? 'block' : 'none');
      show('themeIconMoon', isDark ? 'none' : 'block');
      show('sidebarThemeIconSun', isDark ? 'block' : 'none');
      show('sidebarThemeIconMoon', isDark ? 'none' : 'block');
      const label = document.getElementById('sidebarThemeLabel');
      if (label) label.textContent = isDark ? 'Light mode' : 'Dark mode';
    }
    // Apply saved theme on load
    (function() {
      const saved = localStorage.getItem('solclear-theme');
      if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.setAttribute('data-theme', 'dark');
      }
      updateThemeIcon();
    })();

    // ── Nav/tab active state ──
    // Map step names to the tab/sidebar key they belong to (for active highlighting).
    const STEP_TO_NAV = {
      'home': 'home', 'reports': 'reports',
      1: 'check', 2: 'check', 3: 'check', 4: 'check',
      'orgs': 'orgs', 'orgCreate': 'orgs', 'orgDetail': 'orgs', 'userDetail': 'orgs',
      'reqs': 'reqs', 'reqDetail': 'reqs',
      'costs': 'costs',
      'devnotes': 'devnotes',
    };
    const NAV_TO_TAB = { home: 'home', check: 'check', reports: 'reports', orgs: 'account', reqs: 'account', costs: 'account', devnotes: 'account' };

    function setActiveTab(navKey) {
      document.querySelectorAll('.nav-item[data-nav]').forEach(el =>
        el.classList.toggle('active', el.dataset.nav === navKey));
      const tabKey = NAV_TO_TAB[navKey] || navKey;
      document.querySelectorAll('.tab-btn').forEach(el =>
        el.classList.toggle('active', el.dataset.tab === tabKey));
    }

    // navigate() is the sidebar/bottom-tab entry point. It routes to the
    // underlying showStep and keeps active-state in sync.
    function navigate(key) {
      closeAccountSheet();
      if (key === 'check') { showStep(1); setActiveTab('check'); return; }
      showStep(key);
      setActiveTab(STEP_TO_NAV[key] || key);
    }

    // ── Step navigation ──
    // Top-level sections get a real history entry so the browser back button
    // returns to them after viewing a report. Wizard sub-steps and detail
    // pages use replaceState — no separate history entry.
    const _PUSH_STEPS = new Set(['home', 'reports', 'reqs', 'orgs', 'orgCreate', 'costs', 'devnotes', 1]);

    function showStep(n, _fromPopstate) {
      if (!_fromPopstate) {
        if (_PUSH_STEPS.has(n)) {
          history.pushState({step: n}, '', '/');
        } else {
          history.replaceState({step: n}, '', '/');
        }
      }
      document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
      document.getElementById('homePage').style.display = 'none';
      setActiveTab(STEP_TO_NAV[n] || null);
      if (n === 'home') {
        document.getElementById('homePage').style.display = 'block';
        loadHomeReports();
        // Refresh "your check is still running / just completed" banners
        // every time the user lands on home — otherwise a user who
        // started a check then navigated away wouldn't see the banner
        // until the next page load. Cheap (~one DB query, no fan-out).
        fetchActiveChecks();
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
        loadReqChangeHistory();
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
      if (n === 'costs') {
        document.getElementById('adminCosts').classList.add('active');
        // Default non-superadmins to Performance (Costs is superadmin-only)
        const defaultTab = (_me && _me.role === 'superadmin') ? 'costs' : 'performance';
        switchAnalyticsTab(defaultTab);
        if (defaultTab === 'costs') loadCosts();
        return;
      }
      if (n === 'devnotes') {
        document.getElementById('adminDevNotes').classList.add('active');
        loadDevNotes();
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
      const cls = {active:'badge-success', demo:'badge-info', inactive:'badge-neutral', onboarding:'badge-warning'}[status] || 'badge-neutral';
      return '<span class="badge ' + cls + '">' + status.toUpperCase() + '</span>';
    }

    function roleBadgeHtml(role) {
      // Role → semantic badge class. Superadmin uses purple (error) to stand out; the rest map to sensible tones.
      const cls = {superadmin:'badge-error', admin:'badge-info', reviewer:'badge-info', crew:'badge-success'}[role] || 'badge-neutral';
      return '<span class="badge ' + cls + '">' + role + '</span>';
    }

    // ── Organizations ──
    async function loadOrgs() {
      const list = document.getElementById('orgsList');
      list.innerHTML = skeletonCards(3);
      try {
        const r = await fetch('/api/organizations');
        const orgs = await r.json();
        if (!orgs.length) {
          // Only show the "Create" CTA to superadmins — org admins can't
          // spawn new orgs anyway.
          const isSuper = _me && _me.role === 'superadmin';
          list.innerHTML = isSuper
            ? emptyState('No organizations yet',
                         'Create your first organization to onboard a client.',
                         'Create Organization', 'showCreateOrg()')
            : emptyState('No organization found',
                         'Your account is not linked to an organization yet. Ask a superadmin to set it up.');
          return;
        }
        list.innerHTML = orgs.map(o => {
          const borderColor = {active:'var(--success)', demo:'var(--accent)', inactive:'var(--text-muted)', onboarding:'var(--warning)'}[o.status] || 'var(--border)';
          return `
          <div class="list-item" onclick="openOrg(${o.id})" style="border-left:3px solid ${borderColor};">
            <div style="display:flex;align-items:center;gap:8px;">
              <span class="name">${esc(o.name)}</span>
              ${statusBadgeHtml(o.status)}
            </div>
            <div class="detail">${o.user_count} user${o.user_count!==1?'s':''} · ${o.report_count} report${o.report_count!==1?'s':''}</div>
          </div>`;
        }).join('');
      } catch (e) { list.innerHTML = errorAlert('Could not load organizations'); }
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

    function switchOrgTab(tab) {
      ['settings', 'users', 'activity'].forEach(t => {
        const panel = document.getElementById('orgTab' + t.charAt(0).toUpperCase() + t.slice(1));
        const btn = document.querySelector('[data-org-tab="' + t + '"]');
        if (panel) panel.style.display = t === tab ? '' : 'none';
        if (btn) btn.classList.toggle('active', t === tab);
      });
      if (tab === 'activity') loadOrgAuditLog(currentOrgId);
    }

    async function openOrg(orgId) {
      currentOrgId = orgId;
      showStep('orgDetail');
      switchOrgTab('settings');  // always start on Settings tab
      try {
        const r = await fetch('/api/organizations/' + orgId);
        const org = await r.json();
        document.getElementById('orgDetailLabel').textContent = org.name;
        document.getElementById('orgEditName').value = org.name || '';
        document.getElementById('orgCcKey').value = '';
        document.getElementById('orgCcKey').placeholder = org.companycam_api_key_set ? 'Key is set (enter new value to change)' : 'Not set';
        document.getElementById('orgAnthKey').value = '';
        document.getElementById('orgAnthKey').placeholder = org.anthropic_api_key_set ? 'Key is set (enter new value to change)' : 'Not set';
        // Status toggles
        document.querySelectorAll('[data-param="org-edit-status"]').forEach(b => {
          b.classList.toggle('selected', b.dataset.value === org.status);
        });
        // Make name/status read-only for reviewers (can see current value,
        // can't change it). Save button is already hidden via .admin-write.
        const canWrite = _me && (_me.role === 'superadmin' || _me.role === 'admin');
        document.getElementById('orgEditName').disabled = !canWrite;
        document.querySelectorAll('[data-param="org-edit-status"]').forEach(b => {
          b.disabled = !canWrite;
          b.style.cursor = canWrite ? 'pointer' : 'default';
        });
        // Render users — renderOrgUsers itself checks role for write actions
        renderOrgUsers(org.users || []);
        // Audit log loads lazily when the Activity tab is clicked
      } catch (e) { alert('Error loading org: ' + e.message); }
    }

    async function loadOrgAuditLog(orgId) {
      const container = document.getElementById('orgAuditLog');
      if (!container) return;
      container.innerHTML = '<div style="color:var(--text-muted);font-size:12px;">Loading activity…</div>';
      try {
        const r = await fetch('/api/admin/audit_log');
        if (!r.ok) { container.innerHTML = ''; return; }
        const data = await r.json();
        // Server already scopes by org (admin = own org, superadmin = all).
        // No client-side filter needed.
        const entries = data.entries || [];
        if (!entries.length) {
          container.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px 0;">No activity recorded yet.</div>';
          return;
        }
        const _ACTION_LABELS = {
          login: 'Logged in', report_run: 'Ran check', report_cancel: 'Cancelled check',
          requirement_recheck: 'Re-checked requirement', note_add: 'Added note',
          dev_note_triage: 'Triaged dev note', org_settings_change: 'Updated org settings',
          user_invite: 'Invited user', user_role_change: 'Changed user role',
        };
        container.innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:11px;">' +
          entries.slice(0, 50).map(e => {
            const label = _ACTION_LABELS[e.action] || e.action;
            const actor = e.actor_name || e.actor_email || 'System';
            const time = '<time class="ts-relative" datetime="' + esc(e.created_at || '') + '">' + esc(e.created_at || '') + '</time>';
            const meta = e.metadata && Object.keys(e.metadata).length
              ? '<span style="opacity:0.6;"> · ' + esc(JSON.stringify(e.metadata).slice(0, 60)) + '</span>'
              : '';
            return '<tr style="border-top:1px solid var(--border-light);">' +
              '<td style="padding:4px 6px;color:var(--text-muted);">' + time + '</td>' +
              '<td style="padding:4px 6px;font-weight:500;">' + esc(actor) + '</td>' +
              '<td style="padding:4px 6px;">' + esc(label) + meta + '</td>' +
              '</tr>';
          }).join('') + '</table>';
        if (typeof localizeTimestamps === 'function') localizeTimestamps(container);
      } catch (e) { container.innerHTML = ''; }
    }

    function renderOrgUsers(users) {
      document.getElementById('orgUserCount').textContent = users.length + ' user' + (users.length !== 1 ? 's' : '');
      const list = document.getElementById('orgUsersList');
      if (!users.length) { list.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px 0;">No users yet.</div>'; return; }
      // Reviewers see names/emails/roles only. Write actions (edit on click,
      // activate/deactivate) are admin+superadmin. Impersonate is
      // superadmin-only, and only offered when NOT already impersonating.
      const canWrite = _me && (_me.role === 'superadmin' || _me.role === 'admin');
      const realRole = _me && (_me.real_role || _me.role);
      const canImpersonate = realRole === 'superadmin' && !(_me && _me.is_impersonating);
      const myActiveId = _me && _me.user_id;
      list.innerHTML = users.map(u => {
        const nameLine = `<div style="font-weight:500;font-size:13px;color:${canWrite ? 'var(--accent)' : 'var(--text)'};">${esc(u.full_name || (u.first_name + ' ' + u.last_name))}${u.is_active ? '' : ' <span class="badge badge-danger" style="margin-left:4px;">INACTIVE</span>'}</div>`;
        const emailLine = `<div style="font-size:11px;color:var(--text-muted)">${esc(u.email)}${u.phone ? ' · ' + esc(u.phone) : ''}</div>`;
        const nameBlock = canWrite
          ? `<div style="flex:1;cursor:pointer;" onclick="openUser(${u.id})">${nameLine}${emailLine}</div>`
          : `<div style="flex:1;">${nameLine}${emailLine}</div>`;
        const toggleBtn = canWrite
          ? `<button onclick="toggleUser(${u.id})" style="background:none;border:1px solid ${u.is_active ? 'var(--danger)' : 'var(--success)'};color:${u.is_active ? 'var(--danger)' : 'var(--success)'};border-radius:6px;padding:4px 10px;font-size:10px;font-weight:600;cursor:pointer;min-height:28px;">${u.is_active ? 'Deactivate' : 'Activate'}</button>`
          : '';
        // Only show Impersonate for active users who aren't the current user
        const impersonateBtn = (canImpersonate && u.is_active && u.id !== myActiveId)
          ? `<button onclick="startImpersonate(${u.id}, ${JSON.stringify(u.full_name || u.email || '').replace(/"/g, '&quot;')})" style="background:var(--bg-subtle);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 10px;font-size:10px;font-weight:600;cursor:pointer;min-height:28px;">Impersonate</button>`
          : '';
        return `
          <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border-light);${u.is_active ? '' : 'opacity:0.5;'}">
            ${nameBlock}
            <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
              ${roleBadgeHtml(u.role)}
              ${impersonateBtn}
              ${toggleBtn}
            </div>
          </div>`;
      }).join('');
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
      const role = document.getElementById('addUserRole').value;
      if (!email || !first_name || !last_name) { alert('First name, last name, and email required'); return; }
      try {
        const r = await fetch('/api/organizations/' + currentOrgId + '/users', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({email, first_name, last_name, phone, role})
        });
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        document.getElementById('addUserFirst').value = '';
        document.getElementById('addUserLast').value = '';
        document.getElementById('addUserEmail').value = '';
        document.getElementById('addUserPhone').value = '';
        const msg = result.invite_sent
          ? `${first_name} ${last_name} added. An invitation email has been sent to ${email}.`
          : `${first_name} ${last_name} added. (Invite email could not be sent — check Resend configuration.)`;
        alert(msg);
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
        if (u.deactivated_at) statusHtml += ' · Deactivated: ' + formatTimestamp(u.deactivated_at);
        if (u.created_at) statusHtml += ' · Created: ' + formatTimestamp(u.created_at);
        // Show invite status + resend button for users who haven't set a password
        if (!u.has_password) {
          statusHtml += '<div style="margin-top:10px;padding:10px 12px;background:var(--warning-subtle);border-radius:8px;border:1px solid var(--warning);display:flex;align-items:center;gap:12px;flex-wrap:wrap;">';
          statusHtml += '<span style="font-size:var(--text-xs);color:var(--warning-text);flex:1;">⏳ Awaiting invitation — password not yet set.</span>';
          statusHtml += `<button onclick="resendInvite(${u.id})" style="background:var(--warning);color:var(--text-inverse);border:none;border-radius:6px;padding:6px 12px;font-size:11px;font-weight:600;cursor:pointer;min-height:32px;white-space:nowrap;">Resend invite</button>`;
          statusHtml += '</div>';
        }
        // Superadmin-only: permanent delete
        if (_me && _me.role === 'superadmin') {
          const userName = esc(u.first_name + ' ' + u.last_name);
          statusHtml += `<div style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border);">
            <button onclick="deleteUser(${u.id}, '${userName}')" style="background:#ef4444;color:#fff;border:none;border-radius:6px;padding:8px 16px;font-size:12px;font-weight:600;cursor:pointer;">Delete User Permanently</button>
          </div>`;
        }
        info.innerHTML = statusHtml;
      } catch (e) { alert('Error loading user: ' + e.message); }
    }

    async function resendInvite(userId) {
      try {
        const r = await fetch('/api/users/' + userId + '/resend-invite', {method: 'POST'});
        const data = await r.json();
        if (data.ok) {
          alert(data.message);
          openUser(userId);  // refresh to reflect any state change
        } else {
          alert(data.error || 'Could not resend invite');
        }
      } catch (e) { alert('Error: ' + e.message); }
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

    async function deleteUser(userId, name) {
      if (!confirm('Permanently delete ' + name + '? This cannot be undone.')) return;
      try {
        const r = await fetch('/api/users/' + userId + '/delete', {method: 'POST'});
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        alert(result.message);
        openOrg(currentOrgId);
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

    async function loadReqChangeHistory() {
      const palBox = document.getElementById('reqPalmettoHistory');
      const manBox = document.getElementById('reqManualHistory');
      if (!palBox && !manBox) return;
      try {
        const r = await fetch('/api/requirements/change_history');
        if (!r.ok) return;
        const data = await r.json();

        // Box 1: Palmetto spec changes
        if (palBox) {
          const pChanges = data.palmetto_changes || [];
          if (!pChanges.length) {
            palBox.innerHTML = '<div style="color:var(--text-muted);font-size:11px;padding:8px 0;">No changes recorded yet. Run "Check Now" to establish a baseline.</div>';
          } else {
            palBox.innerHTML = pChanges.map(c => {
              const time = '<time class="ts-relative" datetime="' + esc(c.detected_at || '') + '">' + esc(c.detected_at || '') + '</time>';
              const newPills = (c.new_req_ids || []).map(id => '<span class="badge badge-pass" style="margin:1px 2px;">+' + esc(id) + '</span>').join('');
              const changedPills = (c.changed_req_ids || []).map(id => '<span class="badge badge-missing" style="margin:1px 2px;">~' + esc(id) + '</span>').join('');
              const removedPills = (c.removed_req_ids || []).map(id => '<span class="badge badge-fail" style="margin:1px 2px;">−' + esc(id) + '</span>').join('');
              return '<div style="padding:8px 0;border-bottom:1px solid var(--border-light);">' +
                '<div style="display:flex;justify-content:space-between;margin-bottom:4px;">' +
                  '<span style="font-size:10px;color:var(--text-muted);">' + time + '</span>' +
                  '<span style="font-size:10px;color:var(--text-muted);">+' + (c.lines_added||0) + ' −' + (c.lines_removed||0) + '</span>' +
                '</div>' +
                (c.summary ? '<div style="font-size:11px;line-height:1.4;color:var(--text);">' + esc(c.summary) + '</div>' : '') +
                (newPills || changedPills || removedPills ? '<div style="margin-top:4px;">' + newPills + changedPills + removedPills + '</div>' : '') +
              '</div>';
            }).join('');
          }
          if (typeof localizeTimestamps === 'function') localizeTimestamps(palBox);
        }

        // Box 2: Manual requirement edits
        if (manBox) {
          const mEdits = data.manual_edits || [];
          if (!mEdits.length) {
            manBox.innerHTML = '<div style="color:var(--text-muted);font-size:11px;padding:8px 0;">No manual edits recorded yet.</div>';
          } else {
            const _FIELD_LABELS = {
              validation_prompt: 'prompt',
              task_titles: 'CompanyCam task titles',
              keywords: 'keywords',
              title: 'title',
              selection_criteria: 'selection criteria',
            };
            manBox.innerHTML = mEdits.map(e => {
              const time = '<time class="ts-relative" datetime="' + esc(e.created_at || '') + '">' + esc(e.created_at || '') + '</time>';
              const actor = esc(e.actor_name || e.actor_email || 'Unknown');
              const meta = e.metadata || {};
              const code = esc(meta.req_code || '');
              const fields = (meta.changed_fields || [])
                .map(f => _FIELD_LABELS[f] || f)
                .join(', ');
              const verb = (meta.changed_fields || []).length === 1
                ? 'Changed ' + fields
                : 'Changed ' + fields;
              return '<div style="padding:8px 0;border-bottom:1px solid var(--border-light);">' +
                '<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2px;">' +
                  '<span style="font-size:12px;font-weight:600;">' + code + ' — ' + esc(verb) + '</span>' +
                  '<span style="font-size:10px;color:var(--text-muted);white-space:nowrap;margin-left:8px;">' + time + '</span>' +
                '</div>' +
                '<div style="font-size:11px;color:var(--text-muted);">' + actor + '</div>' +
              '</div>';
            }).join('');
          }
          if (typeof localizeTimestamps === 'function') localizeTimestamps(manBox);
        }
      } catch (e) { /* silently ignore */ }
    }

    async function loadRequirements() {
      const list = document.getElementById('reqsList');
      list.innerHTML = skeletonCards(5);
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
        list.innerHTML = errorAlert('Could not load requirements');
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
          const date = formatTimestamp(data.saved_at);
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
          alert.style.display = 'flex';
          alert.classList.remove('alert-error');
          alert.classList.add('alert-warning');
          document.getElementById('changeSummary').innerHTML =
            "<div><strong>Coverage gap:</strong> " + data.missing_ids.length + " requirement(s) found on Palmetto's page that are not configured in our system:</div>" +
            '<div style="margin-top:6px;">' + data.missing_ids.map(id =>
              '<span class="badge badge-danger" style="margin:2px 4px 2px 0;">' + esc(id) + '</span>'
            ).join('') + '</div>' +
            '<div style="margin-top:8px;font-size:var(--text-sm);">Click "Check Now" again after the page has changed to auto-create stubs, or add these manually in the requirements editor.</div>';
          document.getElementById('changeDiff').style.display = 'none';
        }

        if (data.status === 'baseline_created') {
          el.innerHTML = `<span style="color:var(--accent);font-weight:600;">Baseline created.</span> ${data.message} Hash: ${data.hash}...`;
          badge.style.display = 'inline-block';
          badge.innerHTML = '<span class="badge badge-info">BASELINE SET</span>';
        } else if (data.status === 'no_changes') {
          const hasMissing = data.missing_ids && data.missing_ids.length;
          el.innerHTML = `<span style="color:${hasMissing ? 'var(--warning)' : 'var(--success)'};font-weight:600;">${hasMissing ? 'Page unchanged, but coverage gaps found.' : 'No changes detected.'}</span> Hash: ${data.hash}...`;
          badge.style.display = 'inline-block';
          badge.innerHTML = hasMissing
            ? '<span class="badge badge-warning">GAPS FOUND</span>'
            : '<span class="badge badge-pass">UP TO DATE</span>';
        } else if (data.status === 'changes_detected') {
          const isMaterial = data.material !== false;
          if (isMaterial) {
            el.innerHTML = `<span style="color:var(--danger);font-weight:600;">Material changes detected</span> · ${data.added} added, ${data.removed} removed`;
            badge.style.display = 'inline-block';
            badge.innerHTML = '<span class="badge badge-fail">CHANGED</span>';
          } else {
            el.innerHTML = `<span style="color:var(--success);font-weight:600;">No material changes.</span> Minor metadata updates only.`;
            badge.style.display = 'inline-block';
            badge.innerHTML = '<span class="badge badge-pass">UP TO DATE</span>';
          }
          // Only show alert banner for material changes
          const alert = document.getElementById('changeAlert');
          alert.classList.remove('alert-warning');
          alert.classList.add('alert-error');
          if (!isMaterial) { alert.style.display = 'none'; } else { alert.style.display = 'flex'; }
          let rawSummary = data.summary || '';
          // Clean up any JSON/markdown artifacts from AI response
          rawSummary = rawSummary.replace(/^```(?:json)?/gm, '').replace(/```$/gm, '').trim();
          let summaryHtml = esc(rawSummary).replace(/\\n/g, '<br>');
          // Add structured badges
          const parts = [];
          if (data.new_ids && data.new_ids.length) {
            parts.push('<div style="margin-top:8px;"><span class="badge badge-success">NEW</span> ' +
              data.new_ids.map(n => '<strong>' + esc(n.id) + '</strong> — ' + esc(n.title)).join(', ') + '</div>');
          }
          if (data.changed_ids && data.changed_ids.length) {
            parts.push('<div style="margin-top:4px;"><span class="badge badge-warning">UPDATED</span> ' +
              data.changed_ids.map(c => '<strong>' + esc(c) + '</strong>').join(', ') + '</div>');
          }
          if (data.removed_ids && data.removed_ids.length) {
            parts.push('<div style="margin-top:4px;"><span class="badge badge-danger">REMOVED</span> ' +
              data.removed_ids.map(r => '<strong>' + esc(r) + '</strong>').join(', ') + '</div>');
          }
          document.getElementById('changeSummary').innerHTML = summaryHtml + parts.join('');
          document.getElementById('changeDiff').style.display = 'block';
          document.getElementById('changeDiffContent').textContent = data.diff_preview || '';
          document.getElementById('changeDiffContent').style.display = 'none';
          // Refresh requirements list to show badges
          loadRequirements();
        } else if (data.status === 'no_baseline') {
          el.textContent = data.message;
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
        const nReview = rpt.needs_review || 0;
        const isCancelled = rpt.status === 'cancelled';
        const hasFailures = rpt.failed > 0 || (rpt.missing || 0) > 0;
        // Border rail: gray for cancelled (data is partial so the usual
        // red/green signal is misleading), red for failures/missing, cyan
        // if only items needing review, green if everything's clean.
        let railColor = 'var(--success)';
        if (isCancelled) railColor = 'var(--text-muted)';
        else if (hasFailures) railColor = 'var(--danger)';
        else if (nReview > 0) railColor = 'var(--review)';
        const reviewHint = nReview ? ` · ${nReview} to review` : '';
        // formatTimestamp accepts an epoch-seconds number directly,
        // converts to local tz, returns relative-or-absolute.
        const date = formatTimestamp(rpt.timestamp);
        const img = rpt.featured_image
          ? `<img class="project-card-img" src="${rpt.featured_image}" alt="" loading="lazy">`
          : `<div class="project-card-img"></div>`;
        // Badges: TEST (existing) + CANCELLED if the run was stopped early.
        // Cancelled badge uses warning styling so it stands out as "this
        // report is incomplete by design, not a failed run."
        const testBadge = rpt.is_test ? ' <span class="badge badge-info" style="margin-left:4px;">TEST</span>' : '';
        const cancelBadge = isCancelled ? ' <span class="badge badge-warning" style="margin-left:4px;">CANCELLED</span>' : '';
        const statusLine = isCancelled
          ? `Partial — ${rpt.passed}/${rpt.total} completed before cancel · ${date}`
          : `${rpt.passed}/${rpt.total} passed${reviewHint} · ${date}`;
        return `
          <a href="/report/${rpt.db_report_id || rpt.project_id}" class="project-card" style="text-decoration:none;color:inherit;border-left:4px solid ${railColor};">
            ${img}
            <div class="project-card-info">
              <div class="project-card-name">${esc(rpt.name)}${testBadge}${cancelBadge}</div>
              <div class="project-card-addr">${statusLine}</div>
            </div>
          </a>`;
      }).join('');
    }

    async function loadHomeReports() {
      const list = document.getElementById('homeRecentList');
      list.innerHTML = skeletonCards(2);
      try {
        const r = await fetch('/api/reports');
        const reports = await r.json();
        if (!reports.length) {
          list.innerHTML = '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">No reports yet. Run your first compliance check!</div>';
          return;
        }
        list.innerHTML = renderReportList(reports.slice(0, 3));
      } catch (e) {
        list.innerHTML = errorAlert('Could not load reports');
      }
    }

    let _allReports = [];

    async function loadAllReports() {
      const list = document.getElementById('recentList');
      list.innerHTML = skeletonCards(4);
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
        list.innerHTML = errorAlert('Could not load reports');
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
        // Status filter — "passed" means fully clean (no fails and no review items);
        // "failed" means any hard failures; "needs_review" surfaces reports where
        // a human still needs to weigh in on at least one item.
        const nReview = rpt.needs_review || 0;
        if (status === 'passed' && (rpt.failed > 0 || nReview > 0)) return false;
        if (status === 'failed' && rpt.failed === 0) return false;
        if (status === 'needs_review' && nReview === 0) return false;
        // Date range filter
        if (rpt.timestamp < fromTs || rpt.timestamp > toTs) return false;
        return true;
      });

      const list = document.getElementById('recentList');
      const countEl = document.getElementById('reportCount');

      if (!_allReports.length) {
        list.innerHTML = emptyState(
          'No reports yet',
          'Run your first compliance check to see it here.',
          'Start a new check',
          "navigate('check')"
        );
        countEl.textContent = '';
        return;
      }

      if (!filtered.length) {
        list.innerHTML = emptyState(
          'No matches',
          'No reports match your current filters. Try clearing the search or date range.'
        );
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
          const cw = document.getElementById('cancelRunWrap');
          const cb = document.getElementById('cancelRunBtn');
          if (cw) cw.style.display = 'block';
          if (cb) { cb.disabled = false; cb.textContent = 'Cancel checks'; }
          _currentRunId = data.run_id || null;
          listenSSE(data.run_id, data.total);
        }).catch(e => { alert('Failed: ' + e.message); showStep('home'); });

        // Clean up URL, seed history state so popstate works from here
        history.replaceState({step: 'home'}, '', '/');
        return;
      }
      // Seed initial history state so the very first popstate event has a step
      history.replaceState({step: 'home'}, '', '/');
      loadHomeReports();
    })();

    // Restore the correct SPA step when the user presses the browser back button
    // (e.g. after viewing a /report/... page and returning to the SPA).
    window.addEventListener('popstate', function(e) {
      const step = (e.state && e.state.step != null) ? e.state.step : 'home';
      showStep(step, true);
    });

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

      // Per-checklist breakdown. `p.checklists` is populated by the async
      // enrichment in loadRecentProjects; on initial render (stage 1) it
      // is undefined. We show a shimmering "Loading checklist progress"
      // placeholder during stage 1 so the card doesn't look finished
      // before suddenly growing a new row once stage 2 completes.
      //
      // If p.checklists_error is set (enrichment failed), we fall through
      // silently — no placeholder, no noise. If both are set to valid
      // values we render the real data below.
      let checklistsHtml = '';
      if (Array.isArray(p.checklists) && p.checklists.length) {
        checklistsHtml = '<div class="project-checklists">' + p.checklists.map(c => {
          const total = c.total_tasks || 0;
          const done = c.completed_tasks || 0;
          const pct = total ? Math.round((done / total) * 100) : 0;
          const barCls = (total && done === total) ? 'progress-thin-fill complete' : 'progress-thin-fill';
          const count = total ? `${done}/${total}` : (c.completed_at ? 'Done' : '–');
          const bar = total
            ? `<div class="progress-thin"><div class="${barCls}" style="width:${pct}%"></div></div>`
            : '';
          return `
            <div class="project-checklist-row">
              <div class="project-checklist-meta">
                <span class="project-checklist-name">${esc(c.name)}</span>
                <span class="project-checklist-count">${count}</span>
              </div>
              ${bar}
            </div>`;
        }).join('') + '</div>';
      } else if (p.checklist_count !== undefined) {
        checklistsHtml = `<div class="project-card-meta"><span class="project-card-dot"></span>${p.checklist_count} checklist${p.checklist_count !== 1 ? 's' : ''}</div>`;
      } else if (!p.checklists_error) {
        // Stage 1: enrichment hasn't returned yet for this project.
        checklistsHtml = '<div class="project-checklists-loading"></div>';
      }

      return `
        <div class="project-card" onclick="selectProject('${p.id}', '${esc(p.name)}', '${esc(p.state)}')">
          ${img}
          <div class="project-card-info">
            <div class="project-card-name">${esc(p.name)}</div>
            <div class="project-card-addr">${esc(addr)}</div>
            ${checklistsHtml}
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
      loading.innerHTML = skeletonCards(4);
      loading.style.display = 'block';
      list.innerHTML = '';
      // Reset filters
      document.getElementById('projectDateFrom').value = '';
      document.getElementById('projectDateTo').value = '';
      document.getElementById('projectDateField').value = 'updated_at';
      try {
        const r = await fetch('/api/projects');
        const projects = await r.json();
        if (projects.error) {
          loading.innerHTML = errorAlert('CompanyCam error: ' + esc(projects.error));
          return;
        }
        if (!projects.length) {
          loading.innerHTML = emptyState(
            'No projects found',
            "Check your CompanyCam API key in Organizations, or try a different search."
          );
          return;
        }
        loading.style.display = 'none';

        // Show all projects immediately, then async-enrich with checklist counts
        list.innerHTML = projects.map(p => renderProjectCard(p)).join('');
        loadThumbnails(projects);

        // Async enrich each project with its full checklist array (names +
        // task completion counts). CompanyCam rate limit is 240 req/min —
        // we're well within it for a page of 25 projects.
        const enriched = await Promise.all(projects.map(async p => {
          try {
            const cr = await fetch('/api/projects/' + p.id + '/checklists');
            p.checklists = await cr.json();
            p.checklist_count = Array.isArray(p.checklists) ? p.checklists.length : 0;
          } catch (e) {
            p.checklists = [];
            p.checklist_count = 0;
            // Flag so renderProjectCard stops showing the shimmer on this
            // card (we failed; no point pretending data is still coming).
            p.checklists_error = true;
          }
          return p;
        }));

        // Re-render sorted: projects with checklists first
        _allProjects = enriched.sort((a, b) => b.checklist_count - a.checklist_count);
        filterProjects();
        projectsLoaded = true;
      } catch (e) {
        loading.innerHTML = errorAlert('Could not load projects from CompanyCam');
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
      loading.innerHTML = skeletonCards(3);
      loading.style.display = 'block';
      list.innerHTML = '';
      try {
        const r = await fetch('/api/projects?query=' + encodeURIComponent(query));
        const projects = await r.json();
        loading.style.display = 'none';
        if (!projects.length) {
          loading.style.display = 'block';
          loading.innerHTML = emptyState('No matches', 'Try a different search term.');
          return;
        }
        list.innerHTML = projects.map(p => renderProjectCard(p)).join('');
        loadThumbnails(projects);
      } catch (e) { loading.innerHTML = errorAlert('Could not load projects'); }
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
        if (!cls.length) { list.innerHTML = emptyState('No checklists', "This project has no CompanyCam checklists. Add one in CompanyCam, then come back."); return; }
        list.innerHTML = cls.map(c => renderChecklistRow(c)).join('');
      } catch (e) { list.innerHTML = errorAlert('Could not load checklists'); }
    }

    function renderChecklistRow(c) {
      const total = c.total_tasks || 0;
      const done = c.completed_tasks || 0;
      const pct = total ? Math.round((done / total) * 100) : 0;
      const barCls = (total && done === total) ? 'progress-thin-fill complete' : 'progress-thin-fill';
      const doneTag = c.completed_at ? ' · <span style="color:var(--success-text);font-weight:600;">Marked complete</span>' : '';
      const detail = total
        ? `${done}/${total} tasks complete${doneTag}`
        : (c.completed_at ? 'Completed' : 'No tasks');
      const bar = total
        ? `<div class="progress-thin"><div class="${barCls}" style="width:${pct}%"></div></div>`
        : '';
      return `
        <div class="list-item" onclick="selectChecklist('${c.id}', '${esc(c.name)}')">
          <div class="name">${esc(c.name)}</div>
          <div class="detail">${detail}</div>
          ${bar}
        </div>`;
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
        // Reveal the Cancel button now that a run is in progress.
        const cancelWrap = document.getElementById('cancelRunWrap');
        const cancelBtn = document.getElementById('cancelRunBtn');
        if (cancelWrap) cancelWrap.style.display = 'block';
        if (cancelBtn) { cancelBtn.disabled = false; cancelBtn.textContent = 'Cancel checks'; }

        // Store run_id for the cancel button and future reconnect logic.
        _currentRunId = data.run_id || null;
        listenSSE(data.run_id, data.total);
      } catch (e) {
        alert('Failed to start: ' + e.message);
        btn.disabled = false;
        btn.textContent = 'Run Compliance Check';
      }
    }

    // Tracks the currently-in-progress run so cancelRun() knows which
    // run to cancel. Reset to null when a run completes/cancels.
    let _currentRunId = null;

    async function cancelRun() {
      const btn = document.getElementById('cancelRunBtn');
      if (!btn) return;
      if (!confirm('Cancel the remaining compliance checks?\\nThe requirement that is currently running will still finish (about 5-15 seconds).')) return;
      btn.disabled = true;
      btn.textContent = 'Cancelling…';
      try {
        const r = await fetch('/api/cancel', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({run_id: _currentRunId}),
        });
        const data = await r.json();
        if (!data.ok) {
          alert(data.error || 'Could not cancel');
          btn.disabled = false;
          btn.textContent = 'Cancel checks';
        }
        // Otherwise: wait for the SSE 'cancelled' event to finish teardown.
      } catch (e) {
        alert('Cancel request failed: ' + e.message);
        btn.disabled = false;
        btn.textContent = 'Cancel checks';
      }
    }

    function listenSSE(runId, total) {
      const es = new EventSource('/stream?run=' + (runId || ''));
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

        if (data.type === 'done' || data.type === 'cancelled') {
          es.close();
          _currentRunId = null;  // run is over — clear so stale cancel doesn't fire
          document.getElementById('loaderAnim').classList.add('hidden');
          const s = data.summary;
          const wasCancelled = data.type === 'cancelled';
          const cancelWrap = document.getElementById('cancelRunWrap');
          if (cancelWrap) cancelWrap.style.display = 'none';

          document.getElementById('progressFill').style.width = wasCancelled
            ? Math.round(((s.passed + s.failed + s.missing + (s.needs_review||0)) / (s.total || 1)) * 100) + '%'
            : '100%';
          document.getElementById('progressText').textContent = wasCancelled
            ? `Cancelled — ${s.passed}/${s.total} completed before stopping`
            : `Complete — ${s.passed}/${s.total} passed`;

          const banner = document.getElementById('doneBanner');
          const nReview = s.needs_review || 0;
          // "Ready for submission" only when nothing needs a human — failures,
          // missing photos, and review items all block the ready state.
          // A cancelled run is never "ready" — partial results by definition.
          const isPass = !wasCancelled && s.failed === 0 && s.missing === 0 && nReview === 0;
          banner.className = 'done-banner ' + (isPass ? 'done-pass' : 'done-fail');
          let ccLink = '';
          if (s.checklist_ids && s.checklist_ids.length) {
            ccLink = `<a class="cc-link" href="https://app.companycam.com/projects/${s.project_id}/todos/${s.checklist_ids[0]}" target="_blank">Open in CompanyCam</a>`;
          }
          // color:#fff overrides .cc-link's var(--text-inverse), which is dark
          // in dark mode and would otherwise be invisible against #111827.
          const reportLink = `<a class="cc-link" href="/report/${s.db_report_id || s.project_id}" style="background:#111827;color:#fff;">${wasCancelled ? 'View Partial Report' : 'View Report'}</a>`;
          const reviewStat = nReview ? ` · ${nReview} to review` : '';
          const label = wasCancelled
            ? 'CANCELLED — PARTIAL RESULTS'
            : (isPass ? 'READY FOR SUBMISSION' : 'ACTION REQUIRED');
          banner.innerHTML = `
            <div>
              <div class="done-label">${label}</div>
              <div class="done-stats">${s.passed} passed · ${s.failed} failed · ${s.missing} missing${reviewStat} · ${s.total} required</div>
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
          const cancelWrap = document.getElementById('cancelRunWrap');
          if (cancelWrap) cancelWrap.style.display = 'none';
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
      // Pretty label for the badge (e.g. NEEDS_REVIEW → "NEEDS REVIEW")
      const statusLabel = (req.status === 'NEEDS_REVIEW') ? 'NEEDS REVIEW' : req.status;
      let reason = '';
      if (status !== 'pass' && req.reason) {
        let full = esc(req.reason);
        // Replace "Photo(s) N", "Photos N and M", "Photos N, M, and O" with clickable links
        const urls = req.photo_urls || {};
        function linkPhoto(num) {
          const url = urls[num];
          return url ? `<a href="${url}" target="_blank" style="color:var(--accent);font-weight:500;">${num}</a>` : num;
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
        <div class="result-row ${status}" data-req-id="${req.id}" style="cursor:pointer;" onclick="this.classList.toggle('collapsed')">
          <div class="result-header">
            <span class="badge ${badgeCls}">${statusLabel}</span>
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

      // Re-sort all cards into canonical requirement order each time one
      // arrives. With max_workers=2 checks complete out of order, so
      // without this the live view looks jumbled (R4 before R2, etc.).
      _sortResultsList(list);
    }

    // Canonical section order + numeric position within section.
    // Matches the REQUIREMENTS array order in compliance_check.py.
    const _SECTION_ORDER = {PS:0, R:1, E:2, S:3, SC:4, SI:5};
    function _reqSortKey(code) {
      const m = code && code.match(/^([A-Za-z]+)(\\d+)$/);
      if (!m) return 9999;
      const section = _SECTION_ORDER[m[1].toUpperCase()] ?? 9;
      return section * 100 + parseInt(m[2], 10);
    }
    function _sortResultsList(list) {
      const rows = Array.from(list.querySelectorAll('.result-row[data-req-id]'));
      rows.sort((a, b) => _reqSortKey(a.dataset.reqId) - _reqSortKey(b.dataset.reqId));
      rows.forEach(r => list.appendChild(r));  // DOM reorder (stable, no flicker)
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

    // ── UI helpers: empty state, error alert, skeletons ──
    function emptyState(title, desc, ctaLabel, ctaOnClick) {
      const cta = (ctaLabel && ctaOnClick)
        ? '<button class="btn btn-primary" onclick="' + ctaOnClick + '">' + esc(ctaLabel) + '</button>'
        : '';
      const descHtml = desc ? '<div class="empty-state-desc">' + esc(desc) + '</div>' : '';
      return '<div class="empty-state">' +
        '<div class="empty-state-icon"><svg viewBox="0 0 120 120"><circle cx="60" cy="54" r="14" fill="#F59E0B"/><path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round"/></svg></div>' +
        '<div class="empty-state-title">' + esc(title) + '</div>' +
        descHtml + cta + '</div>';
    }
    function errorAlert(msg) {
      return '<div class="alert alert-error">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>' +
        '<div>' + esc(msg) + '</div></div>';
    }
    function skeletonCards(n) {
      let s = '';
      for (let i = 0; i < (n || 3); i++) {
        s += '<div class="skeleton-card">' +
          '<div class="skeleton skeleton-thumb"></div>' +
          '<div class="skeleton-lines">' +
            '<div class="skeleton skeleton-line skeleton-line-lg"></div>' +
            '<div class="skeleton skeleton-line skeleton-line-md"></div>' +
            '<div class="skeleton skeleton-line skeleton-line-sm"></div>' +
          '</div></div>';
      }
      return s;
    }

    // ── Current user (role-aware nav) ──
    // Role-visibility classes. Elements carrying any of these start with
    // inline style="display:none" in the markup (so nothing flashes before
    // the role fetch returns). loadMe() reveals the ones this user is
    // allowed to see.
    //   .reviewer-plus  — shown to superadmin / admin / reviewer (hidden for crew)
    //   .admin-write    — shown to superadmin / admin  (hidden for reviewer + crew)
    //   .superadmin-only — shown to superadmin only
    let _me = null;
    function _applyRoleVisibility(role) {
      const visible = [];
      if (role === 'superadmin') visible.push('.superadmin-only', '.admin-write', '.reviewer-plus');
      else if (role === 'admin') visible.push('.admin-write', '.reviewer-plus');
      else if (role === 'reviewer') visible.push('.reviewer-plus');
      // crew: no gated classes revealed
      visible.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => { el.style.display = ''; });
      });
      // Section header text reflects the user's actual role instead of
      // the static "Admin" — a Superadmin doesn't have to wonder why
      // their tools are under an "Admin" heading.
      const labelText = {
        superadmin: 'Superadmin',
        admin: 'Admin',
        reviewer: 'Reviewer',
      }[role] || '';
      ['sidebarRoleLabel', 'accountSheetRoleLabel'].forEach(id => {
        const el = document.getElementById(id);
        if (el && labelText) el.textContent = labelText;
      });
    }
    async function loadMe() {
      try {
        const r = await fetch('/api/me');
        if (!r.ok) return;
        _me = await r.json();
        _applyRoleVisibility(_me && _me.role);
        _applyImpersonationBanner(_me);
        _applyPlatformStatus(_me && _me.platform_status);
      } catch (e) { /* silently ignore — non-critical */ }
    }
    loadMe();
    fetchActiveChecks();  // populate running / recently-completed banners
    refreshBellBadge();   // initial unread count for the top-bar bell

    // ── Top-bar bell (notifications) ──
    // Polls /api/notifications/unread_count every 60s for the badge.
    // The full list is only fetched when the user opens the dropdown
    // (toggleBellPanel) — saves a chunk of bandwidth on idle pages.
    async function refreshBellBadge() {
      try {
        const r = await fetch('/api/notifications/unread_count');
        if (!r.ok) return;
        const data = await r.json();
        _setBellBadge(data.unread_count || 0);
      } catch (e) { /* silently ignore */ }
    }
    setInterval(refreshBellBadge, 60000);

    function _setBellBadge(n) {
      // Two bell entry points (mobile top bar + desktop sidebar nav) so
      // sync both badges. Either may be hidden by the responsive layout
      // — that's fine, we update text either way.
      const text = n > 99 ? '99+' : String(n || 0);
      ['bellBadge', 'sidebarBellBadge'].forEach(id => {
        const badge = document.getElementById(id);
        if (!badge) return;
        if (!n || n <= 0) {
          badge.style.display = 'none';
        } else {
          badge.textContent = text;
          badge.style.display = 'inline-flex';
        }
      });
    }

    async function toggleBellPanel(ev) {
      ev && ev.stopPropagation();
      const panel = document.getElementById('bellPanel');
      if (!panel) return;
      const opening = panel.style.display !== 'flex';
      panel.style.display = opening ? 'flex' : 'none';
      panel.style.flexDirection = 'column';
      if (opening) {
        // Position the panel near whichever button was clicked. On
        // desktop that's the sidebar nav button; on mobile it's the
        // top-bar bell. Falls back to fixed top-right if we can't find
        // a click target (e.g. programmatic open).
        _positionBellPanel(panel, ev && ev.currentTarget);
        await refreshBellPanel();
        // Click-outside to close — installed only while open. Also
        // ignores clicks on either bell button so toggling works.
        setTimeout(() => {
          const handler = (e) => {
            const sidebarBtn = document.getElementById('sidebarBellBtn');
            const topbarBtn = document.getElementById('bellBtn');
            const onBell = (sidebarBtn && sidebarBtn.contains(e.target)) ||
                           (topbarBtn && topbarBtn.contains(e.target));
            if (!panel.contains(e.target) && !onBell) {
              panel.style.display = 'none';
              document.removeEventListener('click', handler);
            }
          };
          document.addEventListener('click', handler);
        }, 0);
      }
    }

    function _positionBellPanel(panel, btn) {
      // Reset any prior positioning
      panel.style.position = 'fixed';
      panel.style.top = '54px';
      panel.style.right = '8px';
      panel.style.left = 'auto';
      if (!btn) return;
      const rect = btn.getBoundingClientRect();
      // If the button is in the desktop sidebar (left side of viewport),
      // open the panel to the right of it. Otherwise (mobile top bar),
      // anchor to top-right under the bell.
      if (rect.right < window.innerWidth / 2) {
        panel.style.left = (rect.right + 8) + 'px';
        panel.style.right = 'auto';
        panel.style.top = Math.max(8, rect.top) + 'px';
      } else {
        panel.style.top = (rect.bottom + 6) + 'px';
        panel.style.right = Math.max(8, window.innerWidth - rect.right) + 'px';
        panel.style.left = 'auto';
      }
    }

    async function refreshBellPanel() {
      const list = document.getElementById('bellList');
      if (!list) return;
      try {
        const r = await fetch('/api/notifications');
        if (!r.ok) throw new Error('Could not load notifications');
        const data = await r.json();
        _setBellBadge(data.unread_count || 0);
        const rows = data.notifications || [];
        if (!rows.length) {
          list.innerHTML = '<div style="padding:24px 16px;text-align:center;color:var(--text-muted);font-size:var(--text-sm);">No notifications yet.</div>';
          return;
        }
        list.innerHTML = rows.map(_renderBellRow).join('');
        // Localize the timestamps we just injected
        if (typeof localizeTimestamps === 'function') localizeTimestamps(list);
      } catch (e) {
        list.innerHTML = '<div style="padding:24px 16px;text-align:center;color:var(--danger);font-size:var(--text-sm);">' + esc(e.message) + '</div>';
      }
    }

    function _renderBellRow(n) {
      const isUnread = !n.read_at;
      const cls = 'bell-row' + (isUnread ? ' bell-unread' : '');
      const href = n.link_url || '#';
      // Note: \\n here so Python's triple-quoted string outputs a literal
      // \\n into the JS regex. Bare \\n would be turned into an actual
      // newline in the source, splitting the regex across two lines and
      // breaking the parser ("Invalid regular expression: missing /").
      const body = n.body ? '<div class="bell-row-body">' + esc(n.body).replace(/\\n/g, '<br>') + '</div>' : '';
      const iso = n.created_at || '';
      const time = iso
        ? '<time class="ts-relative bell-row-time" datetime="' + esc(iso) + '"></time>'
        : '';
      return (
        '<a class="' + cls + '" href="' + esc(href) + '" data-notification-id="' + esc(n.id) + '" ' +
        'onclick="_onBellRowClick(event, ' + n.id + ')">' +
          '<div class="bell-row-title">' + esc(n.title || '') + '</div>' +
          body + time +
        '</a>'
      );
    }

    async function _onBellRowClick(ev, notificationId) {
      // Mark read in the background — don't block the navigation
      fetch('/api/notifications/' + notificationId + '/read', {method: 'POST'})
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && data.unread_count != null) _setBellBadge(data.unread_count);
        })
        .catch(() => {});
      // Let the <a> navigation proceed naturally; if href is '#' close panel
      const link = ev.currentTarget;
      if (link.getAttribute('href') === '#') {
        ev.preventDefault();
        document.getElementById('bellPanel').style.display = 'none';
      }
    }

    async function markAllNotificationsRead() {
      try {
        const r = await fetch('/api/notifications/read-all', {method: 'POST'});
        if (!r.ok) return;
        const data = await r.json();
        _setBellBadge(data.unread_count || 0);
        await refreshBellPanel();
      } catch (e) { /* silently ignore */ }
    }

    // ── Dev Notes triage tab ──
    // Three sub-tabs by status (open / acknowledged / corrected).
    // _devNotesAll holds the currently-loaded set; filterDevNotesTab
    // re-renders + persists active tab in _devNotesActiveStatus.
    let _devNotesAll = [];
    let _devNotesActiveStatus = 'open';

    async function loadDevNotes() {
      const list = document.getElementById('devNotesList');
      try {
        // Always pull all 3 statuses so the count badges + tab counts
        // are accurate without needing 3 fetches.
        const r = await fetch('/api/dev_notes');
        if (!r.ok) throw new Error('Could not load dev notes');
        const data = await r.json();
        _devNotesAll = data.notes || [];
        _updateDevNoteCounts(data.counts || {});
        _renderDevNotes();
      } catch (e) {
        list.innerHTML = errorAlert('Could not load dev notes: ' + e.message);
      }
    }

    function _updateDevNoteCounts(counts) {
      ['open', 'acknowledged', 'corrected'].forEach(s => {
        const el = document.getElementById('dnCount' + s.charAt(0).toUpperCase() + s.slice(1));
        if (el) el.textContent = counts[s] || 0;
      });
      // Sidebar badge: unread = open count, since that's what the
      // superadmin actually needs to act on.
      const badge = document.getElementById('sidebarDevNotesBadge');
      const open = counts.open || 0;
      if (badge) {
        if (open > 0) {
          badge.textContent = open > 99 ? '99+' : String(open);
          badge.style.display = 'inline-flex';
        } else {
          badge.style.display = 'none';
        }
      }
    }

    function filterDevNotesTab(status) {
      _devNotesActiveStatus = status;
      document.querySelectorAll('.dev-notes-tab').forEach(t =>
        t.classList.toggle('active', t.dataset.dnTab === status));
      _renderDevNotes();
    }

    function _renderDevNotes() {
      const list = document.getElementById('devNotesList');
      const filtered = _devNotesAll.filter(n => (n.dev_status || 'open') === _devNotesActiveStatus);
      if (!filtered.length) {
        const empty = {
          open: 'No dev notes awaiting triage. 🎉',
          acknowledged: 'Nothing in progress.',
          corrected: 'No resolved notes yet.',
        }[_devNotesActiveStatus];
        list.innerHTML = '<div style="padding:32px 16px;text-align:center;color:var(--text-muted);font-size:var(--text-sm);">' + esc(empty) + '</div>';
        return;
      }
      list.innerHTML = filtered.map(_renderDevNoteCard).join('');
      if (typeof localizeTimestamps === 'function') localizeTimestamps(list);
    }

    function _renderDevNoteCard(n) {
      const status = n.dev_status || 'open';
      const cls = 'dev-note-card dn-' + status;
      const author = esc(n.author_name || n.author_email || 'Unknown');
      const reqLine = n.requirement_code
        ? esc(n.requirement_code) + ' — ' + esc(n.requirement_title || '')
        : '';
      const project = n.project_name ? esc(n.project_name) : ('Project ' + esc(n.project_cc_id || ''));
      const reportLink = n.report_id ? '<a href="/report/' + n.report_id + '">Open report</a>' : '';
      const orgLine = n.org_name ? ' · ' + esc(n.org_name) : '';
      const time = n.created_at
        ? '<time class="ts-relative" datetime="' + esc(n.created_at) + '"></time>'
        : '';
      const repliesHtml = (n.replies && n.replies.length)
        ? '<div class="dn-replies">' + n.replies.map(_renderDevNoteReply).join('') + '</div>'
        : '';
      // Action buttons depend on current status. Cancel reply button
      // is hidden unless the editor is open.
      // data-status avoids quote-nesting issues between the JS string,
      // the HTML attribute delimiters, and the JS argument inside onclick.
      const noteId = n.id;
      let actions = '';
      if (status === 'open') {
        actions += '<button class="btn btn-sm btn-primary" data-note-id="' + noteId + '" data-status="acknowledged" onclick="setDevNoteStatus(+this.dataset.noteId, this.dataset.status)">Acknowledge</button>';
        actions += '<button class="btn btn-sm btn-subtle" data-note-id="' + noteId + '" data-status="corrected" onclick="setDevNoteStatus(+this.dataset.noteId, this.dataset.status)">Mark corrected</button>';
      } else if (status === 'acknowledged') {
        actions += '<button class="btn btn-sm btn-primary" data-note-id="' + noteId + '" data-status="corrected" onclick="setDevNoteStatus(+this.dataset.noteId, this.dataset.status)">Mark corrected</button>';
        actions += '<button class="btn btn-sm btn-subtle" data-note-id="' + noteId + '" data-status="open" onclick="setDevNoteStatus(+this.dataset.noteId, this.dataset.status)">Reopen</button>';
      } else {
        actions += '<button class="btn btn-sm btn-subtle" data-note-id="' + noteId + '" data-status="open" onclick="setDevNoteStatus(+this.dataset.noteId, this.dataset.status)">Reopen</button>';
      }
      actions += '<button class="btn btn-sm btn-ghost" onclick="openDevNoteReply(' + n.id + ', this)">Reply</button>';

      return (
        '<div class="dev-note-card ' + cls + '" id="devNote-' + n.id + '">' +
          '<div class="dn-meta">' +
            '<span class="dn-meta-author">' + author + '</span>' +
            time +
            (orgLine ? '<span>' + orgLine + '</span>' : '') +
            (reqLine ? '<span>· ' + reqLine + '</span>' : '') +
            '<span style="margin-left:auto;">' + reportLink + '</span>' +
          '</div>' +
          '<div class="dn-body">' + esc(n.body || '').replace(/\\n/g, '<br>') + '</div>' +
          repliesHtml +
          '<div class="dn-actions">' + actions + '</div>' +
        '</div>'
      );
    }

    function _renderDevNoteReply(r) {
      const author = esc(r.author_name || r.author_email || 'Unknown');
      const time = r.created_at
        ? '<time class="ts-relative" datetime="' + esc(r.created_at) + '"></time>'
        : '';
      return (
        '<div class="dn-reply">' +
          '<div class="dn-reply-meta">' +
            '<span class="dn-reply-author">' + author + '</span>' +
            time +
          '</div>' +
          '<div class="dn-reply-body">' + esc(r.body || '').replace(/\\n/g, '<br>') + '</div>' +
        '</div>'
      );
    }

    async function setDevNoteStatus(noteId, newStatus) {
      try {
        const r = await fetch('/api/dev_notes/' + noteId + '/status', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({status: newStatus}),
        });
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        // Easiest correct path: refetch the whole list (counts +
        // ordering may have shifted).
        await loadDevNotes();
      } catch (e) {
        alert('Could not update status: ' + e.message);
      }
    }

    function openDevNoteReply(noteId, btn) {
      const card = document.getElementById('devNote-' + noteId);
      if (!card) return;
      const existing = card.querySelector('.dn-reply-editor');
      if (existing) { existing.remove(); return; }
      const editor = document.createElement('div');
      editor.className = 'dn-reply-editor';
      editor.style.marginTop = '10px';
      editor.innerHTML =
        '<textarea placeholder="Reply to this dev note…"></textarea>' +
        '<div class="dn-reply-editor-actions">' +
          '<button class="btn btn-sm btn-primary">Post reply</button>' +
          '<button class="btn btn-sm btn-subtle">Cancel</button>' +
        '</div>';
      card.querySelector('.dn-actions').insertAdjacentElement('beforebegin', editor);
      const ta = editor.querySelector('textarea');
      ta.focus();
      const [saveBtn, cancelBtn] = editor.querySelectorAll('button');
      cancelBtn.onclick = () => editor.remove();
      saveBtn.onclick = async () => {
        if (!ta.value.trim()) { ta.focus(); return; }
        saveBtn.disabled = true;
        try {
          const r = await fetch('/api/dev_notes/' + noteId + '/reply', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({body: ta.value}),
          });
          const data = await r.json();
          if (data.error) throw new Error(data.error);
          editor.remove();
          // Refresh the full list — keeps replies in chronological
          // order without needing partial DOM updates.
          await loadDevNotes();
        } catch (e) {
          alert('Could not post reply: ' + e.message);
          saveBtn.disabled = false;
        }
      };
    }

    // Home page banners: "your check is still running" / "your check
    // completed" — both driven by /api/my_active_check. Keeps a user who
    // disconnected mid-check from thinking their work was lost.
    //
    // Dismissal for the completed banner uses localStorage so it doesn't
    // re-nag after the user has seen it once. Running banner is not
    // dismissible — it's load-bearing info.
    async function fetchActiveChecks() {
      try {
        const r = await fetch('/api/my_active_check');
        if (!r.ok) return;
        const data = await r.json();
        _applyActiveCheckBanners(data);
      } catch (e) { /* silently ignore */ }
    }

    function _applyActiveCheckBanners(data) {
      const running = data && data.running;
      const rb = document.getElementById('runningCheckBanner');
      if (running && rb) {
        rb.href = '/report/' + running.db_report_id;
        const detail = document.getElementById('runningCheckDetail');
        if (detail) {
          const name = running.project_name || ('Project ' + running.project_id);
          detail.textContent = name + ' — click to see current progress';
        }
        rb.style.display = 'flex';
      } else if (rb) {
        rb.style.display = 'none';
      }

      const completed = data && data.recently_completed;
      const cb = document.getElementById('completedCheckBanner');
      if (completed && cb) {
        const dismissKey = 'dismissed_completed_' + completed.db_report_id;
        if (localStorage.getItem(dismissKey)) {
          cb.style.display = 'none';
          return;
        }
        const link = document.getElementById('completedCheckLink');
        if (link) link.href = '/report/' + completed.db_report_id;
        const detail = document.getElementById('completedCheckDetail');
        if (detail) {
          const name = completed.project_name || ('Project ' + completed.project_id);
          const cancelled = completed.status === 'cancelled';
          const passed = completed.total_passed || 0;
          const total = completed.total_required || 0;
          const result = cancelled
            ? `${name} — cancelled with ${passed}/${total} completed`
            : `${name} — ${passed}/${total} passed`;
          detail.textContent = result;
        }
        cb.dataset.reportId = completed.db_report_id;
        cb.style.display = 'flex';
      } else if (cb) {
        cb.style.display = 'none';
      }
    }

    function dismissCompletedCheckBanner(ev) {
      ev.preventDefault();
      ev.stopPropagation();
      const cb = document.getElementById('completedCheckBanner');
      if (!cb) return;
      const id = cb.dataset.reportId;
      if (id) localStorage.setItem('dismissed_completed_' + id, '1');
      cb.style.display = 'none';
    }

    // Refresh Anthropic platform status every 60s so the banner appears/
    // disappears in near real-time without a page reload. Errors are
    // swallowed — the banner just won't update. Poll interval matches
    // the backend's own status fetch cadence.
    async function refreshPlatformStatus() {
      try {
        const r = await fetch('/api/platform_status');
        if (!r.ok) return;
        const s = await r.json();
        _applyPlatformStatus(s);
      } catch (e) { /* silently ignore */ }
    }
    setInterval(refreshPlatformStatus, 60000);

    // Map Statuspage indicators to banner styles. "none" → hide.
    // "maintenance" shown informationally in blue rather than amber/red.
    const _PLATFORM_STATUS_STYLE = {
      minor:       {bg: '#f59e0b', fg: '#1a1a2e', label: 'degraded'},
      major:       {bg: '#dc2626', fg: '#ffffff', label: 'experiencing a partial outage'},
      critical:    {bg: '#991b1b', fg: '#ffffff', label: 'experiencing a major outage'},
      maintenance: {bg: '#3b82f6', fg: '#ffffff', label: 'under maintenance'},
    };

    function _applyPlatformStatus(s) {
      const banner = document.getElementById('platformStatusBanner');
      if (!banner) return;
      const indicator = s && s.indicator;
      const style = _PLATFORM_STATUS_STYLE[indicator];
      // "none" (all good), "unknown" (poller failing / not yet run), or
      // anything unmapped → hide the banner rather than cry wolf.
      if (!style) {
        banner.style.display = 'none';
        return;
      }
      banner.style.background = style.bg;
      banner.style.color = style.fg;
      document.getElementById('platformStatusTitle').textContent =
        'Anthropic API: ' + style.label;
      // Prefer Anthropic's own description when they provide a useful
      // one (e.g. "Partial Outage — Claude API Degraded Performance");
      // otherwise keep our fallback about slower/failed checks.
      const detail = document.getElementById('platformStatusDetail');
      if (s.description && s.description.toLowerCase() !== 'all systems operational') {
        detail.textContent = ' — ' + s.description + '. Compliance checks may be slower or fail intermittently.';
      } else {
        detail.textContent = ' — compliance checks may be slower or fail intermittently.';
      }
      banner.style.display = 'flex';
    }

    function _applyImpersonationBanner(me) {
      const banner = document.getElementById('impersonationBanner');
      if (!banner) return;
      if (me && me.is_impersonating) {
        document.getElementById('impersonationTarget').textContent =
          (me.full_name || me.email || 'user #' + me.user_id) + ' (' + me.role + ')';
        document.getElementById('impersonationInitiator').textContent =
          'as ' + (me.real_full_name || me.real_email || 'superadmin');
        banner.style.display = 'flex';
      } else {
        banner.style.display = 'none';
      }
    }

    async function startImpersonate(userId, userName) {
      if (!confirm("Impersonate " + (userName || "this user") + "? You'll see the app from their perspective until you stop.")) return;
      try {
        const r = await fetch('/api/admin/impersonate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({user_id: userId}),
        });
        const data = await r.json();
        if (!r.ok) { alert(data.error || 'Could not impersonate'); return; }
        // Full reload so the new session cookie + role-gated UI apply cleanly
        window.location.href = '/';
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function stopImpersonate() {
      try {
        const r = await fetch('/api/admin/stop-impersonate', {method: 'POST'});
        if (!r.ok) { alert('Could not stop impersonation'); return; }
        window.location.href = '/';
      } catch (e) { alert('Error: ' + e.message); }
    }

    // ── Cost dashboard ──
    function _fmtUSD(n) {
      if (n == null) return '—';
      if (n >= 1) return '$' + n.toFixed(2);
      if (n >= 0.01) return '$' + n.toFixed(3);
      return '$' + n.toFixed(4);
    }
    // ── Timestamp localization ──
    // Renders a UTC timestamp in the viewer's local tz, with relative
    // ("5 min ago") for recent and absolute ("Apr 17, 2:15 PM") for older.
    // Browser tz detected automatically via Intl. _fmtDate kept as a thin
    // alias for backward compat — same behavior.
    // (This block is duplicated in tools/generate_report_html.py — keep
    // them in sync. Worth extracting to a shared static asset eventually.)
    function formatTimestamp(input, opts) {
      if (!input) return '';
      opts = opts || {};
      const d = _toDate(input);
      if (!d || isNaN(d.getTime())) return String(input);
      const ageMs = Date.now() - d.getTime();
      const sec = Math.round(ageMs / 1000);
      const min = Math.round(sec / 60);
      const hr = Math.round(min / 60);
      const day = Math.round(hr / 24);
      if (opts.absolute) return _absoluteString(d, ageMs);
      if (sec < 30 && sec > -30) return 'just now';
      if (Math.abs(min) < 60) return min + ' min ago';
      if (Math.abs(hr) < 24) return hr + ' hr ago';
      if (Math.abs(day) < 7) return day + (Math.abs(day) === 1 ? ' day ago' : ' days ago');
      return _absoluteString(d, ageMs);
    }
    function formatTimestampAbsolute(input) {
      return formatTimestamp(input, {absolute: true});
    }
    function _absoluteString(d, ageMs) {
      const opts = {month:'short', day:'numeric', hour:'numeric', minute:'2-digit'};
      if (ageMs > 365 * 24 * 60 * 60 * 1000) opts.year = 'numeric';
      return d.toLocaleString('en-US', opts);
    }
    function _toDate(input) {
      if (input == null) return null;
      if (input instanceof Date) return input;
      if (typeof input === 'number') {
        return new Date(input < 1e11 ? input * 1000 : input);
      }
      return new Date(input);
    }
    function localizeTimestamps(root) {
      root = root || document;
      root.querySelectorAll('time.ts-relative').forEach(function(el) {
        const iso = el.getAttribute('datetime');
        if (!iso) return;
        el.textContent = formatTimestamp(iso);
        el.title = formatTimestampAbsolute(iso);
      });
    }
    document.addEventListener('DOMContentLoaded', function() { localizeTimestamps(); });
    setInterval(function() { localizeTimestamps(); }, 60000);

    function _fmtDate(iso) {
      if (!iso) return '—';
      return formatTimestamp(iso);
    }
    function _fmtDay(iso) {
      if (!iso) return '—';
      const d = _toDate(iso);
      if (!d || isNaN(d.getTime())) return '—';
      return d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
    }

    let _costFilterOptionsLoaded = false;
    async function loadCostFilterOptions() {
      if (_costFilterOptionsLoaded) return;
      try {
        const r = await fetch('/api/admin/cost/filter-options');
        if (!r.ok) return;
        const data = await r.json();
        const orgSel = document.getElementById('costOrgFilter');
        const userSel = document.getElementById('costUserFilter');
        // Preserve the "All" option and append DB rows
        orgSel.innerHTML = '<option value="">All organizations</option>' +
          (data.orgs || []).map(o => '<option value="' + o.id + '">' + esc(o.name) + '</option>').join('');
        userSel.innerHTML = '<option value="">All users</option>' +
          (data.users || []).map(u => {
            const label = u.full_name || u.email || ('user ' + u.id);
            return '<option value="' + u.id + '">' + esc(label) + '</option>';
          }).join('');
        _costFilterOptionsLoaded = true;
      } catch (e) { /* non-fatal — dropdowns just stay empty */ }
    }

    function _costFilterQuery() {
      const org = document.getElementById('costOrgFilter').value;
      const user = document.getElementById('costUserFilter').value;
      const from = document.getElementById('costDateFrom').value;
      const to = document.getElementById('costDateTo').value;
      const params = new URLSearchParams();
      if (org) params.set('org_id', org);
      if (user) params.set('user_id', user);
      if (from) params.set('from', from);
      if (to) params.set('to', to);
      const qs = params.toString();
      return qs ? ('?' + qs) : '';
    }

    function switchAnalyticsTab(tab) {
      // Costs tab is superadmin-only — redirect admins to Performance
      if (tab === 'costs' && _me && _me.role !== 'superadmin') {
        tab = 'performance';
      }
      ['costs', 'performance', 'activity'].forEach(t => {
        const panelId = t === 'costs' ? 'analyticsCosts' : t === 'performance' ? 'analyticsPerf' : 'analyticsActivity';
        const btnId = 'analyticsTab' + t.charAt(0).toUpperCase() + t.slice(1);
        const panel = document.getElementById(panelId);
        const btn = document.getElementById(btnId);
        if (panel) panel.style.display = t === tab ? '' : 'none';
        if (btn) btn.classList.toggle('active', t === tab);
      });
      if (tab === 'performance') loadPerformance();
      if (tab === 'activity') loadGlobalAuditLog();
    }

    async function loadGlobalAuditLog() {
      const body = document.getElementById('analyticsActivityBody');
      if (!body || body.dataset.loaded) return;
      try {
        const r = await fetch('/api/admin/audit_log');
        if (!r.ok) throw new Error('Request failed');
        const data = await r.json();
        const entries = data.entries || [];
        if (!entries.length) {
          body.innerHTML = '<div style="color:var(--text-muted);font-size:var(--text-sm);">No activity recorded yet — actions will appear here as users interact with Solclear.</div>';
          body.dataset.loaded = '1';
          return;
        }
        const _ACTION_LABELS = {
          login: 'Logged in', report_run: 'Ran check', report_cancel: 'Cancelled check',
          requirement_recheck: 'Re-checked requirement', note_add: 'Added note',
          dev_note_triage: 'Triaged dev note', org_settings_change: 'Updated org settings',
          user_invite: 'Invited user', user_role_change: 'Changed user role',
        };
        body.innerHTML = '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
          '<thead><tr>' +
          '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">When</th>' +
          '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">User</th>' +
          '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Org</th>' +
          '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Action</th>' +
          '</tr></thead><tbody>' +
          entries.map(e => {
            const label = _ACTION_LABELS[e.action] || e.action;
            const actor = esc(e.actor_name || e.actor_email || 'System');
            const org = esc(e.org_name || '—');
            const time = '<time class="ts-relative" datetime="' + esc(e.created_at || '') + '">' + esc(e.created_at || '') + '</time>';
            return '<tr style="border-top:1px solid var(--border-light);">' +
              '<td style="padding:6px;color:var(--text-muted);white-space:nowrap;">' + time + '</td>' +
              '<td style="padding:6px;font-weight:500;">' + actor + '</td>' +
              '<td style="padding:6px;color:var(--text-muted);">' + org + '</td>' +
              '<td style="padding:6px;">' + esc(label) + '</td>' +
              '</tr>';
          }).join('') + '</tbody></table></div>';
        if (typeof localizeTimestamps === 'function') localizeTimestamps(body);
        body.dataset.loaded = '1';
      } catch (e) {
        body.innerHTML = errorAlert('Could not load activity: ' + e.message);
      }
    }

    async function loadPerformance() {
      const body = document.getElementById('perfBody');
      if (!body) return;
      body.innerHTML = spinnerHtml('Loading performance data...');
      try {
        // Reuse the cost endpoint — it returns requirement_timing in the same payload
        const r = await fetch('/api/admin/cost/summary');
        if (!r.ok) {
          const errData = await r.json().catch(() => ({}));
          throw new Error('HTTP ' + r.status + (errData.error ? ': ' + errData.error : ''));
        }
        const data = await r.json();
        body.innerHTML = renderReqTiming(data.requirement_timing || []);
      } catch (e) {
        body.innerHTML = errorAlert('Could not load performance data: ' + e.message);
      }
    }

    function clearCostFilters() {
      document.getElementById('costOrgFilter').value = '';
      document.getElementById('costUserFilter').value = '';
      document.getElementById('costDateFrom').value = '';
      document.getElementById('costDateTo').value = '';
      loadCosts();
    }

    async function loadCosts() {
      const summary = document.getElementById('costSummary');
      const body = document.getElementById('costBody');
      summary.innerHTML = spinnerHtml('Loading cost data...');
      body.innerHTML = '';
      await loadCostFilterOptions();
      try {
        const r = await fetch('/api/admin/cost/summary' + _costFilterQuery());
        if (r.status === 403) {
          summary.innerHTML = errorAlert('Superadmin access required.');
          return;
        }
        if (!r.ok) throw new Error('Request failed');
        const data = await r.json();
        summary.innerHTML = renderCostSummary(data.totals);
        body.innerHTML =
          renderCostSection('Spend by purpose', renderByPurpose(data.by_purpose, data.totals)) +
          renderCostSection('Most expensive reports', renderTopReports(data.top_reports)) +
          renderCostSection('Most expensive requirements', renderTopRequirements(data.top_requirements)) +
          renderCostSection('Requirement processing time', renderReqTiming(data.requirement_timing)) +
          renderCostSection('Spend by day (last 30)', renderDailyTrend(data.daily_last_30)) +
          renderCostSection('Recent API calls', renderRecentCalls(data.recent_calls));
      } catch (e) {
        summary.innerHTML = errorAlert('Could not load cost data: ' + e.message);
      }
    }

    function renderCostSummary(t) {
      const cards = [
        {label: 'All time', value: _fmtUSD(t && t.all_time)},
        {label: 'This month', value: _fmtUSD(t && t.this_month)},
        {label: 'Today', value: _fmtUSD(t && t.today)},
        {label: 'API calls (all time)', value: (t && t.call_count != null) ? t.call_count.toLocaleString() : '—'},
      ];
      return '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;">' +
        cards.map(c =>
          '<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:12px 14px;box-shadow:var(--shadow-sm);">' +
          '<div style="font-size:var(--text-xs);color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;font-weight:600;">' + c.label + '</div>' +
          '<div style="font-size:var(--text-xl);font-weight:700;color:var(--text);margin-top:4px;">' + c.value + '</div>' +
          '</div>'
        ).join('') + '</div>';
    }

    function renderCostSection(title, inner) {
      return '<div style="margin-top:20px;">' +
        '<div style="font-size:var(--text-xs);text-transform:uppercase;letter-spacing:0.1em;color:var(--text-muted);font-weight:600;padding:8px 0;border-bottom:2px solid var(--border);margin-bottom:10px;">' + esc(title) + '</div>' +
        inner + '</div>';
    }

    // Friendly labels + colors per purpose. Keep in sync with the
    // `purpose` values written in tools/compliance_check.py and
    // live_server.py recheck endpoint.
    const _PURPOSE_META = {
      vision:    {label: 'Full check (Sonnet)',    color: 'var(--accent)'},
      prefilter: {label: 'Pre-filter (Haiku)',     color: 'var(--success)'},
      recheck:   {label: 'Single-item re-check',   color: 'var(--warning)'},
      unknown:   {label: 'Unknown / legacy',       color: 'var(--text-muted)'},
    };

    function renderByPurpose(rows, totals) {
      if (!rows || !rows.length) {
        return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No cost data recorded yet.</div>';
      }
      // Caption clarifies that "Pre-filter" is broken out separately
      // regardless of whether it ran inside a full vision pass or a
      // single-item recheck. Without this it's easy to read "Single-item
      // re-check" as the full cost of rechecks when in reality a recheck
      // on a heavy requirement also incurs prefilter spend.
      const caption = '<div style="color:var(--text-muted);font-size:var(--text-xs);margin-bottom:8px;">' +
        'Pre-filter spend is shown separately and includes calls triggered by both full vision runs and single-item rechecks.' +
        '</div>';
      const grandTotal = rows.reduce((s, r) => s + (r.total_cost || 0), 0) || 0.0001;
      // Stacked bar at top so the proportion is visible at a glance, then
      // a small table with the underlying numbers.
      const bar = '<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--bg-subtle);margin-bottom:10px;">' +
        rows.map(r => {
          const meta = _PURPOSE_META[r.purpose] || _PURPOSE_META.unknown;
          const pct = ((r.total_cost || 0) / grandTotal) * 100;
          return '<div title="' + esc(meta.label) + ': ' + _fmtUSD(r.total_cost) + '" ' +
            'style="width:' + pct.toFixed(2) + '%;background:' + meta.color + ';"></div>';
        }).join('') + '</div>';
      const table = '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
        '<thead><tr><th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Purpose</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Total</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">% of spend</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Calls</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Avg</th></tr></thead><tbody>' +
        rows.map(r => {
          const meta = _PURPOSE_META[r.purpose] || _PURPOSE_META.unknown;
          const pct = ((r.total_cost || 0) / grandTotal) * 100;
          return '<tr style="border-top:1px solid var(--border-light);">' +
            '<td style="padding:6px;font-weight:600;">' +
              '<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + meta.color + ';margin-right:8px;vertical-align:middle;"></span>' +
              esc(meta.label) +
            '</td>' +
            '<td style="padding:6px;text-align:right;font-weight:600;">' + _fmtUSD(r.total_cost) + '</td>' +
            '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + pct.toFixed(1) + '%</td>' +
            '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + r.call_count + '</td>' +
            '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + _fmtUSD(r.avg_cost) + '</td>' +
            '</tr>';
        }).join('') + '</tbody></table></div>';
      return caption + bar + table;
    }

    function renderTopReports(rows) {
      if (!rows || !rows.length) return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No cost data recorded yet.</div>';
      return '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
        '<thead><tr><th style="text-align:left;padding:8px 6px;color:var(--text-muted);font-weight:600;">Project</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Cost</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Calls</th>' +
        '<th style="text-align:left;padding:8px 6px;color:var(--text-muted);font-weight:600;">Completed</th></tr></thead><tbody>' +
        rows.map(r =>
          '<tr style="border-top:1px solid var(--border-light);">' +
          '<td style="padding:8px 6px;"><a href="/report/' + r.report_id + '" style="color:var(--accent);text-decoration:none;">' + esc(r.project_name) + '</a>' +
          (r.is_test ? ' <span class="badge badge-info" style="margin-left:4px;">TEST</span>' : '') + '</td>' +
          '<td style="padding:8px 6px;text-align:right;font-weight:600;">' + _fmtUSD(r.cost_usd) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);">' + r.call_count + '</td>' +
          '<td style="padding:8px 6px;color:var(--text-muted);">' + _fmtDate(r.completed_at) + '</td>' +
          '</tr>'
        ).join('') + '</tbody></table></div>';
    }

    function _fmtMs(ms) {
      if (!ms) return '—';
      if (ms < 1000) return ms + 'ms';
      return (ms / 1000).toFixed(1) + 's';
    }

    function renderReqTiming(rows) {
      if (!rows || !rows.length) return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No timing data yet — run a check to populate.</div>';
      return '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
        '<thead><tr>' +
        '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Req</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Avg total</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Avg API</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Avg download</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Min</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Max</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Runs</th>' +
        '</tr></thead><tbody>' +
        rows.map(r => {
          const totalMs = r.avg_total_ms || 0;
          const apiMs = r.avg_api_ms || 0;
          const downloadMs = Math.max(0, totalMs - apiMs);
          const colour = totalMs > 30000 ? 'var(--danger)' : totalMs > 10000 ? 'var(--warning)' : 'var(--success)';
          const code = esc(r.requirement_code);
          return (
            '<tr style="border-top:1px solid var(--border-light);cursor:pointer;" data-code="' + code + '" onclick="toggleReqTimingDetail(this.dataset.code, this)">' +
              '<td style="padding:6px;font-weight:600;">' + code + ' <span style="font-size:10px;opacity:0.5;">&#9660;</span></td>' +
              '<td style="padding:6px;text-align:right;font-weight:700;color:' + colour + ';">' + _fmtMs(totalMs) + '</td>' +
              '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + _fmtMs(apiMs) + '</td>' +
              '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + _fmtMs(downloadMs) + '</td>' +
              '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + _fmtMs(r.min_total_ms) + '</td>' +
              '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + _fmtMs(r.max_total_ms) + '</td>' +
              '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + (r.run_count || 0) + '</td>' +
            '</tr>' +
            '<tr id="reqTimingDetail-' + code + '" style="display:none;">' +
              '<td colspan="7" style="padding:0;">' +
                '<div id="reqTimingDetailBody-' + code + '" style="padding:8px 12px;background:var(--bg-subtle);font-size:var(--text-xs);">Loading…</div>' +
              '</td>' +
            '</tr>'
          );
        }).join('') + '</tbody></table></div>';
    }

    async function toggleReqTimingDetail(code, clickedRow) {
      const detailRow = document.getElementById('reqTimingDetail-' + code);
      const body = document.getElementById('reqTimingDetailBody-' + code);
      if (!detailRow || !body) return;
      const open = detailRow.style.display !== 'none';
      detailRow.style.display = open ? 'none' : '';
      const arrow = clickedRow.querySelector('span');
      if (arrow) arrow.textContent = open ? '▼' : '▲';
      if (open || body.dataset.loaded) return;
      // Lazy-load per-run breakdown
      try {
        const r = await fetch('/api/admin/req_timing/' + encodeURIComponent(code));
        if (!r.ok) throw new Error('Request failed');
        const data = await r.json();
        const runs = data.runs || [];
        if (!runs.length) { body.innerHTML = 'No runs recorded yet.'; body.dataset.loaded = '1'; return; }
        body.innerHTML = '<table style="width:100%;border-collapse:collapse;">' +
          '<thead><tr>' +
          '<th style="text-align:left;padding:4px 6px;color:var(--text-muted);">Project</th>' +
          '<th style="text-align:right;padding:4px 6px;color:var(--text-muted);">Total</th>' +
          '<th style="text-align:right;padding:4px 6px;color:var(--text-muted);">API</th>' +
          '<th style="text-align:right;padding:4px 6px;color:var(--text-muted);">Download</th>' +
          '<th style="text-align:left;padding:4px 6px;color:var(--text-muted);">Status</th>' +
          '<th style="text-align:left;padding:4px 6px;color:var(--text-muted);">Date</th>' +
          '</tr></thead><tbody>' +
          runs.map(run => {
            const tot = run.total_duration_ms || 0;
            const api = run.api_ms || 0;
            const dl = Math.max(0, tot - api);
            const colour = tot > 30000 ? 'var(--danger)' : tot > 10000 ? 'var(--warning)' : 'var(--success)';
            return '<tr style="border-top:1px solid var(--border-light);">' +
              '<td style="padding:4px 6px;"><a href="/report/' + run.report_id + '" style="color:var(--accent);">' + esc(run.project_name || ('Report ' + run.report_id)) + '</a></td>' +
              '<td style="padding:4px 6px;text-align:right;font-weight:600;color:' + colour + ';">' + _fmtMs(tot) + '</td>' +
              '<td style="padding:4px 6px;text-align:right;color:var(--text-muted);">' + _fmtMs(api) + '</td>' +
              '<td style="padding:4px 6px;text-align:right;color:var(--text-muted);">' + _fmtMs(dl) + '</td>' +
              '<td style="padding:4px 6px;">' + esc(run.status || '') + '</td>' +
              '<td style="padding:4px 6px;color:var(--text-muted);"><time class="ts-relative" datetime="' + esc(run.created_at || '') + '">' + esc(run.created_at || '') + '</time></td>' +
              '</tr>';
          }).join('') +
          '</tbody></table>';
        if (typeof localizeTimestamps === 'function') localizeTimestamps(body);
        body.dataset.loaded = '1';
      } catch (e) {
        body.innerHTML = 'Error: ' + esc(e.message);
      }
    }

    function renderTopRequirements(rows) {
      if (!rows || !rows.length) return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No cost data recorded yet.</div>';
      return '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
        '<thead><tr><th style="text-align:left;padding:8px 6px;color:var(--text-muted);font-weight:600;">Requirement</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Total</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Avg</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Max</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Calls</th></tr></thead><tbody>' +
        rows.map(r =>
          '<tr style="border-top:1px solid var(--border-light);">' +
          '<td style="padding:8px 6px;font-weight:600;">' + esc(r.requirement_code) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;font-weight:600;">' + _fmtUSD(r.total_cost) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);">' + _fmtUSD(r.avg_cost) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);">' + _fmtUSD(r.max_cost) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);">' + r.call_count + '</td>' +
          '</tr>'
        ).join('') + '</tbody></table></div>';
    }

    function renderDailyTrend(rows) {
      if (!rows || !rows.length) return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No calls in the last 30 days.</div>';
      // Compute a max for bar scaling
      const max = rows.reduce((m, r) => Math.max(m, r.cost_usd || 0), 0.0001);
      return '<div style="display:flex;flex-direction:column;gap:4px;">' +
        rows.map(r => {
          const pct = (r.cost_usd / max) * 100;
          return '<div style="display:flex;align-items:center;gap:10px;font-size:var(--text-xs);">' +
            '<div style="width:60px;color:var(--text-muted);flex-shrink:0;">' + _fmtDay(r.day) + '</div>' +
            '<div style="flex:1;height:8px;background:var(--bg-subtle);border-radius:4px;overflow:hidden;">' +
              '<div style="height:100%;background:var(--accent);width:' + pct.toFixed(1) + '%;transition:width 0.3s;"></div>' +
            '</div>' +
            '<div style="width:60px;text-align:right;font-weight:600;flex-shrink:0;">' + _fmtUSD(r.cost_usd) + '</div>' +
            '<div style="width:40px;text-align:right;color:var(--text-muted);flex-shrink:0;">' + r.call_count + '</div>' +
            '</div>';
        }).join('') + '</div>';
    }

    function renderRecentCalls(rows) {
      if (!rows || !rows.length) return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No calls yet.</div>';
      return '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
        '<thead><tr><th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">When</th>' +
        '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Project</th>' +
        '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Req</th>' +
        '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Purpose</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Tokens</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Cost</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">ms</th></tr></thead><tbody>' +
        rows.map(c =>
          '<tr style="border-top:1px solid var(--border-light);">' +
          '<td style="padding:6px;color:var(--text-muted);white-space:nowrap;">' + _fmtDate(c.called_at) + '</td>' +
          '<td style="padding:6px;">' + esc(c.project_name || '—') + '</td>' +
          '<td style="padding:6px;font-weight:600;">' + esc(c.requirement_code || '—') + '</td>' +
          '<td style="padding:6px;color:var(--text-muted);">' + esc(c.purpose || '—') + '</td>' +
          '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + (c.input_tokens || 0) + ' / ' + (c.output_tokens || 0) + '</td>' +
          '<td style="padding:6px;text-align:right;font-weight:600;">' + _fmtUSD(c.cost_usd) + '</td>' +
          '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + (c.duration_ms || '—') + '</td>' +
          '</tr>'
        ).join('') + '</tbody></table></div>';
    }
  
