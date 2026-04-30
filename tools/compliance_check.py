"""
Tool: compliance_check.py
Purpose: Run a full Palmetto M1 compliance check against a CompanyCam project's photos and checklists.

How it works:
1. Determines required photo set based on job parameters (manufacturer, battery, etc.)
2. Loads photos from .tmp/photos_{project_id}.json (run companycam_get_project_photos.py first)
3. Loads checklist task completion from the project's checklists
4. For each required photo ID, attempts to match a photo (by tag, description, or completed checklist task)
5. For matched photos, calls Claude Vision API to verify the photo meets its specific requirement
6. Outputs a compliance report

Usage:
  python tools/compliance_check.py \\
    --project_id <id> \\
    --manufacturer SolarEdge|Tesla|Enphase \\
    --has_battery true|false \\
    --is_backup_battery true|false \\
    --is_incentive_state true|false \\
    --portal_access_granted true|false

Output:
  .tmp/compliance_{project_id}.json
  Human-readable report to stdout
"""

import argparse
import json
import os
import re
import sys
import base64
from pathlib import Path
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
KNOWLEDGEBASE_DIR = Path(__file__).parent.parent / "knowledgebase"

API_BASE = "https://api.companycam.com/v2"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
COMPANYCAM_API_KEY = os.getenv("COMPANYCAM_API_KEY")


# ── Requirement definitions ──────────────────────────────────────────────────

# Each requirement: id, description, validation_prompt, condition_fn
# condition_fn(params) -> bool: whether this requirement applies given job params

def always(params):
    return True

def if_no_portal(params):
    return not params["portal_access_granted"]

def if_tesla(params):
    return params["manufacturer"] == "Tesla"

def if_solaredge(params):
    return params["manufacturer"] == "SolarEdge"

def if_enphase(params):
    return params["manufacturer"] == "Enphase"

def if_battery(params):
    return params["has_battery"]

def if_backup_battery(params):
    return params["has_battery"] and params["is_backup_battery"]

def if_incentive(params):
    return params["is_incentive_state"]

def if_no_portal_or_incentive(params):
    return not params["portal_access_granted"] or params["is_incentive_state"]

def if_enphase_or_incentive(params):
    return params["manufacturer"] == "Enphase" or params["is_incentive_state"]

def if_no_portal_and_battery(params):
    return params["has_battery"] and not params["portal_access_granted"]

def if_backup_and_no_portal(params):
    return params["has_battery"] and params["is_backup_battery"] and not params["portal_access_granted"]


# ── CompanyCam checklist task title → Palmetto requirement ID mapping ─────────
#
# task_titles: exact task titles from CompanyCam checklists (primary match method)
# keywords:    fallback — matches against photo descriptions if no checklist task found
#
# Template task titles sourced from:
#   LightReach_PV_Only  (template 184408, checklist 8981814)
#   Install_Battery     (template 95194,  checklist 9048095)
#   LightReach_PV_Battery (template 184407) — assumes same task titles as PV_Only + Battery sections

REQUIREMENTS = [
    {
        "id": "PS1",
        "section": "Project Site",
        "title": "Inverter / Micro-inverter / Optimizer Label",
        "condition": if_no_portal,
        "task_titles": ["Inverter label"],
        "keywords": ["inverter label", "micro-inverter", "microinverter", "optimizer", "model label"],
        "validation_prompt": (
            "This photo should show a manufacturer label for an inverter, micro-inverter, or AC optimizer. "
            "Verify: (1) Is a manufacturer label present in the photo? (2) Can the model information be identified? "
            "PASS if the label is present and the model can be determined, even if the photo requires zooming. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "PS2",
        "section": "Project Site",
        "title": "Combiner Box / Inverter Serial Number",
        "condition": if_enphase_or_incentive,
        "task_titles": ["Inverter label"],
        "keywords": ["serial", "combiner", "IQ combiner", "envoy", "Q.Home", "serial number"],
        "validation_prompt": (
            "This photo should show serial numbers for an inverter, DC safety switch, or combiner box. "
            "Verify: (1) Is a serial number present in the photo? (2) Can the serial number be identified? "
            "PASS if a serial number is visible and can be read, even if zooming would help. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "PS3",
        "section": "Project Site",
        "title": "MCI Location & Photo (Tesla only)",
        "condition": if_tesla,
        "task_titles": ["Stringing Map"],
        "keywords": ["MCI", "string map", "stringing map", "mid-circuit interrupter", "stringing"],
        "validation_prompt": (
            "Context: On Tesla solar installs, an MCI (Mid-Circuit Interrupter) is a "
            "rapid-shutdown device installed on the roof in-line with the DC strings. "
            "To document its location, installers submit a stringing map — a simple "
            "diagram of the array showing which panels are on which string and where "
            "the MCI sits. These maps are usually HAND-DRAWN on a notepad or whiteboard; "
            "typography, stick-figure drawings, and informal notation are normal and "
            "acceptable. "
            "\n\nPASS this requirement if the photo shows EITHER: "
            "(a) any stringing/string map diagram of the array (hand-drawn is fine) "
            "that indicates the MCI's approximate position, OR "
            "(b) a photograph of the physical MCI device installed on the roof. "
            "\n\nFAIL only if the photo shows neither of those — e.g., a blank page, "
            "an unrelated subject, or a map with no MCI marking at all. "
            "\n\nDo NOT fail on the grounds of drawing quality, informal style, or "
            "because a diagram isn't a photograph of hardware. "
            "\n\nDescribe what you see in the photo, then end with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "PS4",
        "section": "Project Site",
        "title": "Module Manufacturer Label",
        "condition": always,
        "task_titles": ["Manufacturer Labels"],
        "keywords": ["manufacturer labels", "module label", "panel label", "panel spec"],
        "validation_prompt": (
            "This photo should show the manufacturer label from a solar module/panel. "
            "Verify: (1) Is a panel label present? (2) Can make/model information be identified? "
            "PASS if the label is visible, even if zooming would be needed to read fine print. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "PS5",
        "section": "Project Site",
        "title": "Module Serial Number",
        "condition": always,
        "task_titles": ["Manufacturer Labels"],
        "keywords": ["manufacturer labels", "module serial", "panel serial", "serial number"],
        "validation_prompt": (
            "This photo should show a serial number label from a solar module. "
            "\n\nIMPORTANT — ground your answer in pixels, not guesses: "
            "A serial number is a specific alphanumeric string printed on the module's "
            "data label, typically near a barcode. Do NOT assume one exists — you must "
            "be able to actually read characters in the image. "
            "\n\nPASS only if you can transcribe AT LEAST 4 consecutive characters of "
            "a serial number that you actually see in the photo. Include those "
            "characters in your response as proof. If the photo is too blurry, too "
            "far away, or the angle obscures the label such that no characters are "
            "legible, respond FAIL. "
            "\n\nFAIL if: no serial label is visible, no characters are legible, or "
            "the photo shows something other than a module data label. "
            "\n\nDo NOT invent or guess at a serial number — if you cannot clearly "
            "read specific characters from the image, the answer is FAIL. "
            "\n\nExplain what you see: either quote the characters you can actually "
            "read in the photo, or explain why you cannot read any. Then end with a "
            "final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "R1",
        "section": "Roof",
        "title": "Attachment Close-Up (Flashing & Sealant)",
        "condition": always,
        "task_titles": ["Railing Type", "Roof Penetration & Conduit"],
        "keywords": ["railing type", "roof penetration", "flashing", "sealant", "attachment"],
        "selection_criteria": "a close-up showing a roof mounting attachment (lag bolt, L-foot, stanchion, or post) physically installed through the roof deck, with sealant visibly applied around the hardware — the metal hardware must be visible, not just a sealed hole",
        "validation_prompt": (
            "This photo should show a close-up of a roof attachment (lag bolt, "
            "stanchion, or post) where it penetrates the roof, documenting the "
            "weatherproof seal. Per Palmetto M1: sealant must always be visible "
            "and properly applied. Flashing is required when the racking system "
            "uses flashing (most pitched-roof installs); for systems without "
            "flashing, sealant alone may be sufficient as long as it's visibly "
            "applied within or around the attachment in a way that sheds water. "
            "\n\nIMPORTANT — work through these observations BEFORE picking a "
            "verdict. Write each observation as a numbered line:"
            "\n1. Subject check — Does the photo show a roof mounting attachment "
            "(lag bolt / stanchion / L-foot / post) physically installed through "
            "the roof deck, with the metal hardware visible? Or is it something "
            "else — a rail end, a sealed hole with no hardware visible, a bare "
            "deck, a completed array, or conduit? A sealed hole alone (no "
            "hardware visible) does NOT qualify — Palmetto requires documentation "
            "of the actual mounting hardware. Describe what is actually centered "
            "in the frame."
            "\n2. Sealant check — Is sealant visible at the penetration? "
            "Sealant typically appears as a black, gray, or clear "
            "bead/blob/smear applied around the bolt head, under the "
            "flashing, or directly on the shingle. It is a hand-applied "
            "caulking material — irregular shape, often glossy, sometimes "
            "with visible squeeze-out lines. "
            "Things that are NOT sealant (do not count these): rail end "
            "caps (molded plastic plugs on cut rail ends), rubber EPDM "
            "washers under bolt heads (these are gaskets, not sealant — "
            "though they're often used WITH sealant), the metal flashing "
            "itself, or shingle adhesive strips. "
            "State whether you see sealant, where it is, and whether it "
            "looks freshly applied vs. weathered/missing."
            "\n3. Flashing check — Is flashing visible (a metal or composite "
            "plate slid under the upper course of shingles to direct water "
            "around the attachment)? Note its presence and whether it is "
            "properly tucked under the upper shingle course or sitting on "
            "top of shingles."
            "\n\nOnly AFTER those three observations, choose:"
            "\n- PASS: observation #1 confirms a roof attachment point AND "
            "observation #2 confirms sealant is visibly applied at the "
            "penetration. (Flashing alone without visible sealant is NOT "
            "enough — sealant is the universally required element.)"
            "\n- FAIL: observation #1 shows the photo is NOT a roof "
            "attachment close-up with visible hardware (e.g., a rail end, "
            "a bare deck, an array overview, or a sealed hole with no "
            "mounting hardware visible), OR observation #2 confirms NO "
            "sealant is visible anywhere at the penetration."
            "\n- NEEDS_REVIEW: subject is the right kind of shot but sealant "
            "presence/quality is genuinely unclear due to glare, shadow, "
            "extreme angle, or a part of the attachment being out of frame. "
            "Use this when you'd be guessing rather than reading."
            "\n\nFORMAT — your response MUST follow this structure, in this "
            "order:"
            "\n1. <observation #1>"
            "\n2. <observation #2>"
            "\n3. <observation #3>"
            "\nVERDICT: PASS   (or FAIL, or NEEDS_REVIEW)"
            "\n\nDo NOT put the verdict at the top. Work through observations "
            "first, then commit to a verdict on the last line."
        ),
    },
    {
        "id": "R2",
        "section": "Roof",
        "title": "Rail + EGC + Wire Management (per array)",
        "condition": always,
        "task_titles": ["Racking Assembly + Grounding"],
        "keywords": ["racking assembly", "grounding", "rail", "EGC", "wire management", "clips"],
        "selection_criteria": "a wide pullback shot of a roof mounting plane showing the full racking system with rail, wire management clips, and EGC copper grounding wire routed between rails — not a close-up or a photo after panels are installed",
        "validation_prompt": (
            "Palmetto M1 R2 requires: a pullback of each mounting plane showing (1) rail and attachments installed "
            "with optimizers/micro-inverters if present, (2) wire management — wires secured with UV-rated clips or "
            "cable ties on the rail or modules, and (3) the EGC (Equipment Grounding Conductor) copper wire routed "
            "between the rails for each array.\n\n"
            "Evaluate the COMPLETE SET of photos together — on multi-array jobs the evidence may be spread across "
            "multiple photos, one per array. PASS if the photos collectively show a pullback of each array's mounting "
            "plane with rail, wire management, and EGC copper visible. FAIL if any array's mounting plane is missing "
            "from the documentation, or if wire management or EGC is absent across all photos.\n\n"
            "Note: the EGC appears as a copper wire (bare or green) running along or between the rails. It may not "
            "be clearly distinguishable at photo resolution — do not fail solely because you cannot identify it, "
            "but do fail if there is no evidence of any grounding conductor across the full photo set.\n\n"
            "Select as EVIDENCE only the photos that show a mounting plane pullback — exclude close-ups, "
            "under-array shots, or photos taken after panels are installed."
        ),
    },
    {
        "id": "R3",
        "section": "Roof",
        "title": "Complete Array with Rail Trimmed (per array)",
        "condition": always,
        "task_titles": ["Array Photos"],
        "keywords": ["array photos", "array", "all panels", "complete array"],
        "validation_prompt": (
            "This photo should show a complete solar array with all modules visible and rail trimmed. "
            "Verify: (1) Are all panels visible in the frame? (2) Is the rail trimmed (not extending past the last module)? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "R4",
        "section": "Roof",
        "title": "Under-Array Wire Management (per array)",
        "condition": always,
        "task_titles": ["Wire Management / Under Array"],
        "keywords": ["wire management / under array", "under array", "wire management"],
        "selection_criteria": "a photo showing wires under the solar array secured with clips, rail clamps, or wire management hardware above the roof surface",
        "validation_prompt": (
            "This photo should show wire management under the solar array after panels are installed. "
            "The rule is that wires must not touch the roof surface; they should be secured and "
            "bundled above the roof using clips, rail clamps, management channels, or standoffs. "
            "\n\nIMPORTANT — work through these observations BEFORE picking a verdict. Write each "
            "observation as a numbered line:"
            "\n1. Hardware check — Do you see any of the following in the photo: wire clips, "
            "rail clamps, wire management channels, standoffs, or the edge of the module/rack "
            "the wires appear secured to? Describe specifically what you see (including their "
            "approximate location in the frame)."
            "\n2. Contact check — Where do the wires physically contact the structure? Options: "
            "(a) clipped to a rail/channel above the roof, (b) resting directly on shingles with "
            "no visible support, (c) the contact point is obscured, blurred, or out of frame."
            "\n3. Camera angle check — Note whether the photo is taken at an angle that makes the "
            "clip/rail attachment points hard to see (e.g. parallel-to-roof shot, extreme close-up)."
            "\n\nOnly AFTER those three observations, choose:"
            "\n- PASS: observation #1 shows visible clips/rails AND observation #2 shows wires "
            "secured to them above the roof."
            "\n- FAIL: observation #1 shows NO management hardware AND observation #2 clearly "
            "shows wires resting flat on the roof surface. Both conditions required — absence "
            "of visible hardware alone is NOT enough to FAIL."
            "\n- NEEDS_REVIEW: anything else. Use this when hardware is partially visible, "
            "contact points are obscured, the camera angle defeats your ability to see attachment "
            "clearly, or you're tempted to say FAIL because 'wires are near shingles' without "
            "positive evidence of non-compliance. When in doubt, this is the correct answer."
            "\n\nFORMAT — your response MUST follow this structure, in this order:"
            "\n1. <your observation #1 text>"
            "\n2. <your observation #2 text>"
            "\n3. <your observation #3 text>"
            "\nVERDICT: PASS   (or FAIL, or NEEDS_REVIEW)"
            "\n\nDo NOT put the verdict at the top. Work through observations first, then "
            "commit to a verdict on the last line. This discipline is required."
        ),
    },
    {
        "id": "R5",
        "section": "Roof",
        "title": "Tilt Measurement (per unique pitch)",
        "condition": always,
        "task_titles": ["Tilt Measurement"],
        "keywords": ["tilt measurement", "tilt", "pitch", "angle", "degree"],
        "validation_prompt": (
            "This photo should show a tilt/pitch measurement taken on the solar module itself. "
            "Verify: (1) Is the measurement clearly legible? (2) Is the measurement taken on the module "
            "(NOT just a phone app screenshot without array context)? (3) Is the array visible in the photo? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL. "
            "FAIL if this is just a screenshot of a tilt app without the array visible."
        ),
    },
    {
        "id": "R6",
        "section": "Roof",
        "title": "Rooftop Junction Box (per junction box)",
        "condition": always,
        "task_titles": ["J-Box"],
        "keywords": ["J-Box", "j-box", "junction box", "jbox"],
        "selection_criteria": "a photo of a rooftop junction box with the COVER REMOVED, showing internal wiring and terminations (NOT a closed/sealed box viewed from outside)",
        "validation_prompt": (
            "This photo should show a rooftop junction box (J-Box) with its cover removed "
            "so conductor terminations and bonding are visible for inspection. "
            "\n\nIMPORTANT — work through these observations BEFORE picking a verdict. Write each "
            "observation as a numbered line:"
            "\n1. Lid/cover state — Is the junction box lid/cover REMOVED, LIFTED, or CLOSED? "
            "Describe what you see: is the internal chamber visible (lid off), or is the enclosure "
            "sealed with only its exterior visible? Note whether you see screw holes/gasket around "
            "the edge (indicates removed lid) or a flat covered top (indicates closed)."
            "\n2. Wiring visibility — Can you see individual conductors/wires terminated inside "
            "the box? If yes, describe color and count roughly. If no, describe what is blocking "
            "the view (closed lid, extreme angle, glare, obstruction)."
            "\n3. Exposed conductor check — If wiring IS visible, is there more than ~2 inches of "
            "exposed conductor exiting the box before entering a conduit or the array? Skip this if "
            "you can't see the wiring at all."
            "\n\nOnly AFTER those observations, choose:"
            "\n- PASS: lid is clearly off/removed AND conductors are visible AND terminations "
            "look complete AND no excessive exposed conductor. All four required."
            "\n- FAIL: lid is clearly closed/sealed (no internal view), OR you can clearly see "
            "conductors with excessive >2\" exposure outside the box."
            "\n- NEEDS_REVIEW: any ambiguity — lid state unclear, partially obscured view, glare "
            "or angle prevents confirming termination quality, or you're tempted to FAIL because "
            "you 'can't see wiring' without positive evidence the lid is actually closed."
            "\n\nFORMAT — your response MUST follow this structure, in this order:"
            "\n1. <observation #1>"
            "\n2. <observation #2>"
            "\n3. <observation #3>"
            "\nVERDICT: PASS   (or FAIL, or NEEDS_REVIEW)"
            "\n\nDo NOT put the verdict at the top. Work through observations first."
        ),
    },
    {
        "id": "E1",
        "section": "Electrical",
        "title": "Inverter / Combiner Box Interior (Enphase/QCells)",
        "condition": if_enphase,
        "task_titles": ["Inverter Location & Wiring"],
        "keywords": ["inverter location & wiring", "combiner box", "AC wiring", "branch circuit"],
        "validation_prompt": (
            "This photo should show an open combiner box with complete AC wiring and branch circuit breakers. "
            "Verify: (1) Is the box open? (2) Is all AC wiring visible? (3) Are all branch circuit breakers visible? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "E2",
        "section": "Electrical",
        "title": "Main Breaker Rating",
        "condition": always,
        "task_titles": ["Main Breaker"],
        "keywords": ["main breaker", "breaker rating", "ampere", "main disconnect"],
        "validation_prompt": (
            "This photo should show the main breaker with its amperage rating. "
            "Verify: (1) Is the main breaker visible? (2) Can the amperage rating be identified? "
            "PASS if the main breaker is shown and the rating can be determined, even if zooming would help. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "E3",
        "section": "Electrical",
        "title": "Main Panel Busbar Rating",
        "condition": always,
        "task_titles": ["MSP Label", "Full Bus Bar / All Breakers"],
        "keywords": ["MSP label", "full bus bar", "all breakers", "busbar", "bus rating", "panel label"],
        "validation_prompt": (
            "This photo should show the main panel's busbar rating label/sticker. "
            "Verify: (1) Is a panel label or sticker present? (2) Can the busbar rating be identified? "
            "PASS if the label is visible, even if zooming would be needed. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "E4",
        "section": "Electrical",
        "title": "Point of Interconnection (POI)",
        "condition": always,
        "task_titles": ["Backfeed Breaker", "Meter Enclosure"],
        "keywords": ["backfeed breaker", "meter enclosure", "POI", "IPC", "lug", "interconnection"],
        "validation_prompt": (
            "This photo should show the point of interconnection — a view of IPCs, parallel lugs, "
            "distribution blocks, breakers, or wire terminations. "
            "Verify: (1) Are interconnection components visible? (2) Can termination points be seen? "
            "PASS if the photo documents the point of interconnection. A single well-framed photo showing "
            "the components is sufficient — do not require both a pullback and close-up in one photo. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "E5",
        "section": "Electrical",
        "title": "Balance of System Pullback",
        "condition": always,
        "task_titles": ["Inverter Location & Wiring"],
        "keywords": ["inverter location & wiring", "BOS", "balance of system", "pullback"],
        "validation_prompt": (
            "This photo should show a pullback view of the balance-of-system (BOS) equipment area. "
            "Verify: (1) Does the photo show the general BOS area? (2) Is equipment visible in the frame? "
            "PASS if the photo provides context of where the BOS equipment is installed. "
            "Do not require every individual component to be identifiable. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "E6",
        "section": "Electrical",
        "title": "Production Meter or CTs",
        "condition": always,
        "task_titles": ["CT Installation", "Meter Enclosure"],
        "keywords": ["CT installation", "meter enclosure", "production meter", "production CT", "RGM"],
        "review_if_missing_for": ["tesla"],
        "validation_prompt": (
            "This photo should show the production metering device for this solar installation.\n\n"
            "Standard installations use a dedicated production CT clipped to the production circuit "
            "conductor, or a standalone production meter. Tesla/Powerwall installations use a Tesla "
            "Backup Switch (Gateway) or Tesla Remote Meter as the production monitoring device.\n\n"
            "PASS if: traditional production CTs or a dedicated production meter is visible and "
            "properly installed on the production circuit conductors.\n"
            "NEEDS_REVIEW if: a Tesla Backup Switch, Tesla Gateway, or Tesla Remote Meter is visible "
            "as the monitoring device — these require manual reviewer verification that the Tesla "
            "integration is complete and the meter collar is properly installed.\n"
            "FAIL if: no production metering device or CT is visible in the photo.\n\n"
            "Work through what you see, then end your response with a final line: "
            "VERDICT: PASS or VERDICT: FAIL or VERDICT: NEEDS_REVIEW."
        ),
    },
    {
        "id": "E7",
        "section": "Electrical",
        "title": "Consumption Metering (CTs)",
        "condition": always,
        "task_titles": ["CT Installation"],
        "keywords": ["CT installation", "consumption CT", "service feeder", "CT direction"],
        "review_if_missing_for": ["tesla"],
        "validation_prompt": (
            "This photo should show the consumption monitoring device for this solar installation.\n\n"
            "Standard installations use CTs clipped around service feeder conductors for consumption "
            "monitoring, with CT orientation/direction discernible. Tesla/Powerwall installations use "
            "the Tesla Backup Switch (Gateway) for consumption monitoring in place of traditional CTs.\n\n"
            "PASS if: CTs are visible on service feeder conductors with discernible orientation.\n"
            "NEEDS_REVIEW if: a Tesla Backup Switch or Tesla Gateway is visible as the consumption "
            "monitoring device — these require manual reviewer verification that the integration is "
            "complete.\n"
            "FAIL if: no consumption monitoring device or CT is visible in the photo.\n\n"
            "Work through what you see, then end your response with a final line: "
            "VERDICT: PASS or VERDICT: FAIL or VERDICT: NEEDS_REVIEW."
        ),
    },
    {
        "id": "E8",
        "section": "Electrical",
        "title": "Fused AC Disconnects",
        "condition": always,
        "task_titles": ["Disconnect(s)"],
        "keywords": ["disconnect(s)", "fused disconnect", "AC disconnect", "fuse rating"],
        "optional": True,
        "validation_prompt": (
            "This photo should show a fused AC disconnect with wiring and fuse ratings. "
            "Verify: (1) Is the disconnect visible with wiring? (2) Are fuse ratings present in the photo? "
            "PASS if the disconnect is documented with fuses visible, even if zooming is needed to read ratings. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "E9",
        "section": "Electrical",
        "title": "Combiner Sub Panels",
        "condition": always,
        "task_titles": ["Subpanel (if applicable)"],
        "keywords": ["subpanel (if applicable)", "sub panel", "combiner panel", "breaker rating"],
        "optional": True,
        "validation_prompt": (
            "This photo should show a sub panel with wiring, breakers, and bus rating label. "
            "Verify: (1) Is the sub panel visible with wiring? (2) Are breakers present? "
            "PASS if the sub panel is documented showing its wiring and breakers. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "S1",
        "section": "Storage",
        "title": "Battery Label",
        "condition": if_no_portal_and_battery,
        "task_titles": ["Battery Label"],
        "keywords": ["battery label", "battery manufacturer", "storage label"],
        "validation_prompt": (
            "This photo should show the manufacturer label on the battery/storage unit. "
            "Verify: (1) Is the battery label visible? (2) Is the make/model readable? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "S2",
        "section": "Storage",
        "title": "Comms Cable & Drain Wire",
        "condition": if_battery,
        "task_titles": ["Comms Cable & Drain Wire"],
        "keywords": ["comms cable & drain wire", "comms cable", "drain wire", "communication cable"],
        "validation_prompt": (
            "This photo should show battery comms cable terminations with the drain wire visible. "
            "Verify: (1) Are both ends of the comms cable terminated and visible? "
            "(2) Is the drain wire visible and landed on ONE end only (not both)? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL. "
            "FAIL if drain wire is on both ends or neither end."
        ),
    },
    {
        "id": "S3",
        "section": "Storage",
        "title": "Battery CT",
        "condition": if_battery,
        "task_titles": ["CT Installation", "Battery Wiring"],
        "keywords": ["CT installation", "battery wiring", "battery CT", "battery current transformer"],
        "review_if_missing_for": ["tesla"],
        "validation_prompt": (
            "This photo should show the battery current monitoring device for this storage installation.\n\n"
            "Standard installations use a dedicated CT for battery current monitoring, with orientation "
            "discernible. Tesla/Powerwall installations use the Tesla Backup Switch (Gateway) for "
            "battery current monitoring in place of a traditional CT.\n\n"
            "PASS if: a battery CT is visible with discernible direction/orientation.\n"
            "NEEDS_REVIEW if: a Tesla Backup Switch or Tesla Gateway is visible as the battery "
            "monitoring device — these require manual reviewer verification that the integration is "
            "complete.\n"
            "FAIL if: no battery monitoring device or CT is visible in the photo.\n\n"
            "Work through what you see, then end your response with a final line: "
            "VERDICT: PASS or VERDICT: FAIL or VERDICT: NEEDS_REVIEW."
        ),
    },
    {
        "id": "S4",
        "section": "Storage",
        "title": "Battery BOS Pullback",
        "condition": if_battery,
        "task_titles": ["Battery Location", "Mounting Bracket Installation"],
        "keywords": ["battery location", "mounting bracket installation", "battery BOS", "storage install"],
        "validation_prompt": (
            "This photo should show a pullback of the battery installation area showing the battery "
            "in context of the surrounding equipment. "
            "Verify: (1) Is a battery/storage unit visible? (2) Is surrounding equipment context shown? "
            "PASS if the photo shows the battery install location with context. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "S5",
        "section": "Storage",
        "title": "Gateway / Transfer Switch Wiring (Backup Battery)",
        "condition": if_backup_battery,
        "task_titles": ["Transfer Switch Wiring"],
        "keywords": ["transfer switch wiring", "gateway", "transfer switch", "ATS"],
        "validation_prompt": (
            "This photo should show the transfer switch/gateway panel interior with all wiring "
            "and breaker ratings clearly legible. "
            "Verify: (1) Is the internal wiring visible? (2) Are breaker ratings readable? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "S6",
        "section": "Storage",
        "title": "Gateway / Transfer Switch Label (Backup Battery)",
        "condition": if_backup_and_no_portal,
        "task_titles": ["Inverter label"],
        "keywords": ["inverter label", "gateway label", "ATS label", "transfer switch label"],
        "validation_prompt": (
            "This photo should show the manufacturer label for the ATS/gateway installed on site. "
            "Verify: (1) Is a manufacturer label visible? (2) Is the make/model readable? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "SC1",
        "section": "Commissioning",
        "title": "Tesla Commissioning Screenshots",
        "condition": if_tesla,
        "task_titles": ["Monitoring App Screenshots"],
        "keywords": ["monitoring app screenshots", "commissioning", "LightReach partner", "cellular", "PCS settings"],
        "validation_prompt": (
            "These are screenshots from the Tesla installer commissioning app. A "
            "complete commissioning record confirms several separate operational "
            "settings that typically live on DIFFERENT screens — so criteria will "
            "be spread across multiple screenshots. Verify each criterion is "
            "confirmed SOMEWHERE in the set."
        ),
        "criteria": [
            "LightReach is added as a monitoring/service partner (installer partner entry)",
            "Inverter and CTs (current transformers) are enabled — not in an error/alert state",
            "Networking is connected via Cellular (cellular shown as active connection type)",
            "Operations settings show both a panel current limit value AND PCS (power control system) settings configured",
        ],
    },
    {
        "id": "SC2",
        "section": "Commissioning",
        "title": "SolarEdge Commissioning Screenshots",
        "condition": if_solaredge,
        "task_titles": ["Monitoring App Screenshots"],
        "keywords": ["monitoring app screenshots", "commissioning", "backup reserve", "storm guard", "SolarEdge"],
        "validation_prompt": (
            "These are screenshots from the SolarEdge installer/monitoring app. "
            "Verify each commissioning criterion is confirmed SOMEWHERE in the set "
            "of screenshots (they commonly live on separate screens)."
        ),
        "criteria": [
            "Backup reserve is set to at least 20% (any value ≥ 20% qualifies)",
            "Storm Guard is enabled (shown as ON or active)",
        ],
    },
    {
        "id": "SI2",
        "section": "Site Improvements",
        "title": "Incentive State Serial Photos",
        "condition": if_incentive,
        "task_titles": ["Inverter label", "Domestic Content"],
        "keywords": ["domestic content", "inverter label", "serial number", "IQ combiner serial"],
        "validation_prompt": (
            "This photo should show serial numbers for the inverter or combiner box — "
            "required for incentive state projects. "
            "Verify: (1) Is a serial number present in the photo? (2) Can the serial number be identified? "
            "PASS if a serial number is visible, even if zooming would be needed. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
]


# ── Cost estimation ──────────────────────────────────────────────────────────

# Pricing per million tokens (as of April 2026)
MODEL_PRICING = {
    "claude-haiku-4-5-20251001":  {"input": 0.80,  "output": 4.00},   # prototype default
    "claude-sonnet-4-6":          {"input": 3.00,  "output": 15.00},
    "claude-opus-4-6":            {"input": 15.00, "output": 75.00},
}

# Rough token estimates per vision call
# Image: CompanyCam "web" size images are typically 800-1500px → ~1,600 tokens via base64
# Prompt: ~150 tokens per requirement prompt
# Output: ~100 tokens per response (we cap at 200)
AVG_IMAGE_TOKENS = 1600
AVG_PROMPT_TOKENS = 150
AVG_OUTPUT_TOKENS = 80


def estimate_run_cost(num_vision_checks: int, model: str = "claude-haiku-4-5-20251001") -> dict:
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-haiku-4-5-20251001"])
    input_tokens = num_vision_checks * (AVG_IMAGE_TOKENS + AVG_PROMPT_TOKENS)
    output_tokens = num_vision_checks * AVG_OUTPUT_TOKENS
    cost = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]
    return {
        "model": model,
        "vision_checks": num_vision_checks,
        "est_input_tokens": input_tokens,
        "est_output_tokens": output_tokens,
        "est_cost_usd": round(cost, 4),
        "haiku_cost_usd": round(cost, 4) if "haiku" in model else round(
            (input_tokens / 1_000_000) * 0.80 + (output_tokens / 1_000_000) * 4.00, 4
        ),
    }


def print_cost_estimate(params: dict):
    """Print expected cost before running vision checks. Call this before a run."""
    applicable = sum(1 for r in REQUIREMENTS if r["condition"](params) and not r.get("optional"))
    # Two-tier: thumbnails for selection (~400 tok each, avg 8 per task) + 1 full image for validation
    AVG_THUMBS_PER_TASK = 8
    AVG_THUMB_TOKENS = 400
    tier1_tokens = applicable * (AVG_THUMBS_PER_TASK * AVG_THUMB_TOKENS + 100)
    tier2_tokens = applicable * (AVG_IMAGE_TOKENS + AVG_PROMPT_TOKENS)
    input_tokens = tier1_tokens + tier2_tokens
    output_tokens = applicable * 150
    cost = (input_tokens / 1_000_000) * 0.80 + (output_tokens / 1_000_000) * 4.00
    print(f"\n── COST ESTIMATE ──────────────────────────────────")
    print(f"  Model:          claude-haiku-4-5-20251001")
    print(f"  Requirements:   {applicable} | API calls: {applicable} (1 per requirement)")
    print(f"  Est. tokens:    ~{input_tokens:,} in / ~{output_tokens:,} out")
    print(f"  Est. cost:      ~${cost:.4f} USD")
    print(f"──────────────────────────────────────────────────\n")


# ── Vision check ─────────────────────────────────────────────────────────────

# Max candidate photos to send per requirement — caps token cost
# No cap on candidate photos — two-tier approach evaluates all candidates via thumbnails

# Anthropic API headers (reused across calls)
ANTHROPIC_HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY or "",
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}


# ── API cost tracking ────────────────────────────────────────────────────────

# Pricing per million tokens (USD). Keep this aligned with Anthropic's
# published rates; models not listed fall through with zero cost.
_MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
    "claude-sonnet-4-6":         {"input": 3.0, "output": 15.0},
    "claude-opus-4-7":           {"input": 15.0, "output": 75.0},
}


def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost for a single API call."""
    price = _MODEL_PRICING.get(model)
    if not price:
        return 0.0
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


# Thread-local attribution context. Callers (e.g. live_server.run_check_thread)
# wrap a compliance-check invocation in `set_call_context(report_id=...)` so
# every _call_anthropic inside that scope gets attributed to that report.
# Leaving this None (no context) simply skips logging — useful for one-off
# scripts that shouldn't pollute the DB.
import threading as _threading
_call_ctx = _threading.local()


class set_call_context:
    """Context manager that scopes API-call attribution to a report_id etc.

    Usage:
        with set_call_context(report_id=42):
            run_compliance_check(...)
    """
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        prior = getattr(_call_ctx, "attrs", None)
        self._prior = prior
        merged = {**(prior or {}), **self.kwargs}
        _call_ctx.attrs = merged
        return merged

    def __exit__(self, *args):
        _call_ctx.attrs = self._prior


def _log_api_call(model, input_tokens, output_tokens, duration_ms, req_id):
    """Insert a row in api_call_log. Never raises — logging must not break checks."""
    ctx = getattr(_call_ctx, "attrs", None) or {}
    if not ctx.get("report_id") and not ctx.get("log_anyway"):
        return  # no report context → skip (e.g. diagnostic scripts)
    try:
        from tools.db import execute
        # req_id is typically the requirement code (e.g. "R6"); purpose comes
        # from the surrounding context when set, otherwise defaults to "vision".
        cost = _calculate_cost(model, input_tokens or 0, output_tokens or 0)
        execute(
            """INSERT INTO api_call_log
               (report_id, requirement_code, purpose, model,
                input_tokens, output_tokens, cost_usd, duration_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                ctx.get("report_id"),
                req_id,
                ctx.get("purpose", "vision"),
                model,
                input_tokens or 0,
                output_tokens or 0,
                cost,
                duration_ms,
            ),
        )
    except Exception as e:
        print(f"WARNING: api_call_log insert failed: {e}", file=sys.stderr)


_MAX_RETRIES = 6       # total window ≈ 5+10+20+40+60+60 = ~195s per call
_BASE_BACKOFF_S = 5
_MAX_BACKOFF_S = 60

# Global semaphore caps the total number of concurrent Anthropic API
# calls across ALL active check runs. Without this, two concurrent
# checks (each max_workers=2) can burst to 4 simultaneous calls and
# starve each other via 429 retries — the second check's calls succeed
# while the first check waits through exponential backoff, making the
# first check look "frozen" until the second finishes.
# Value 3: 1 check uses up to 3 freely; 2 checks share 3 (~1.5 each,
# fairer); 3+ checks get 1 each. Keeps total ITPM burst well inside
# our Tier 2 limit while distributing capacity proportionally.
_anthropic_global_semaphore = _threading.Semaphore(3)


def _retry_after_seconds(resp) -> Optional[float]:
    """Extract a sleep duration from Anthropic's rate-limit response headers.

    Anthropic sends `retry-after` (seconds, integer) plus token-bucket
    reset timestamps like `anthropic-ratelimit-input-tokens-reset` (ISO
    8601). Prefer retry-after when present; otherwise compute the gap
    until the input-tokens bucket refills. Returns None if neither is
    usable — caller should fall back to exponential backoff."""
    ra = resp.headers.get("retry-after")
    if ra:
        try:
            return max(0.0, float(ra))
        except ValueError:
            pass
    reset = resp.headers.get("anthropic-ratelimit-input-tokens-reset")
    if reset:
        try:
            from datetime import datetime, timezone
            # Anthropic returns ISO with trailing 'Z'; strip it for fromisoformat
            reset_dt = datetime.fromisoformat(reset.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return max(0.0, (reset_dt - now).total_seconds())
        except (ValueError, TypeError):
            pass
    return None


def _call_anthropic(payload: dict, req_id: str) -> Optional[str]:
    """Make an Anthropic API call with bounded retries on 429.
    Returns response text or None. Logs usage to api_call_log when a
    report context is active (see set_call_context).

    Retry policy: up to _MAX_RETRIES attempts. On 429, sleep the longer
    of (server-provided retry-after) and (exponential backoff starting
    at _BASE_BACKOFF_S, capped at _MAX_BACKOFF_S). The server hint is
    almost always shorter than our blind 20s/40s/60s sequence — honoring
    it both reduces total wait time and avoids burning all retries on
    transient bursts."""
    import time
    for attempt in range(_MAX_RETRIES):
        try:
            # Acquire the global slot before making the network call.
            # This blocks if 3 other calls are already in-flight, which
            # naturally spreads capacity across concurrent check runs
            # instead of letting one run monopolise the API budget.
            _anthropic_global_semaphore.acquire()
            try:
                t0 = time.time()
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers=ANTHROPIC_HEADERS,
                    timeout=60,
                )
            finally:
                _anthropic_global_semaphore.release()
            duration_ms = int((time.time() - t0) * 1000)
            # Treat 429 (rate-limit) AND 5xx transient errors (500 internal,
            # 502 bad gateway, 503 unavailable, 504 gateway timeout, 529
            # overloaded) as retryable with the same retry-after-aware
            # backoff. 529 in particular is Anthropic's "overloaded" signal
            # — means their capacity is saturated and we should back off
            # longer than a simple rate-limit retry.
            if resp.status_code == 429 or resp.status_code in (500, 502, 503, 504, 529):
                # Prefer server hint; fall back to exponential. Always at
                # least 1s to avoid hammering. Cap so a misconfigured
                # server can't park us for hours.
                server_wait = _retry_after_seconds(resp)
                backoff = min(_BASE_BACKOFF_S * (2 ** attempt), _MAX_BACKOFF_S)
                wait = max(1.0, server_wait if server_wait is not None else backoff)
                wait = min(wait, _MAX_BACKOFF_S)
                src = "server" if server_wait is not None else "backoff"
                kind = "Rate limited" if resp.status_code == 429 else f"HTTP {resp.status_code}"
                print(f"  {kind} on {req_id}, retrying in {wait:.1f}s ({src})...", file=sys.stderr)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            body = resp.json()
            usage = body.get("usage", {}) or {}
            _log_api_call(
                model=payload.get("model", ""),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                duration_ms=duration_ms,
                req_id=req_id,
            )
            return body["content"][0]["text"]
        except requests.exceptions.RequestException as e:
            # Network/timeout/connection errors — worth retrying. Anything
            # else (JSON decode, missing keys, etc.) won't get better on
            # retry, so we let those fail through immediately below.
            if attempt == _MAX_RETRIES - 1:
                return f"ERROR: {e}"
            # Continue to next attempt with the same backoff schedule
            time.sleep(min(_BASE_BACKOFF_S * (2 ** attempt), _MAX_BACKOFF_S))
            continue
        except (KeyError, IndexError, ValueError) as e:
            # Malformed response shape — retrying won't help. Fail fast so
            # the caller sees an actionable error instead of "Max retries".
            return f"ERROR: malformed Anthropic response: {e}"
    return "ERROR: Max retries exceeded"


def _download_image(url: str) -> Optional[tuple]:
    """Download image and return (base64_data, media_type) or None on failure."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = base64.standard_b64encode(r.content).decode("utf-8")
        media_type = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
        return data, media_type
    except Exception:
        return None


# Concurrent fetcher used by the prefilter + validation steps. With
# CompanyCam serving from imgproxy at ~50-300ms latency per photo and
# requirements occasionally fielding 30+ candidates, doing these in
# series adds several seconds per worker. 8 in parallel is well below
# any sane HTTP host limit and saturates our outbound bandwidth.
_DOWNLOAD_CONCURRENCY = 8


def _download_images_parallel(urls_with_keys):
    """Download many images concurrently. Input is an iterable of
    (key, url) pairs; output is a dict {key: (data, media_type)} only
    for the ones that succeeded. Order does not matter to callers — they
    look up by their own key."""
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    pairs = [(k, u) for k, u in urls_with_keys if u]
    if not pairs:
        return out
    with ThreadPoolExecutor(max_workers=_DOWNLOAD_CONCURRENCY) as ex:
        results = ex.map(lambda p: (p[0], _download_image(p[1])), pairs)
        for key, result in results:
            if result is not None:
                out[key] = result
    return out


VISION_MODEL = "claude-sonnet-4-6"
PREFILTER_MODEL = "claude-haiku-4-5-20251001"

# When a requirement has more than this many candidates, run a cheap Haiku
# pre-filter on thumbnails to pick the best PREFILTER_KEEP photos, then send
# only those (full-res) to Sonnet. Above ~25 photos the Anthropic API
# returns 413/400 from base64 payload size; below ~10 the prefilter cost
# isn't worth it. 5 is the same as keep — see threshold rationale in the
# 2026-04-23 conversation: keeping K means filtering kicks in at K+1.
PREFILTER_THRESHOLD = 5
PREFILTER_KEEP = 5

# Hard cap on candidates before the prefilter runs. Checklist task photos
# have no separate thumbnail URL so the prefilter downloads full-res for
# every candidate. R2 ("Racking Assembly + Grounding") routinely accumulates
# 50-100+ photos across a job, making uncapped prefilter fetches the dominant
# cost. Take the most recent MAX_PREFILTER_CANDIDATES; crews upload in
# chronological order so the tail is the final installation state.
MAX_PREFILTER_CANDIDATES = 18  # Anthropic hard limit is 20 images per request;
# reference photos take up to 2 slots, leaving 18 safe for candidate thumbnails.

# For multi-criterion mode (SC1/SC2) we can't pre-filter — every photo is
# evidence. Cap the number we send full-res to stay under the payload limit.
# If a project genuinely has more screenshots than this, the most recent
# ones are usually the relevant commissioning state.
MULTI_CRITERION_MAX = 20


# Requirements excluded from reference-photo prefiltering because their
# first Palmetto reference photo is a multi-image collage that confuses
# the prefilter model (it tries to match the collage layout instead of
# the subject matter). Text-only selection_criteria works better here.
_REFERENCE_PHOTO_EXCLUDED = {"PS1", "PS2"}


def _load_reference_photos(req_code: str, max_photos: int = 2) -> list:
    """Load Palmetto reference photos for a requirement from the DB.
    Returns a list of (base64_data, mime_type) tuples, at most max_photos.
    Empty list if none found, DB unavailable, or req is in the exclusion
    set — caller falls back to text-only selection gracefully."""
    if req_code.upper() in _REFERENCE_PHOTO_EXCLUDED:
        return []
    try:
        from tools.db import fetch_all
        import base64 as _b64
        # Fetch one extra so we can detect multi-photo requirements.
        # Palmetto's pattern: first photo = collage/overview, subsequent
        # photos = specific examples. Skip the first when multiple exist.
        rows = fetch_all(
            "SELECT image_bytes, mime_type FROM requirement_reference_photos "
            "WHERE requirement_code = %s ORDER BY display_order ASC LIMIT %s",
            (req_code.upper(), max_photos + 1),
        )
        if len(rows) > 1:
            rows = rows[1:]  # drop the collage overview, keep specific examples
        rows = rows[:max_photos]
        result = []
        for row in rows:
            img = row.get("image_bytes")
            if img:
                data = _b64.standard_b64encode(bytes(img)).decode("utf-8")
                result.append((data, row.get("mime_type") or "image/jpeg"))
        return result
    except Exception as e:
        print(f"  WARNING: could not load reference photos for {req_code}: {e}", file=sys.stderr)
        return []


def _haiku_prefilter(candidates: list, requirement: dict, keep: int = PREFILTER_KEEP) -> list:
    """Cheap Haiku pass that ranks candidate photos by relevance to the
    requirement and returns the top-`keep` (in original task order). Uses
    thumbnails only, so payload stays small even at 30+ candidates.

    Returns indices into `candidates` of the photos to keep. On any failure
    falls back to the first `keep` candidates so the main vision call still
    runs (degraded but not broken)."""
    fallback = list(range(min(keep, len(candidates))))
    if not ANTHROPIC_API_KEY:
        return fallback

    # Parallel-fetch thumbnails (was serial — added ~3-6s per worker for
    # 30-candidate requirements). Keys are original-candidate indices so we
    # preserve the mapping back to `candidates` after Haiku picks winners.
    fetched = _download_images_parallel(
        (i, get_photo_thumbnail_url(p)) for i, p in enumerate(candidates)
    )
    # Order matters for the labels we send to Haiku (and for index ↔ photo
    # mapping after) — keep original task order, drop misses.
    downloaded = [
        (i, *fetched[i]) for i in range(len(candidates)) if i in fetched
    ]

    if not downloaded:
        return fallback

    selection_criteria = requirement.get("selection_criteria") or requirement["title"]

    # Load Palmetto reference photos for this requirement. Prepending them
    # gives Haiku a concrete visual standard to rank against instead of
    # relying solely on text description — significantly improves pick
    # accuracy for visually ambiguous requirements like R1 and R6.
    ref_photos = _load_reference_photos(requirement["id"])

    content = []
    if ref_photos:
        content.append({"type": "text", "text": (
            f"The following {'photo is' if len(ref_photos) == 1 else 'photos are'} "
            f"from Palmetto's official M1 documentation showing what a correct "
            f"\"{requirement['title']}\" photo looks like. Use "
            f"{'it' if len(ref_photos) == 1 else 'them'} as your visual standard "
            f"when ranking the candidates below."
        )})
        for ref_data, ref_mime in ref_photos:
            content.append({"type": "text", "text": "Palmetto reference:"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": ref_mime, "data": ref_data}})
        content.append({"type": "text", "text": (
            f"Now, from the {len(downloaded)} candidate photos below, pick the "
            f"{keep} that best show the same subject and coverage as the reference "
            f"{'photo' if len(ref_photos) == 1 else 'photos'} above. Match on "
            f"subject matter, not photo quality — field photos will be rougher "
            f"than the reference but should show the same elements."
        )})
    for label_idx, (_, data, media_type) in enumerate(downloaded, start=1):
        content.append({"type": "text", "text": f"Photo {label_idx}:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
    if ref_photos:
        content.append({"type": "text", "text": (
            f"Reply with ONLY a comma-separated list of the {keep} best-matching "
            f"photo numbers, best match first. Example:\n"
            f"  PICKS: 3, 7, 1, 4, 9\n"
            f"No other text — just the PICKS line."
        )})
    else:
        content.append({"type": "text", "text": (
            f"Pick the {keep} photos most likely to show: \"{selection_criteria}\".\n\n"
            f"There are {len(downloaded)} candidates total. Reply with ONLY a comma-separated "
            f"list of photo numbers, in order of best match first. Example:\n"
            f"  PICKS: 3, 7, 1, 4, 9\n"
            f"No other text — just the PICKS line."
        )})

    payload = {
        "model": PREFILTER_MODEL,
        "max_tokens": 80,
        "messages": [{"role": "user", "content": content}],
    }
    # Tag this call as 'prefilter' so api_call_log distinguishes the cheap
    # Haiku narrowing pass from the expensive Sonnet validation.
    with set_call_context(purpose="prefilter"):
        text = _call_anthropic(payload, requirement["id"])
    if not text or text.startswith("ERROR"):
        return fallback

    m = re.search(r"PICKS\s*:\s*([\d,\s]+)", text, re.IGNORECASE)
    if not m:
        return fallback

    label_indices = []
    for tok in m.group(1).split(","):
        tok = tok.strip()
        if tok.isdigit():
            label_indices.append(int(tok))

    # Map model's 1-based labels back to original `candidates` indices.
    orig_indices = []
    for label in label_indices:
        if 1 <= label <= len(downloaded):
            orig_indices.append(downloaded[label - 1][0])
        if len(orig_indices) >= keep:
            break

    if not orig_indices:
        return fallback

    # Restore original task order so downstream logic stays predictable.
    return sorted(set(orig_indices))


def check_candidates_with_vision(candidates: list, requirement: dict) -> dict:
    """
    Single-tier vision check. Sends all candidate photos + validation prompt to
    Sonnet in one call. The model both picks the best-matching photo (CHOICE)
    and validates it (VERDICT) within a single response, plus emits a
    customer-facing EXPLANATION that the UI surfaces as the reason.

    Why single-tier: previously ran a cheap Haiku selection pass ("Tier 1")
    followed by a Haiku validation pass ("Tier 2"). Haiku's multi-image
    reasoning was ~80% reliable — compounding across 25 requirements that
    meant only ~0.4% of reports were fully correct. Sonnet handles both
    tasks reliably in one call, with lower total API round trips and simpler
    code. See diagnosis notes in memory for 2026-04-22.
    """
    if not ANTHROPIC_API_KEY:
        return {"result": "SKIP", "reason": "ANTHROPIC_API_KEY not set"}

    # Decide which candidates to send to Sonnet full-res.
    # - Multi-criterion (SC1/SC2): can't pre-filter (every photo is evidence);
    #   cap at MULTI_CRITERION_MAX most-recent to stay under the payload limit.
    # - Single-winner mode with > PREFILTER_THRESHOLD candidates: run a Haiku
    #   thumbnail pass first to narrow to PREFILTER_KEEP.
    # - Otherwise (≤ threshold): send everything as-is.
    truncation_note = ""  # appended to user-facing reason if non-empty
    if requirement.get("criteria"):
        if len(candidates) > MULTI_CRITERION_MAX:
            original_count = len(candidates)
            # Photos are in task order from CompanyCam; assume newest at the
            # end (typical upload order). Take the tail.
            candidates = candidates[-MULTI_CRITERION_MAX:]
            truncation_note = (
                f" (Note: this requirement had {original_count} candidate photos; "
                f"only the {MULTI_CRITERION_MAX} most recent were analyzed. "
                f"If a criterion is shown only on an older screenshot it may be missed — "
                f"consider re-checking after consolidating the screenshot set.)"
            )
            print(
                f"WARNING: {requirement['id']} multi-criterion truncated "
                f"{original_count} → {MULTI_CRITERION_MAX} candidates "
                f"(MULTI_CRITERION_MAX cap)",
                file=sys.stderr, flush=True,
            )
    elif len(candidates) > PREFILTER_THRESHOLD:
        import time as _t
        _t0 = _t.time()
        if len(candidates) > MAX_PREFILTER_CANDIDATES:
            print(f"[timing:{requirement['id']}] capping {len(candidates)} → {MAX_PREFILTER_CANDIDATES} candidates", file=sys.stderr, flush=True)
            candidates = candidates[-MAX_PREFILTER_CANDIDATES:]
        print(f"[timing:{requirement['id']}] starting prefilter with {len(candidates)} candidates", file=sys.stderr, flush=True)
        keep_indices = _haiku_prefilter(candidates, requirement)
        print(f"[timing:{requirement['id']}] prefilter done in {_t.time()-_t0:.1f}s → {len(keep_indices)} kept", file=sys.stderr, flush=True)
        if keep_indices:
            candidates = [candidates[i] for i in keep_indices]

    # Download all candidates (full-res) in parallel. Skip any that fail —
    # the model can still reason about the ones that succeeded. Photos keep
    # their original task-list order for consistency with what the
    # CompanyCam API returns.
    import time as _t
    _t1 = _t.time()
    urls_by_idx = {i: get_photo_web_url(p) for i, p in enumerate(candidates)}
    fetched = _download_images_parallel(urls_by_idx.items())
    print(f"[timing:{requirement['id']}] full-res download of {len(candidates)} photos done in {_t.time()-_t1:.1f}s", file=sys.stderr, flush=True)
    downloaded = [
        (i, urls_by_idx[i], *fetched[i])
        for i in range(len(candidates))
        if i in fetched
    ]

    if not downloaded:
        return {"result": "ERROR", "reason": "Could not download any candidate photos", "photo_urls": {}}

    # Build content: label BEFORE each image (Anthropic best practice for
    # multi-image reasoning — label-after was causing the model to bind labels
    # to the NEXT image, which swapped descriptions).
    content = []
    for model_idx, (_, _, data, media_type) in enumerate(downloaded, start=1):
        content.append({"type": "text", "text": f"Photo {model_idx}:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})

    # Multi-criterion mode: when the requirement specifies a list of criteria
    # that must ALL be confirmed across a SET of photos (commonly used for
    # commissioning screenshots where each criterion lives on a different
    # screen). Otherwise the default single-winner-pick + validate flow.
    if requirement.get("criteria"):
        content.append({"type": "text", "text": _build_multi_criterion_prompt(requirement, len(downloaded))})
    else:
        content.append({"type": "text", "text": _build_validation_prompt(requirement, len(downloaded))})

    # max_tokens budgets per-photo description room plus validation reasoning
    # plus the final VERDICT + EXPLANATION lines. Capped so a task with 15+
    # photos can't blow up costs.
    dynamic_max_tokens = min(500 + 60 * len(downloaded), 1400)
    payload = {
        "model": VISION_MODEL,
        "max_tokens": dynamic_max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    text = _call_anthropic(payload, requirement["id"])
    print(f"[debug:{requirement['id']}] raw response tail: {repr((text or '')[-300:])}", file=sys.stderr, flush=True)
    if text and text.startswith("ERROR"):
        # Best-effort photo_urls even on error — default to task order.
        all_photo_urls = {i + 1: get_photo_web_url(p) for i, p in enumerate(candidates) if get_photo_web_url(p)}
        err_reason = text + (truncation_note or "")
        return {"result": "ERROR", "reason": err_reason, "photo_urls": all_photo_urls}

    # In multi-criterion mode there's no single winner — every photo is
    # part of the evidence set. Keep task-order indexing so photo_urls[1] is
    # just "first screenshot" (a stable, predictable reference).
    all_photo_captions = {}  # populated in single-winner path when EVIDENCE line is present
    if requirement.get("criteria"):
        all_photo_urls = {}
        for i, photo in enumerate(candidates):
            url = get_photo_web_url(photo)
            if url:
                all_photo_urls[i + 1] = url
    else:
        # Try to extract explicit EVIDENCE photo numbers from the response.
        # If the model cited specific photos, store only those — this keeps
        # irrelevant candidates out of the report and moves toward using
        # AI-selected photos as the submission evidence set.
        evidence_nums = _parse_evidence(text or "", len(downloaded))
        photo_descs = _parse_photo_descriptions(text or "", len(downloaded))
        print(f"[debug:{requirement['id']}] photo_descs keys={list(photo_descs.keys())} evidence_nums={evidence_nums}", file=sys.stderr, flush=True)
        if evidence_nums:
            all_photo_urls = {}
            all_photo_captions = {}
            for rank, model_photo_num in enumerate(evidence_nums, start=1):
                candidate_entry = downloaded[model_photo_num - 1]
                url = candidate_entry[1]
                if url:
                    all_photo_urls[rank] = url
                desc = photo_descs.get(model_photo_num)
                if desc:
                    all_photo_captions[rank] = desc
        else:
            # Fallback: existing single-winner-pick logic — winner at key 1,
            # remaining candidates at keys 2+. Used when EVIDENCE line is
            # absent (legacy prompts, parse failure, single-photo case).
            all_photo_captions = {}
            choice_idx = _parse_choice(text or "", len(downloaded))
            winner_candidate_idx = downloaded[choice_idx][0]
            winner_url = downloaded[choice_idx][1]
            if photo_descs.get(choice_idx + 1):
                all_photo_captions[1] = photo_descs[choice_idx + 1]

            all_photo_urls = {1: winner_url}
            next_key = 2
            for i, photo in enumerate(candidates):
                if i == winner_candidate_idx:
                    continue
                url = get_photo_web_url(photo)
                if url:
                    all_photo_urls[next_key] = url
                    next_key += 1

    verdict = _parse_verdict(text or "")
    explanation = _parse_explanation(text or "")
    reason = explanation or text  # fall back to full response if EXPLANATION missing
    if truncation_note:
        reason = (reason or "").rstrip() + truncation_note
    # For multi-photo runs where Sonnet described some photos but skipped others,
    # fall back to EXPLANATION for the gaps. Single-photo runs intentionally get
    # no tooltip — the caption would duplicate the reason text shown in the row.
    if explanation and photo_descs:
        for k in all_photo_urls:
            if k not in all_photo_captions:
                all_photo_captions[k] = explanation
    return {"result": verdict, "reason": reason, "photo_urls": all_photo_urls,
            "photo_captions": all_photo_captions}


def _build_validation_prompt(requirement: dict, n_photos: int) -> str:
    """Compose the single-tier prompt wrapped around the requirement's
    validation_prompt. For N=1 we skip the selection step."""
    selection_criteria = requirement.get("selection_criteria") or requirement["title"]
    manufacturer_line = ""
    if requirement.get("_manufacturer"):
        manufacturer_line = f"Job manufacturer: {requirement['_manufacturer']}\n"
    base = (
        f"REQUIREMENT: {requirement['id']} — {requirement['title']}\n"
        f"{manufacturer_line}\n"
        f"{requirement['validation_prompt']}\n\n"
    )
    if n_photos == 1:
        return base + (
            "Work through what you see in the photo, then end your response with "
            "these three lines exactly:\n"
            "  EVIDENCE: 1\n"
            "  VERDICT: PASS   (or FAIL, or NEEDS_REVIEW)\n"
            "  EXPLANATION: <one sentence describing what was actually seen that led "
            "to the verdict. Customer-facing — do NOT reference photo numbers like "
            "'Photo 1'; describe what's physically visible instead.>"
        )
    return base + (
        f"You have {n_photos} candidate photos. Work through this in four steps:\n\n"
        "STEP 1 — Describe each photo briefly (one line each):\n"
        "  Photo 1: <what you see>\n"
        "  Photo 2: <what you see>\n"
        "  ...\n\n"
        "STEP 2 — Pick the photo(s) that best match this selection criteria:\n"
        f"  \"{selection_criteria}\"\n"
        "  If multiple photos are of the same general subject, prefer the one that "
        "matches the specific criteria over a generic shot. State your choice:\n"
        "  CHOICE: <number>\n\n"
        "STEP 3 — For the photo(s) you chose, apply the validation rules from the "
        "REQUIREMENT block above.\n\n"
        "STEP 4 — End your response with these three lines exactly:\n"
        "  EVIDENCE: <comma-separated list of photo numbers you used as evidence — "
        "only photos that directly support your verdict, not every photo you saw>\n"
        "  VERDICT: PASS   (or FAIL, or NEEDS_REVIEW)\n"
        "  EXPLANATION: <one sentence describing what was actually seen that led "
        "to the verdict. Customer-facing — do NOT reference photo numbers like "
        "'Photo 1'; describe what's physically visible instead.>"
    )


def _build_multi_criterion_prompt(requirement: dict, n_photos: int) -> str:
    """Compose a prompt for requirements where multiple criteria must ALL be
    confirmed across a SET of photos (no single winner to pick). The model
    scans across the set and produces CONFIRMED/MISSING/VERDICT lines."""
    criteria = requirement["criteria"]
    criteria_lines = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(criteria))
    intro = requirement.get("validation_prompt", "") or ""
    base = (
        f"REQUIREMENT: {requirement['id']} — {requirement['title']}\n\n"
        f"{intro}\n\n" if intro else f"REQUIREMENT: {requirement['id']} — {requirement['title']}\n\n"
    )

    set_context = (
        f"There is only 1 photo to check." if n_photos == 1
        else f"You have {n_photos} photos. Scan across ALL of them — criteria may be "
             f"confirmed in any photo, not necessarily the same one."
    )

    return (
        base +
        f"{set_context} The following criteria must ALL be confirmed for this requirement to PASS:\n\n"
        f"{criteria_lines}\n\n"
        "STEP 1 — For each criterion, note which photo(s) confirm it (or that none do), "
        "quoting visible UI text / describing specific elements as proof.\n\n"
        "STEP 2 — End your response with these lines exactly:\n"
        "  CONFIRMED: <comma-separated list of criterion numbers confirmed, e.g. 1, 2, 4>\n"
        "  MISSING: <comma-separated list of criterion numbers NOT confirmed, e.g. 3>\n"
        "  VERDICT: PASS (all criteria confirmed) / FAIL (any missing) / NEEDS_REVIEW (genuine ambiguity)\n"
        "  EXPLANATION: <one sentence, customer-facing, listing what was confirmed vs missing. "
        "Do NOT reference photo/screenshot numbers — describe the content instead (e.g. 'the "
        "cellular networking screen', 'the operations settings panel').>"
    )


def _parse_choice(text: str, n_downloaded: int) -> int:
    """Extract the winning photo index from CHOICE: N. Returns 0-based index
    into the `downloaded` list. Defaults to 0 if missing or invalid."""
    m = re.search(r"CHOICE\s*:\s*(?:Photo\s*)?(\d+)", text, re.IGNORECASE)
    if not m:
        return 0
    try:
        idx = int(m.group(1)) - 1
    except ValueError:
        return 0
    if idx < 0 or idx >= n_downloaded:
        return 0
    return idx


def _parse_explanation(text: str) -> str:
    """Extract the customer-facing EXPLANATION line(s) from the response.
    Empty string if no anchor found — caller falls back to full text."""
    m = re.search(r"EXPLANATION\s*:\s*(.+?)(?:\n\n|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def _parse_photo_descriptions(text: str, n_candidates: int) -> dict:
    """Extract per-photo descriptions from Sonnet's STEP 1 output.
    Returns {photo_number: description_string} for every photo described.
    Used to populate hover tooltips on evidence photos in the report."""
    descriptions = {}
    for m in re.finditer(r'\bPhoto\s+(\d+)\s*:\s*(.+)', text, re.IGNORECASE):
        num = int(m.group(1))
        if 1 <= num <= n_candidates:
            descriptions[num] = m.group(2).strip()
    return descriptions


def _parse_evidence(text: str, n_candidates: int) -> list:
    """Extract the EVIDENCE photo numbers from a model response.
    Returns a list of 1-based photo indices (e.g. [1, 3]) that the model
    cited as supporting evidence. Returns [] if the line is absent or
    unparseable — caller falls back to existing winner logic."""
    m = re.search(r"EVIDENCE\s*:\s*([0-9,\s]+)", text, re.IGNORECASE)
    if not m:
        return []
    nums = []
    for part in m.group(1).split(","):
        part = part.strip()
        if part.isdigit():
            n = int(part)
            if 1 <= n <= n_candidates:
                nums.append(n)
    return nums


def _parse_verdict(text: str) -> str:
    """Extract PASS / FAIL / NEEDS_REVIEW from a model response.

    Two strategies, in order:
      1. Anchored verdict: look for the LAST occurrence of "VERDICT: X" in the
         response. Prompts that ask the model to reason first should end with
         this anchor so we aren't fooled by the word "PASS" or "FAIL" appearing
         inside the reasoning text.
      2. First-word heuristic: for legacy prompts that just say
         "Respond: PASS or FAIL, ...", the first non-markdown token is the verdict.
    """
    # Strategy 1: VERDICT: anchor (case-insensitive, accepts dash/underscore variants)
    anchor_matches = re.findall(
        r"\bVERDICT\s*:\s*(PASS|FAIL|NEEDS[_\-\s]?REVIEW|INCONCLUSIVE)\b",
        text, re.IGNORECASE,
    )
    if anchor_matches:
        token = anchor_matches[-1].upper()  # last occurrence wins
        token = re.sub(r"[\s\-]", "_", token)
        if token in ("NEEDS_REVIEW", "INCONCLUSIVE", "NEEDSREVIEW"):
            return "NEEDS_REVIEW"
        return token if token in ("PASS", "FAIL") else "FAIL"

    # Strategy 2: first-word heuristic (legacy prompts)
    cleaned = text.strip().lstrip("*_`").strip()
    first_word = cleaned.split()[0].upper().rstrip(".:,*_") if cleaned.split() else ""
    if first_word in ("NEEDS_REVIEW", "NEEDS-REVIEW", "NEEDSREVIEW", "REVIEW", "INCONCLUSIVE"):
        return "NEEDS_REVIEW"
    if first_word == "PASS":
        return "PASS"
    return "FAIL"


# ── Photo matching ────────────────────────────────────────────────────────────

def find_candidate_photos(requirement: dict, photos: list, checklist_tasks: list) -> list:
    """
    Return all candidate photos for a requirement.
    Strategy (in priority order):
    1. Exact task title match — returns all photos from that task
    2. Keyword match against task titles — returns all photos from first matching task
    3. Keyword match against photo descriptions — returns that single photo
    Returns [] if nothing found.
    """
    task_titles = [t.lower() for t in requirement.get("task_titles", [])]
    keywords = [kw.lower() for kw in requirement.get("keywords", [])]

    # Strategy 1: exact task title match
    for task in checklist_tasks:
        if task.get("title", "").lower().strip() in task_titles:
            task_photos = task.get("photos", [])
            if task_photos:
                return task_photos

    # Strategy 2: keyword match against task titles
    for task in checklist_tasks:
        if any(kw in task.get("title", "").lower() for kw in keywords):
            task_photos = task.get("photos", [])
            if task_photos:
                return task_photos

    # Strategy 3: keyword match in photo description (single result)
    for photo in photos:
        if any(kw in (photo.get("description") or "").lower() for kw in keywords):
            return [photo]

    return []


def get_photo_web_url(photo: dict) -> Optional[str]:
    """Extract the best quality image URL for validation (original > web > thumbnail).

    Checklist task photos: flat {"url": "...", "creator": "...", "uploaded_at": "..."}
    Project-level photos:  {"uris": [{"type": "web", "url": "..."}, ...], "id": "...", ...}
    """
    # Checklist task photo format
    if "url" in photo and "uris" not in photo:
        return photo["url"]
    # Project-level photo format — prefer original for best accuracy
    uris = photo.get("uris", [])
    for uri_type in ["original", "web", "thumbnail"]:
        for uri in uris:
            if uri.get("type") == uri_type:
                return uri.get("url")
    return None


def get_photo_thumbnail_url(photo: dict) -> Optional[str]:
    """Extract thumbnail URL — smaller image for selection tier. Falls back to web URL."""
    if "url" in photo and "uris" not in photo:
        return photo["url"]  # Checklist photos only have one URL
    uris = photo.get("uris", [])
    for uri_type in ["thumbnail", "web"]:
        for uri in uris:
            if uri.get("type") == uri_type:
                return uri.get("url")
    return None


# ── Main compliance check ─────────────────────────────────────────────────────

def run_compliance_check(project_id: str, params: dict, run_vision: bool = True,
                         progress_callback=None, only_ids=None,
                         should_cancel=None, max_workers: int = 2) -> dict:
    """Run a full compliance check.

    `should_cancel`: optional callable returning True when the caller wants
    to abort the run. It is polled before each requirement is dispatched.
    Already-in-flight vision calls cannot be interrupted mid-flight, so
    expect up to one requirement's worth of latency (~5-15s) between
    cancel request and the function returning. The returned report has
    a `cancelled: True` flag when cancellation was honored; results
    array contains only requirements processed before the cancel.

    `max_workers`: how many requirements to vision-check in parallel.
    Default 2 keeps the burst input-tokens-per-minute under Anthropic's
    tier-2 ITPM limit (~80K) while still cutting wall time roughly in
    half versus sequential. We tried 4 and consistently tripped 429s
    once 2-3 long Sonnet calls overlapped — see report 3 logs from
    2026-04-23. Set to 1 for deterministic sequential execution.
    """
    # Load photos. When invoked from the live server (always), the caller
    # is responsible for fetching photos first. When invoked from the CLI
    # the user runs companycam_get_project_photos.py beforehand. We raise
    # FileNotFoundError instead of sys.exit so a server worker thread
    # surfaces it as a normal exception (turned into an ERROR result row
    # by run_check_thread) instead of triggering SystemExit + a 502 cascade
    # from the http.server send_error path.
    photos_path = TMP_DIR / f"photos_{project_id}.json"
    if not photos_path.exists():
        msg = (
            f"{photos_path} not found. "
            f"Run companycam_get_project_photos.py first."
        )
        print(f"ERROR: {msg}", file=sys.stderr)
        raise FileNotFoundError(msg)

    with open(photos_path) as f:
        photos = json.load(f)

    # Load checklist tasks from CompanyCam
    if not COMPANYCAM_API_KEY:
        checklist_tasks = []
        print("WARNING: COMPANYCAM_API_KEY not set — skipping checklist task matching", file=sys.stderr)
    else:
        try:
            headers = {"Authorization": f"Bearer {COMPANYCAM_API_KEY}"}
            resp = requests.get(f"{API_BASE}/projects/{project_id}/checklists", headers=headers)
            resp.raise_for_status()
            checklists = resp.json()

            checklist_tasks = []
            checklist_ids = []
            for cl in checklists:
                checklist_ids.append(cl.get("id"))
                for task in cl.get("sectionless_tasks", []):
                    checklist_tasks.append(task)
                for section in cl.get("sections", []):
                    for task in section.get("tasks", []):
                        checklist_tasks.append(task)
        except Exception as e:
            checklist_tasks = []
            print(f"WARNING: Could not load checklists: {e}", file=sys.stderr)

    # Build a lookup from project-photo URL → thumbnail URL so checklist
    # task photos (which only carry a single full-res URL) can get real
    # thumbnails for the Haiku prefilter. Falls back gracefully: if a task
    # photo URL isn't in the map, get_photo_thumbnail_url returns the
    # full-res URL as before.
    _thumb_by_url: dict = {}
    for _pp in photos:
        _full_url = _pp.get("photo_url") or ""
        if not _full_url:
            continue
        for _uri in _pp.get("uris", []):
            if _uri.get("type") == "thumbnail":
                _thumb_by_url[_full_url] = _uri.get("url")
                break
    # Both task photo URLs and project photo URIs are imgproxy URLs that
    # encode the same S3 source path as base64 after the processing params.
    # Extract that base64 payload as a common key to match them — regardless
    # of whether the sizes differ (rs:fit:4032:4032 vs rs:fit:250:250).
    def _imgproxy_b64_key(url: str) -> str:
        """Extract the base64 source-URL payload from an imgproxy URL.
        All size variants of the same photo share this payload, making it
        a stable key for cross-referencing task photos ↔ project thumbnails."""
        if not url or "img.companycam.com" not in url:
            return ""
        try:
            parts = url.split("/")
            # Structure: https: / '' / img.companycam.com / {sig} / {params...} / {b64...}
            # parts[3] = signature (skip), parts[4+] with ':' = params (skip),
            # remaining parts = base64 payload (join and strip file extension).
            b64_parts = []
            skip_sig = True
            for part in parts[3:]:
                if skip_sig:
                    skip_sig = False
                    continue
                if ":" in part:
                    continue
                if part:
                    b64_parts.append(part.split(".")[0])
            return "".join(b64_parts)
        except Exception:
            return ""

    # Build b64_key → thumbnail_url map from project photos
    _thumb_by_b64: dict = {}
    for _pp in photos:
        thumb_url = next(
            (u["url"] for u in _pp.get("uris", []) if u.get("type") == "thumbnail"),
            None,
        )
        if not thumb_url:
            continue
        for _uri in _pp.get("uris", []):
            key = _imgproxy_b64_key(_uri.get("url", ""))
            if key:
                _thumb_by_b64[key] = thumb_url
                break  # all URIs for same photo share the same b64 payload

    # Enrich task photos: inject a synthetic uris entry so get_photo_thumbnail_url
    # returns the real 250px thumbnail instead of the 4032px original.
    enriched_count = 0
    for _task in checklist_tasks:
        for _tp in _task.get("photos", []):
            if "uris" in _tp:
                continue
            key = _imgproxy_b64_key(_tp.get("url", ""))
            thumb = _thumb_by_b64.get(key) if key else None
            if thumb:
                # Include both thumbnail (for prefilter) and original (for
                # validation) so get_photo_web_url still returns full-res.
                _tp["uris"] = [
                    {"type": "thumbnail", "url": thumb},
                    {"type": "original", "url": _tp["url"]},
                ]
                enriched_count += 1
    if enriched_count:
        print(f"[thumb-enrich] enriched {enriched_count} task photos with real thumbnails",
              file=sys.stderr, flush=True)

    # Determine applicable requirements
    if only_ids:
        total_applicable = len(only_ids)
    else:
        total_applicable = sum(1 for r in REQUIREMENTS if r["condition"](params))

    results = []
    cancelled = False

    # Load DB overrides for mutable requirement fields once, before the
    # main loop. Admins can edit task_titles, keywords, and
    # validation_prompt via the Requirements admin page — those changes
    # should take effect immediately on the next check/recheck without
    # requiring a code deploy. The Python constant provides defaults for
    # anything not overridden in the DB.
    _db_req_overrides: dict = {}
    try:
        from tools.db import fetch_all as _db_fetch
        db_reqs = _db_fetch(
            "SELECT code, task_titles, keywords, validation_prompt "
            "FROM requirements WHERE is_active = TRUE "
            "ORDER BY code, version DESC"
        )
        # Keep only the latest version per code
        seen = set()
        for row in db_reqs:
            code = row["code"]
            if code not in seen:
                seen.add(code)
                _db_req_overrides[code] = {
                    k: v for k, v in row.items()
                    if k != "code" and v is not None
                }
    except Exception as _e:
        print(f"WARNING: could not load DB requirement overrides: {_e}", file=sys.stderr)

    # Phase 1 (serial, fast): walk requirements, emit N/A and MISSING
    # immediately, queue the rest as work for parallel vision checks.
    vision_work = []  # (req, candidates) pairs for run_vision==True
    for _base_req in REQUIREMENTS:
        # Merge DB overrides into the Python constant. DB wins for
        # task_titles, keywords, validation_prompt — the fields an admin
        # can edit. Structural fields (condition, section, etc.) stay
        # from the Python definition since they need code to be correct.
        _override = _db_req_overrides.get(_base_req["id"], {})
        req = {**_base_req, **_override} if _override else _base_req
        applies = req["condition"](params)
        if only_ids and req["id"] not in only_ids:
            continue
        if not applies:
            results.append({
                "id": req["id"],
                "title": req["title"],
                "section": req["section"],
                "status": "N/A",
                "reason": "Not applicable for this job type",
                "optional": req.get("optional", False),
            })
            continue

        candidates = find_candidate_photos(req, photos, checklist_tasks)
        if not candidates:
            manufacturer = (params.get("manufacturer") or "").lower()
            review_manufacturers = [m.lower() for m in req.get("review_if_missing_for", [])]
            if manufacturer in review_manufacturers:
                missing_status = "NEEDS_REVIEW"
                missing_reason = (
                    f"No CT photo found in CompanyCam — on {params.get('manufacturer')} "
                    f"installations this requirement uses manufacturer-specific hardware "
                    f"that requires manual reviewer verification."
                )
            else:
                missing_status = "MISSING"
                missing_reason = "No matching photo found in CompanyCam"
            result_entry = {
                "id": req["id"],
                "title": req["title"],
                "section": req["section"],
                "status": missing_status,
                "reason": missing_reason,
                "optional": req.get("optional", False),
            }
            results.append(result_entry)
            # progress emitted in Phase 2 alongside vision results so the
            # client sees a single consistent stream
            vision_work.append(("__missing__", result_entry))
            continue

        if not run_vision:
            result_entry = {
                "id": req["id"],
                "title": req["title"],
                "section": req["section"],
                "status": "FOUND_NO_VISION",
                "reason": f"{len(candidates)} candidate photo(s) found — vision check skipped",
                "candidates": len(candidates),
                "optional": req.get("optional", False),
            }
            results.append(result_entry)
            vision_work.append(("__skip__", result_entry))
            continue

        # Inject manufacturer so prompts can use it without mutating the
        # shared requirement definition. Critical for E6/E7/S3 (Tesla CTs).
        manufacturer = (params.get("manufacturer") or "").strip()
        req_ctx = dict(req, _manufacturer=manufacturer) if manufacturer else req
        vision_work.append((req_ctx, candidates))

    # Phase 2: parallel execution of vision checks (and emission of the
    # already-decided MISSING / FOUND_NO_VISION results) so progress events
    # arrive in one ordered stream and `checked` counts up cleanly.
    parent_ctx = getattr(_call_ctx, "attrs", None)
    progress_lock = _threading.Lock()
    checked = [0]  # closure-mutable counter

    def _emit(result_entry):
        if not progress_callback:
            return
        with progress_lock:
            checked[0] += 1
            progress_callback(result_entry, checked[0], total_applicable)

    def _worker(req, candidates):
        # Re-bind parent's API-call attribution so api_call_log rows from
        # this worker thread land against the right report_id.
        prior = getattr(_call_ctx, "attrs", None)
        if parent_ctx is not None:
            _call_ctx.attrs = parent_ctx
        import time as _time
        t0 = _time.time()
        try:
            vision_result = check_candidates_with_vision(candidates, req)
            total_ms = int((_time.time() - t0) * 1000)
            # Upgrade FAIL → NEEDS_REVIEW for manufacturer-specific requirements
            # where the correct hardware may not be in the expected checklist task
            # (e.g. Tesla CTs are handled by the Backup Switch, not standard CTs).
            result_status = vision_result["result"]
            _mfr = (req.get("_manufacturer") or "").lower()
            _review_mfrs = [m.lower() for m in req.get("review_if_missing_for", [])]
            if result_status == "FAIL" and _mfr in _review_mfrs:
                result_status = "NEEDS_REVIEW"
            return {
                "id": req["id"],
                "title": req["title"],
                "section": req["section"],
                "status": result_status,
                "reason": vision_result["reason"],
                "candidates": len(candidates),
                "photo_urls": vision_result.get("photo_urls", {}),
                "photo_captions": vision_result.get("photo_captions", {}),
                "optional": req.get("optional", False),
                "total_duration_ms": total_ms,
            }
        finally:
            _call_ctx.attrs = prior

    from concurrent.futures import ThreadPoolExecutor, as_completed, CancelledError

    if vision_work:
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as ex:
            futures = {}
            for marker, payload in vision_work:
                # Honor cancel BEFORE submitting — already-in-flight workers
                # will still run to completion, but we don't queue more.
                if should_cancel and should_cancel():
                    cancelled = True
                    break
                if marker == "__missing__" or marker == "__skip__":
                    # Pre-decided result; fire its progress event in-line
                    # so ordering roughly matches requirement order.
                    _emit(payload)
                    continue
                req = marker
                fut = ex.submit(_worker, req, payload)
                futures[fut] = req

            # As workers finish, emit progress and append to results. Workers
            # may complete out of definition order — that's fine; the report
            # detail page groups by section anyway.
            for fut in as_completed(futures):
                if should_cancel and should_cancel() and not cancelled:
                    cancelled = True
                    # Cancel any not-yet-started futures (in-flight ones run to
                    # completion). Their result() will raise CancelledError.
                    for f in futures:
                        f.cancel()
                try:
                    result_entry = fut.result()
                except CancelledError:
                    continue
                except Exception as e:
                    req = futures[fut]
                    # Log the traceback to stderr so the running server
                    # console (or Railway logs) shows what actually broke,
                    # not just the user-facing reason. Without this, an
                    # ERROR row is opaque after the fact.
                    import traceback
                    print(
                        f"WORKER EXCEPTION on {req['id']}: {e}\n"
                        f"{traceback.format_exc()}",
                        file=sys.stderr, flush=True,
                    )
                    result_entry = {
                        "id": req["id"],
                        "title": req["title"],
                        "section": req["section"],
                        "status": "ERROR",
                        "reason": f"ERROR: {e}",
                        "optional": req.get("optional", False),
                    }
                results.append(result_entry)
                _emit(result_entry)

    return {
        "project_id": project_id,
        "params": params,
        "total_photos": len(photos),
        "checklist_ids": checklist_ids if COMPANYCAM_API_KEY else [],
        "requirements": results,
        "cancelled": cancelled,
    }


def print_report(report: dict):
    print(f"\n{'='*60}")
    print(f"M1 COMPLIANCE REPORT — Project: {report['project_id']}")
    print(f"{'='*60}")
    print(f"Total photos in CompanyCam: {report['total_photos']}")
    print(f"Job parameters: {json.dumps(report['params'], indent=2)}\n")

    sections = {}
    for r in report["requirements"]:
        sec = r["section"]
        sections.setdefault(sec, []).append(r)

    total_required = sum(1 for r in report["requirements"] if r["status"] != "N/A" and not r.get("optional"))
    total_pass = sum(1 for r in report["requirements"] if r["status"] == "PASS")
    total_fail = sum(1 for r in report["requirements"] if r["status"] in ("FAIL", "MISSING", "ERROR"))

    print(f"SUMMARY: {total_pass} passed / {total_fail} issues / {total_required} required\n")

    for section, reqs in sections.items():
        relevant = [r for r in reqs if r["status"] != "N/A"]
        if not relevant:
            continue
        print(f"\n── {section.upper()} ──")
        for r in relevant:
            icon = {"PASS": "✓", "FAIL": "✗", "MISSING": "!", "ERROR": "?", "FOUND_NO_VISION": "~"}.get(r["status"], " ")
            optional_tag = " [optional]" if r.get("optional") else ""
            print(f"  [{icon}] {r['id']}: {r['title']}{optional_tag}")
            if r["status"] != "PASS":
                print(f"       → {r['reason']}")
                if r.get("photo_url"):
                    print(f"       → Photo: {r['photo_url']}")


def parse_bool(val: str) -> bool:
    return val.lower() in ("true", "1", "yes")


def main():
    parser = argparse.ArgumentParser(description="Run Palmetto M1 compliance check")
    parser.add_argument("--project_id", required=True)
    parser.add_argument("--manufacturer", required=True, choices=["SolarEdge", "Tesla", "Enphase"])
    parser.add_argument("--has_battery", required=True)
    parser.add_argument("--is_backup_battery", default="false")
    parser.add_argument("--is_incentive_state", default="false")
    parser.add_argument("--portal_access_granted", default="false")
    parser.add_argument("--skip_vision", action="store_true", help="Skip Claude Vision API calls")
    args = parser.parse_args()

    params = {
        "manufacturer": args.manufacturer,
        "lender": "LightReach",
        "has_battery": parse_bool(args.has_battery),
        "is_backup_battery": parse_bool(args.is_backup_battery),
        "is_incentive_state": parse_bool(args.is_incentive_state),
        "portal_access_granted": parse_bool(args.portal_access_granted),
    }

    # Always show cost estimate before running vision checks
    if not args.skip_vision:
        print_cost_estimate(params)

    report = run_compliance_check(args.project_id, params, run_vision=not args.skip_vision)

    # Save report
    TMP_DIR.mkdir(exist_ok=True)
    output_path = TMP_DIR / f"compliance_{args.project_id}.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {output_path}", file=sys.stderr)

    print_report(report)


if __name__ == "__main__":
    main()
