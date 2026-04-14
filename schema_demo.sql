-- Solclear Schema Demo — Dummy Data
-- Run after schema.sql to populate sample data

-- ── Organizations ────────────────────────────────────────────────────────────

INSERT INTO organizations (id, name, companycam_api_key) VALUES
  (1, 'Independent Solar', 'cc_key_independent_solar_xxx'),
  (2, 'Sunrise Power Co', 'cc_key_sunrise_power_xxx');

-- ── Users ────────────────────────────────────────────────────────────────────

INSERT INTO users (id, organization_id, email, name, role) VALUES
  (1,  NULL, 'brandon@solclear.io',      'Brandon Pantano',  'superadmin'),
  (2,  1,    'dylan@independentsolar.com','Dylan Mitchell',   'admin'),
  (3,  1,    'micah@independentsolar.com','Micah Izquierdo',  'reviewer'),
  (4,  1,    'carlos@independentsolar.com','Carlos Reyes',    'crew'),
  (5,  1,    'jose@independentsolar.com', 'Jose Ramirez',     'crew'),
  (6,  2,    'sarah@sunrisepower.com',    'Sarah Chen',       'admin'),
  (7,  2,    'mike@sunrisepower.com',     'Mike Thompson',    'crew');

-- ── Projects ─────────────────────────────────────────────────────────────────

INSERT INTO projects (id, organization_id, companycam_id, name, address, city, state) VALUES
  (1, 1, '99090405', 'IND-5453 Reynaldo Melgoza',   '3656 W Palmaire Ave',  'Phoenix',    'Arizona'),
  (2, 1, '98404086', 'IND-5210 Maria Santos',        '1422 E Baseline Rd',   'Tempe',      'Arizona'),
  (3, 1, '99494794', 'IND-5501 James Wilson',        '8801 N 12th St',       'Phoenix',    'Arizona'),
  (4, 2, '50001001', 'SUN-1001 David Park',          '245 Maple Ave',        'San Jose',   'California'),
  (5, 2, '50001002', 'SUN-1002 Lisa Nguyen',         '1800 Mission St',      'San Francisco','California');

-- ── Checklists ───────────────────────────────────────────────────────────────

INSERT INTO checklists (id, project_id, companycam_checklist_id, companycam_template_id, name, manufacturer, has_battery, is_backup_battery, is_incentive_state, portal_access_granted) VALUES
  (1, 1, '8937299', '95194',  'Install - Battery',       'Tesla',     TRUE,  FALSE, FALSE, TRUE),
  (2, 2, '8850001', '58508',  'Install',                 'SolarEdge', FALSE, FALSE, FALSE, TRUE),
  (3, 3, '8981814', '184408', 'LightReach : PV Only',    'Enphase',   FALSE, FALSE, FALSE, FALSE),
  (4, 4, '7001001', '95194',  'Install - Battery',       'Tesla',     TRUE,  TRUE,  TRUE,  TRUE),
  (5, 5, '7001002', '184408', 'LightReach : PV Only',    'SolarEdge', FALSE, FALSE, TRUE,  TRUE);

-- ── Requirements (sample — just a few for demo) ─────────────────────────────

INSERT INTO requirements (id, code, version, section, title, condition_json, task_titles, keywords, validation_prompt, is_optional) VALUES
  (1,  'PS4', 1, 'Project Site', 'Module Manufacturer Label',
       '{"always": true}', '{"Manufacturer Labels"}', '{"manufacturer labels","module label"}',
       'This photo should show the manufacturer label from a solar module/panel.', FALSE),
  (2,  'PS5', 1, 'Project Site', 'Module Serial Number',
       '{"always": true}', '{"Manufacturer Labels"}', '{"module serial","serial number"}',
       'This photo should show a serial number from a solar module installed on site.', FALSE),
  (3,  'R3',  1, 'Roof', 'Complete Array with Rail Trimmed',
       '{"always": true}', '{"Array Photos"}', '{"array photos","complete array"}',
       'This photo should show a complete solar array with all modules visible and rail trimmed.', FALSE),
  (4,  'R4',  1, 'Roof', 'Under-Array Wire Management',
       '{"always": true}', '{"Wire Management / Under Array"}', '{"wire management"}',
       'This photo should show wire management under the solar array.', FALSE),
  (5,  'R5',  1, 'Roof', 'Tilt Measurement',
       '{"always": true}', '{"Tilt Measurement"}', '{"tilt measurement"}',
       'This photo should show a tilt/pitch measurement taken on the solar module itself.', FALSE),
  (6,  'E2',  1, 'Electrical', 'Main Breaker Rating',
       '{"always": true}', '{"Main Breaker"}', '{"main breaker"}',
       'This photo should show the main breaker with its amperage rating clearly visible.', FALSE),
  (7,  'SC1', 1, 'Commissioning', 'Tesla Commissioning Screenshots',
       '{"manufacturer": "Tesla"}', '{"Monitoring App Screenshots"}', '{"commissioning"}',
       'This screenshot should show Tesla system commissioning.', FALSE),
  (8,  'S2',  1, 'Storage', 'Comms Cable & Drain Wire',
       '{"has_battery": true}', '{"Comms Cable & Drain Wire"}', '{"comms cable"}',
       'This photo should show battery comms cable terminations.', FALSE);

-- ── Reports ──────────────────────────────────────────────────────────────────

-- Report 1: IND-5453 Melgoza (Tesla + Battery) — mostly failing
INSERT INTO reports (id, project_id, checklist_id, run_by, manufacturer, has_battery, is_backup_battery, is_incentive_state, portal_access_granted, total_required, total_passed, total_failed, total_missing, status, completed_at) VALUES
  (1, 1, 1, 4, 'Tesla', TRUE, FALSE, FALSE, TRUE, 19, 6, 11, 2, 'complete', NOW() - INTERVAL '2 days');

-- Report 2: IND-5210 Santos (SolarEdge, PV only) — mostly passing
INSERT INTO reports (id, project_id, checklist_id, run_by, manufacturer, has_battery, is_backup_battery, is_incentive_state, portal_access_granted, total_required, total_passed, total_failed, total_missing, status, completed_at) VALUES
  (2, 2, 2, 5, 'SolarEdge', FALSE, FALSE, FALSE, TRUE, 14, 12, 2, 0, 'complete', NOW() - INTERVAL '1 day');

-- Report 3: IND-5501 Wilson (Enphase, PV only) — all passing
INSERT INTO reports (id, project_id, checklist_id, run_by, manufacturer, has_battery, is_backup_battery, is_incentive_state, portal_access_granted, total_required, total_passed, total_failed, total_missing, status, completed_at) VALUES
  (3, 3, 3, 4, 'Enphase', FALSE, FALSE, FALSE, FALSE, 15, 15, 0, 0, 'complete', NOW() - INTERVAL '12 hours');

-- Report 4: SUN-1001 Park (Tesla + Backup Battery, CA incentive) — some failures
INSERT INTO reports (id, project_id, checklist_id, run_by, manufacturer, has_battery, is_backup_battery, is_incentive_state, portal_access_granted, total_required, total_passed, total_failed, total_missing, status, completed_at) VALUES
  (4, 4, 4, 7, 'Tesla', TRUE, TRUE, TRUE, TRUE, 21, 17, 3, 1, 'complete', NOW() - INTERVAL '6 hours');

-- Report 5: Rerun of Report 1 after fixes — improved
INSERT INTO reports (id, project_id, checklist_id, run_by, manufacturer, has_battery, is_backup_battery, is_incentive_state, portal_access_granted, total_required, total_passed, total_failed, total_missing, status, completed_at) VALUES
  (5, 1, 1, 4, 'Tesla', TRUE, FALSE, FALSE, TRUE, 19, 14, 4, 1, 'complete', NOW() - INTERVAL '1 day');

-- ── Requirement Results ──────────────────────────────────────────────────────

-- Report 1 results (IND-5453, first run — 6 pass, 11 fail, 2 missing)
INSERT INTO requirement_results (report_id, requirement_id, status, reason, candidates) VALUES
  (1, 1, 'PASS',    'Manufacturer label clearly visible — LONGi LR5-54HPB-405M with full specs readable.', 8),
  (1, 2, 'FAIL',    'Serial number partially obscured by glare, not fully readable.', 8),
  (1, 3, 'FAIL',    'Rail extends past last module on right side of array.', 9),
  (1, 4, 'FAIL',    'Wires in direct contact with roof surface and gravel.', 7),
  (1, 5, 'PASS',    'Tilt measurement clearly legible at 30 degrees on Empire inclinometer, taken on module.', 4),
  (1, 6, 'FAIL',    'Main breaker amperage rating not clearly readable from this angle.', 6),
  (1, 7, 'FAIL',    'Wrong screenshot — shows customer registration, not commissioning dashboard.', 18),
  (1, 8, 'FAIL',    'Drain wire appears to be landed on both ends instead of one.', 10);

-- Report 2 results (IND-5210, mostly passing)
INSERT INTO requirement_results (report_id, requirement_id, status, reason, candidates) VALUES
  (2, 1, 'PASS',    'SolarEdge inverter label clearly visible with model and serial.', 5),
  (2, 2, 'PASS',    'Serial number fully readable on module backsheet.', 5),
  (2, 3, 'PASS',    'All modules visible, rail properly trimmed flush with last panel.', 6),
  (2, 4, 'FAIL',    'One wire bundle touching shingle surface near array edge.', 4),
  (2, 5, 'PASS',    'Digital inclinometer reading 22 degrees, placed directly on module surface.', 3),
  (2, 6, 'FAIL',    'Panel door partially closed, breaker rating partially obscured.', 4);

-- Report 3 results (IND-5501, all passing)
INSERT INTO requirement_results (report_id, requirement_id, status, reason, candidates) VALUES
  (3, 1, 'PASS',    'Enphase IQ combiner box label clearly legible.', 4),
  (3, 2, 'PASS',    'Serial number clearly readable.', 4),
  (3, 3, 'PASS',    'Complete array visible, rails trimmed.', 7),
  (3, 4, 'PASS',    'All wires properly elevated and secured with UV-rated clips.', 5),
  (3, 5, 'PASS',    'Tilt reading clearly visible at 18 degrees on module.', 2),
  (3, 6, 'PASS',    'Main breaker rating 200A clearly visible.', 3);

-- Report 4 results (SUN-1001, some failures)
INSERT INTO requirement_results (report_id, requirement_id, status, reason, candidates) VALUES
  (4, 1, 'PASS',    'Tesla Powerwall label clearly visible.', 3),
  (4, 2, 'PASS',    'Module serial number legible.', 4),
  (4, 3, 'FAIL',    'Rail extends 3 inches past last module on south array.', 8),
  (4, 4, 'PASS',    'Wire management properly elevated.', 6),
  (4, 5, 'PASS',    'Tilt measurement clear at 25 degrees.', 3),
  (4, 6, 'PASS',    'Main breaker 200A clearly visible.', 5),
  (4, 7, 'FAIL',    'LightReach not shown as partner in Tesla app screenshots.', 12),
  (4, 8, 'PASS',    'Comms cable properly terminated, drain wire on one end only.', 8);

-- Report 5 results (IND-5453 rerun — improved after fixes)
INSERT INTO requirement_results (report_id, requirement_id, status, reason, candidates) VALUES
  (5, 1, 'PASS',    'Manufacturer label clearly visible.', 8),
  (5, 2, 'PASS',    'Serial number now clearly readable after retake.', 8),
  (5, 3, 'PASS',    'Rail trimmed after crew returned to fix.', 9),
  (5, 4, 'PASS',    'Wires now elevated and clipped properly.', 7),
  (5, 5, 'PASS',    'Tilt measurement unchanged, still passing.', 4),
  (5, 6, 'FAIL',    'Main breaker photo still taken from poor angle.', 6),
  (5, 7, 'FAIL',    'Still showing wrong commissioning screenshot.', 18),
  (5, 8, 'FAIL',    'Drain wire issue not addressed.', 10);

-- ── Run Pricing ──────────────────────────────────────────────────────────────

INSERT INTO run_pricing (report_id, model, input_tokens, output_tokens, api_calls, estimated_cost) VALUES
  (1, 'claude-haiku-4-5-20251001', 154850, 2850, 19, 0.1353),
  (2, 'claude-haiku-4-5-20251001', 112000, 2100, 14, 0.0980),
  (3, 'claude-haiku-4-5-20251001', 120000, 2250, 15, 0.1050),
  (4, 'claude-haiku-4-5-20251001', 168000, 3150, 21, 0.1470),
  (5, 'claude-haiku-4-5-20251001', 48000,  900,  6,  0.0420);  -- rerun only 6 failed items

-- ── Impersonation Log ────────────────────────────────────────────────────────

INSERT INTO impersonation_log (superadmin_id, impersonated_user_id, started_at, ended_at, reason) VALUES
  (1, 4, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days' + INTERVAL '15 minutes', 'Testing crew view for IND-5453'),
  (1, 6, NOW() - INTERVAL '1 day',  NOW() - INTERVAL '1 day' + INTERVAL '5 minutes',   'Verifying Sunrise Power onboarding');
