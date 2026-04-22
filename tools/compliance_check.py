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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "\n\nRespond: PASS or FAIL, then one sentence explaining what you see."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "\n\nRespond: PASS or FAIL, then one sentence that either quotes the "
            "characters you read, or explains why you cannot read any."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
        ),
    },
    {
        "id": "R4",
        "section": "Roof",
        "title": "Under-Array Wire Management (per array)",
        "condition": always,
        "task_titles": ["Wire Management / Under Array"],
        "keywords": ["wire management / under array", "under array", "wire management"],
        "validation_prompt": (
            "This photo should show wire management under the solar array after panels are installed. "
            "Verify: (1) Are wires NOT touching the roof surface? (2) Are wires secured/bundled above the surface? "
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why. "
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
        "validation_prompt": (
            "This photo should show an open rooftop junction box with completed wiring and bonding. "
            "Verify: (1) Is the junction box open and wiring visible? (2) Are conductors terminated properly? "
            "(3) Is there no more than 2 inches of exposed conductors outside the array (more requires conduit)? "
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why. "
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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
            "This screenshot should show Tesla system commissioning confirming: LightReach added as partner, "
            "inverter & CTs enabled, networking connected to Cellular, and operations settings "
            "with panel current limit & PCS settings. "
            "Verify which of these four items are visible. "
            "Respond: PASS if all four are shown, FAIL if any are missing, then list what is confirmed vs. missing."
        ),
    },
    {
        "id": "SC2",
        "section": "Commissioning",
        "title": "SolarEdge Commissioning Screenshots",
        "condition": if_solaredge,
        "task_titles": ["Monitoring App Screenshots"],
        "keywords": ["monitoring app screenshots", "commissioning", "backup reserve", "storm guard", "SolarEdge"],
        "validation_prompt": (
            "This screenshot should show SolarEdge system commissioning confirming: "
            "20% minimum backup reserve set, and Storm Guard enabled. "
            "Verify: (1) Is backup reserve visible and set to 20% or more? (2) Is Storm Guard enabled? "
            "Respond: PASS if both are confirmed, FAIL if either is missing, then explain."
        ),
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
            "Respond: PASS or FAIL, then one sentence explaining why."
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


def _call_anthropic(payload: dict, req_id: str) -> Optional[str]:
    """Make an Anthropic API call with up to 3 retries on 429. Returns response text or None."""
    import time
    for attempt in range(3):
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=ANTHROPIC_HEADERS,
                timeout=60,
            )
            if resp.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"  Rate limited on {req_id}, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
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


def check_candidates_with_vision(candidates: list, requirement: dict) -> dict:
    """
    Two-tier vision check for maximum accuracy:

    Tier 1 (selection): Send ALL candidate thumbnails to Haiku. Ask which photo
    best represents the requirement. Thumbnails are small (~400 tokens each),
    so even 15 photos is cheap.

    Tier 2 (validation): Download the full-res winner and validate it against
    the requirement's validation prompt.

    Cost: ~2 Haiku calls per requirement. Tier 1 is cheap (thumbnails),
    Tier 2 is one full image. Total similar to old single-pass with 5 photos,
    but evaluates ALL candidates.
    """
    if not ANTHROPIC_API_KEY:
        return {"result": "SKIP", "reason": "ANTHROPIC_API_KEY not set"}

    import concurrent.futures

    # ── Tier 1: Selection — download ALL thumbnails and pick the best ─────

    thumb_urls = []
    for photo in candidates:
        url = get_photo_thumbnail_url(photo)
        if url:
            thumb_urls.append(url)

    if not thumb_urls:
        return {"result": "ERROR", "reason": "No photo URLs found", "photo_urls": {}}

    # If only 1 candidate, skip selection tier
    if len(thumb_urls) == 1:
        best_idx = 0
    else:
        # Download all thumbnails in parallel
        thumb_downloaded = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(thumb_urls))) as executor:
            future_to_url = {executor.submit(_download_image, url): url for url in thumb_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        thumb_downloaded[url] = result
                except Exception:
                    pass

        # Build thumbnail image blocks
        thumb_blocks = []
        valid_indices = []
        for i, url in enumerate(thumb_urls):
            if url in thumb_downloaded:
                data, media_type = thumb_downloaded[url]
                thumb_blocks.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
                thumb_blocks.append({"type": "text", "text": f"[Photo {i + 1}]"})
                valid_indices.append(i)

        if not thumb_blocks:
            return {"result": "ERROR", "reason": "Could not download any candidate photos", "photo_urls": {}}

        # Ask Haiku to pick the best photo
        selection_payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 5,
            "messages": [{"role": "user", "content": thumb_blocks + [{"type": "text", "text": (
                f"These are {len(valid_indices)} photos from a solar installation checklist task.\n"
                f"Requirement: {requirement['title']}\n"
                f"Which photo number (1-{len(thumb_urls)}) best shows this requirement? Reply with only the number."
            )}]}],
        }

        selection_text = _call_anthropic(selection_payload, requirement["id"] + "-select")
        try:
            best_idx = int("".join(c for c in (selection_text or "1") if c.isdigit())) - 1
            if best_idx < 0 or best_idx >= len(candidates):
                best_idx = 0
        except (ValueError, TypeError):
            best_idx = 0

    # ── Tier 2: Validation — download full-res winner and validate ────────

    best_photo = candidates[best_idx]
    full_url = get_photo_web_url(best_photo)
    if not full_url:
        return {"result": "ERROR", "reason": "Could not get URL for selected photo", "photo_urls": {}}

    full_result = _download_image(full_url)
    if not full_result:
        return {"result": "ERROR", "reason": "Could not download selected photo", "photo_urls": {}}

    data, media_type = full_result
    photo_urls = {1: full_url}

    # Also include URLs of all candidates for reference in the report
    all_photo_urls = {}
    for i, photo in enumerate(candidates):
        url = get_photo_web_url(photo)
        if url:
            all_photo_urls[i + 1] = url

    prompt = (
        f"Requirement {requirement['id']}: {requirement['title']}\n\n"
        f"{requirement['validation_prompt']}\n\n"
        "IMPORTANT: Your response MUST start with exactly 'PASS' or 'FAIL' on the first line "
        "(no asterisks, headers, or other text before it), followed by one sentence explaining why."
    )

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 150,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
            {"type": "text", "text": prompt},
        ]}],
    }

    text = _call_anthropic(payload, requirement["id"])
    if text and text.startswith("ERROR"):
        return {"result": "ERROR", "reason": text, "photo_urls": all_photo_urls}

    first_word = (text or "").strip().split()[0].upper().rstrip(".:,")
    passed = first_word == "PASS"
    return {"result": "PASS" if passed else "FAIL", "reason": text, "photo_urls": all_photo_urls}


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

def run_compliance_check(project_id: str, params: dict, run_vision: bool = True, progress_callback=None, only_ids=None) -> dict:
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
    for req in REQUIREMENTS:
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
