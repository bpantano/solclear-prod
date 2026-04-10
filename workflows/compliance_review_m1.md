# Workflow: M1 Compliance Review (Phase 1)

## Objective
Given a CompanyCam project, determine whether the photo documentation package is complete and compliant with Palmetto M1 requirements for the job's specific lender + manufacturer + job type combination. Produce a gap report that tells a reviewer exactly what is missing or failing.

## Inputs Required
Before starting, collect:
1. `project_id` — CompanyCam project ID (or project name to search by)
2. `manufacturer` — One of: `SolarEdge`, `Tesla`, `Enphase`
3. `lender` — Currently: `LightReach` (Palmetto)
4. `has_battery` — Boolean: is a battery storage system included?
5. `is_backup_battery` — Boolean: is it a backup/gateway battery (vs. self-consumption only)?
6. `is_incentive_state` — Boolean: is the job in an incentive state requiring SI2?
7. `portal_access_granted` — Boolean: has monitoring portal access been granted to LightReach at M1?

These fields should eventually come from NetSuite. For now, collect them manually or from the checklist metadata.

## Tools to Run (in order)

### Step 1: Fetch project details
```
python tools/companycam_get_project.py --project_id <id>
```
Or search by name:
```
python tools/companycam_list_projects.py --query "<project name>"
```
Output: project ID, name, address, status

### Step 2: Fetch all checklists on the project
```
python tools/companycam_get_project_checklists.py --project_id <id>
```
Output: list of checklists with their sections and tasks. Identifies which Palmetto checklist template was applied (if any).

### Step 3: Fetch all photos on the project
```
python tools/companycam_get_project_photos.py --project_id <id>
```
Output: JSON list of all photos with URIs, timestamps, descriptions, and tags. Saved to `.tmp/photos_{project_id}.json`.

### Step 4: Determine required photo set
Based on inputs (manufacturer, lender, battery, backup, incentive state, portal access), determine which Palmetto photo IDs are required.

Reference: `knowledgebase/palmetto_m1_requirements.md` — Checklist Matrix section

Required photo set for common combos:
- **LightReach + SolarEdge, no battery, no incentive, portal granted:** PS4, PS5, PS6*, R1, R2, R3, R4, R5, R6, E2, E3, E4, E5, E6, E7, E8*, E9*, SC2
- **LightReach + Tesla, no battery:** Add PS3, SC1; replace SC2
- **LightReach + Enphase, no battery:** Add PS2 (mandatory), E1, E6 (enhanced)
- **+ Battery:** Add S1*, S2, S3, S4
- **+ Backup Battery:** Add S5, S6*
- **+ Incentive State:** Add SI2, PS1* conditional

*= conditional/if-applicable

### Step 5: Run compliance check
```
python tools/compliance_check.py \
  --project_id <id> \
  --manufacturer <manufacturer> \
  --lender LightReach \
  --has_battery <true/false> \
  --is_backup_battery <true/false> \
  --is_incentive_state <true/false> \
  --portal_access_granted <true/false>
```
This tool:
1. Loads photos from `.tmp/photos_{project_id}.json`
2. Loads the required photo set based on job parameters
3. For each required photo ID, checks whether a matching photo exists (by tag, description, or checklist task completion)
4. For matched photos, calls Claude Vision API to verify the photo meets the specific requirement
5. Outputs a compliance report to `.tmp/compliance_{project_id}.json`

### Step 6: Review and report
Read the compliance report and present:
- PASS/FAIL overall status
- List of satisfied requirements
- List of gaps (missing photos or failed validation)
- Specific remediation instructions for each gap

## Outputs
- `.tmp/compliance_{project_id}.json` — Machine-readable compliance result
- Console/chat report — Human-readable gap list with remediation steps

## Edge Cases

### No checklist on project
If the project has no Palmetto checklist applied, note it prominently. The crew skipped the checklist entirely. Flag for manual review.

### Photo exists but is blurry / illegible
The Vision check will flag this. Treat as a failed photo, not a missing photo — different remediation (retake vs. add).

### Mixed pitch roof
R5 requires one photo per unique pitch. If only one tilt photo exists on a multi-pitch roof, flag as incomplete.

### Multiple arrays
R2, R3, R4, R6 require one photo per array. Count arrays from the checklist or Aurora/Solo data (future). For now, flag if fewer photos exist than expected for a multi-array system.

### CompanyCam API rate limits
If rate limited, back off 30 seconds and retry. Document rate limit behavior here as it's discovered.

### Portal access not yet granted at submission
PS1 becomes required. Flag if missing.

## Notes / Lessons Learned
- CompanyCam photos do not have structured photo type metadata by default — matching photos to requirement IDs depends on tags, descriptions, or checklist task completion status. Ensure crews use the Palmetto checklist template so tasks are linked to photos.
- Ground mounts are INELIGIBLE for Palmetto LightReach from 2026-01-01 per FEOC requirements. Flag and reject these jobs immediately.
- Tilt app screenshots without array context are explicitly rejected by Palmetto. Vision check should flag these.
