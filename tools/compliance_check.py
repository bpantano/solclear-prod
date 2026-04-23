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
        "validation_prompt": (
            "This photo should show a close-up of a roof attachment point with flashing and/or sealant. "
            "Verify: (1) Is a roof attachment point visible? (2) Is flashing or sealant present? "
            "PASS if the photo documents the attachment point with flashing or sealant visible. "
            "Do not judge installation quality — only verify the photo shows what is required. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "R2",
        "section": "Roof",
        "title": "Rail + EGC + Wire Management (per array)",
        "condition": always,
        "task_titles": ["Racking Assembly + Grounding"],
        "keywords": ["racking assembly", "grounding", "rail", "EGC", "wire management", "clips"],
        "validation_prompt": (
            "This photo should show the racking assembly area including rail, attachments, and wire management. "
            "Verify: (1) Is racking/rail visible? (2) Is wire management visible (clips, secured wires)? "
            "PASS if the photo shows the racking area with wire management present. "
            "A grounding conductor may not be clearly distinguishable at photo resolution — do not fail solely for that. "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
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
        "validation_prompt": (
            "This photo should show the production meter or production current transformers (CTs). "
            "Verify: (1) Is a production meter or CT visible? (2) For Enphase: is L1 wiring from branch circuits "
            "passing through the production CT visible? Are CT terminal lugs with correct phase landing visible? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
        ),
    },
    {
        "id": "E7",
        "section": "Electrical",
        "title": "Consumption Metering (CTs)",
        "condition": always,
        "task_titles": ["CT Installation"],
        "keywords": ["CT installation", "consumption CT", "service feeder", "CT direction"],
        "validation_prompt": (
            "This photo should show consumption monitoring CTs on service feeders. "
            "Verify: (1) Are CTs visible on service feeders? (2) Is the CT direction/orientation visible? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
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
        "validation_prompt": (
            "This photo should show the battery CT with its location and direction visible. "
            "Verify: (1) Is the CT visible? (2) Is the CT direction/orientation discernible? "
            "Work through what you see, then end your response with a final line: VERDICT: PASS or VERDICT: FAIL."
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


def _call_anthropic(payload: dict, req_id: str) -> Optional[str]:
    """Make an Anthropic API call with up to 3 retries on 429.
    Returns response text or None. Logs usage to api_call_log when a
    report context is active (see set_call_context)."""
    import time
    for attempt in range(3):
        try:
            t0 = time.time()
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=ANTHROPIC_HEADERS,
                timeout=60,
            )
            duration_ms = int((time.time() - t0) * 1000)
            if resp.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"  Rate limited on {req_id}, retrying in {wait}s...", file=sys.stderr)
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
        except Exception as e:
            if attempt == 2:
                return f"ERROR: {e}"
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


VISION_MODEL = "claude-sonnet-4-6"


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

    # Download all candidates (full-res). Skip any that fail — the model can
    # still reason about the ones that succeeded. Photos keep their original
    # task-list order for consistency with what the CompanyCam API returns.
    downloaded = []  # list of (candidate_idx, url, data, media_type)
    for i, photo in enumerate(candidates):
        url = get_photo_web_url(photo)
        if not url:
            continue
        result = _download_image(url)
        if result is None:
            continue
        data, media_type = result
        downloaded.append((i, url, data, media_type))

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
    dynamic_max_tokens = min(450 + 60 * len(downloaded), 1200)
    payload = {
        "model": VISION_MODEL,
        "max_tokens": dynamic_max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    text = _call_anthropic(payload, requirement["id"])
    if text and text.startswith("ERROR"):
        # Best-effort photo_urls even on error — default to task order.
        all_photo_urls = {i + 1: get_photo_web_url(p) for i, p in enumerate(candidates) if get_photo_web_url(p)}
        return {"result": "ERROR", "reason": text, "photo_urls": all_photo_urls}

    # In multi-criterion mode there's no single winner — every photo is
    # part of the evidence set. Keep task-order indexing so photo_urls[1] is
    # just "first screenshot" (a stable, predictable reference).
    if requirement.get("criteria"):
        all_photo_urls = {}
        for i, photo in enumerate(candidates):
            url = get_photo_web_url(photo)
            if url:
                all_photo_urls[i + 1] = url
    else:
        # Single-winner-pick mode: rotate photo_urls so winner is at key 1.
        choice_idx = _parse_choice(text or "", len(downloaded))
        winner_candidate_idx = downloaded[choice_idx][0]
        winner_url = downloaded[choice_idx][1]

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
    return {"result": verdict, "reason": reason, "photo_urls": all_photo_urls}


def _build_validation_prompt(requirement: dict, n_photos: int) -> str:
    """Compose the single-tier prompt wrapped around the requirement's
    validation_prompt. For N=1 we skip the selection step."""
    selection_criteria = requirement.get("selection_criteria") or requirement["title"]
    base = (
        f"REQUIREMENT: {requirement['id']} — {requirement['title']}\n\n"
        f"{requirement['validation_prompt']}\n\n"
    )
    if n_photos == 1:
        return base + (
            "Work through what you see in the photo, then end your response with "
            "these two lines exactly:\n"
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
        "STEP 2 — Pick the photo that best matches this selection criteria:\n"
        f"  \"{selection_criteria}\"\n"
        "  If multiple photos are of the same general subject, prefer the one that "
        "matches the specific criteria over a generic shot. State your choice:\n"
        "  CHOICE: <number>\n\n"
        "STEP 3 — For the photo you chose, apply the validation rules from the "
        "REQUIREMENT block above.\n\n"
        "STEP 4 — End your response with these two lines exactly:\n"
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
                         should_cancel=None) -> dict:
    """Run a full compliance check.

    `should_cancel`: optional callable returning True when the caller wants
    to abort the run. It is polled at each requirement boundary — the
    currently-executing vision call cannot be interrupted mid-flight, so
    expect up to one requirement's worth of latency (~5-15s) between
    cancel request and the function returning. The returned report has
    a `cancelled: True` flag when cancellation was honored; results
    array contains only requirements processed before the cancel.
    """
    # Load photos
    photos_path = TMP_DIR / f"photos_{project_id}.json"
    if not photos_path.exists():
        print(f"ERROR: {photos_path} not found. Run companycam_get_project_photos.py first.", file=sys.stderr)
        sys.exit(1)

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

    # Determine applicable requirements
    if only_ids:
        total_applicable = len(only_ids)
    else:
        total_applicable = sum(1 for r in REQUIREMENTS if r["condition"](params))
    results = []
    checked = 0
    cancelled = False
    for req in REQUIREMENTS:
        # Cooperative cancellation check — poll before starting each
        # requirement. The in-flight vision call (if any) already
        # completed; we stop here without launching the next one.
        if should_cancel and should_cancel():
            cancelled = True
            break
        applies = req["condition"](params)

        # If only_ids specified, skip requirements not in the set
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

        checked += 1

        if not candidates:
            result_entry = {
                "id": req["id"],
                "title": req["title"],
                "section": req["section"],
                "status": "MISSING",
                "reason": "No matching photo found in CompanyCam",
                "optional": req.get("optional", False),
            }
            results.append(result_entry)
            if progress_callback:
                progress_callback(result_entry, checked, total_applicable)
            continue

        if run_vision:
            # Single-pass: send all candidates, Haiku selects best and validates in one call
            import time; time.sleep(1)  # ~19 calls/run — stay well under 240/min limit
            vision_result = check_candidates_with_vision(candidates, req)
            result_entry = {
                "id": req["id"],
                "title": req["title"],
                "section": req["section"],
                "status": vision_result["result"],
                "reason": vision_result["reason"],
                "candidates": len(candidates),
                "photo_urls": vision_result.get("photo_urls", {}),
                "optional": req.get("optional", False),
            }
            results.append(result_entry)
            if progress_callback:
                progress_callback(result_entry, checked, total_applicable)
        else:
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
            if progress_callback:
                progress_callback(result_entry, checked, total_applicable)

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
