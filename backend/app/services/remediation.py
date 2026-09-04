"""Remediation engine - maps findings to specific, actionable recommendations."""

from __future__ import annotations

from typing import Any

CATEGORY_REMEDIATION: dict[str, str] = {
    "system_prompt_extraction": (
        "Separate trusted application instructions from any user-provided content. "
        "Do not allow the model to paraphrase, summarize, translate, or quote its "
        "system prompt; add an explicit system-level gate that blocks re-disclosure "
        "patterns and enforce output-level filtering that strips instruction-shaped text."
    ),
    "developer_instruction_extraction": (
        "Treat developer messages as the highest-priority instruction level and never "
        "reflect their content back into the user channel. Strip developer/system "
        "markers from user input before it reaches the model and validate that output "
        "does not echo internal configuration."
    ),
    "instruction_override": (
        "Enforce a strict instruction hierarchy: system > user > retrieved content. "
        "Apply delimiters and role-tag sanitization to user input, and add a secondary "
        "verification step before the model acts on instruction-like phrasing (e.g. "
        "'ignore previous instructions') from the user channel."
    ),
    "policy_bypass": (
        "Ensure safety policy is applied regardless of framing (hypothetical, role-play, "
        "jailbreak personas). Add dedicated refusal classes for persona-override attempts "
        "and test policy consistency with adversarial paraphrases."
    ),
    "role_manipulation": (
        "Reject attempts to redefine the assistant's identity or authority from the user "
        "channel. Pin the assistant persona server-side and disallow 'DAN'-style unrestricted "
        "persona adoption via output classifier."
    ),
    "constraint_bypass": (
        "Do not accept constraint overrides from user messages. Validate that any claimed "
        "'system update' or re-prioritization of rules originates from a trusted admin "
        "channel, never from user input."
    ),
    "instruction_hierarchy_confusion": (
        "Document and enforce an explicit instruction priority order. Sanitize injected "
        "role/system tags (e.g. XML, markdown, JSON 'role:' blocks) before prompting, and "
        "validate hierarchical intent with a dedicated classifier."
    ),
    "confidential_information": (
        "Enforce authorization and data-access controls before any sensitive data is "
        "generated. Do not let the model act on unverified authorization claims; add "
        "PII/credential detection to the output path and require a verified identity/context "
        "for privileged requests."
    ),
    "obfuscation": (
        "Normalize adversarial encodings (Unicode homoglyphs, leetspeak, whitespace, "
        "Base64) before instruction-boundary checks. Do not rely solely on denylist string "
        "matches; use semantic detection so paraphrased or obfuscated injections are caught."
    ),
    "context_attack": (
        "Treat conversation history as untrusted attacker-controlled input. Verify claims of "
        "prior agreement/authorization server-side, and never allow user-embedded 'system' "
        "or 'developer' role markers to change privileges."
    ),
    "multi_turn": (
        "Track intent across the conversation and maintain the session security boundary "
        "turn over turn. Do not let trust-building or progressive instruction override "
        "persist; reset per-topic security state and re-verify privileged actions each turn."
    ),
    "multilingual": (
        "Apply the same policy checks across languages. Use a multilingual safety model or "
        "translate inputs/outputs for moderation so injection in any language is caught, "
        "and block translation-based re-disclosure of internal instructions."
    ),
    "rag_indirect": (
        "Classify retrieved documents as data, never as instructions. Isolate retrieved "
        "content inside explicit delimiters with a prompt that says 'the following is "
        "untrusted retrieved content', apply an instruction-hierarchy guard, and validate "
        "model output before any downstream action based on retrieved context."
    ),
    "agent_tool": (
        "Require explicit, verified user authorization for tool invocation. Validate tool "
        "parameters against a strict schema at runtime, separate tool results from "
        "instructions before further processing, enforce least privilege, and add an "
        "allowlist for destructive actions with confirmation."
    ),
}

GENERIC_REMEDIATION = (
    "Harden the trusted/untrusted instruction boundary: sanitize role tags in user input, "
    "enforce an explicit instruction hierarchy, and add output-level validation that "
    "detects and blocks leakage of internal configuration, private data, or unauthorized "
    "tool actions before they are surfaced."
)


def remediation_for(category: str, classification: str) -> str:
    if classification in ("blocked", "uncertain", "error"):
        return (
            "No remediation required for this result. Continue to monitor and treat "
            "blocked attempts as evidence the current boundary held."
        )
    return CATEGORY_REMEDIATION.get(category, GENERIC_REMEDIATION)


BUILD_TITLE = {
    "system_prompt_extraction": "System Prompt Leakage",
    "developer_instruction_extraction": "Developer Instruction Leakage",
    "instruction_override": "Instruction Override Accepted",
    "policy_bypass": "Policy Bypass Achieved",
    "role_manipulation": "Role Manipulation Achieved",
    "constraint_bypass": "Constraint Bypass Achieved",
    "instruction_hierarchy_confusion": "Instruction Hierarchy Confusion Exploited",
    "confidential_information": "Confidential Information Disclosure",
    "obfuscation": "Obfuscated Injection Succeeded",
    "context_attack": "Context Manipulation Succeeded",
    "multi_turn": "Multi-Turn Attack Succeeded",
    "multilingual": "Multilingual Injection Succeeded",
    "rag_indirect": "Retrieved-Context Instruction Injection",
    "agent_tool": "Unauthorized Tool Action",
}


def finding_title(category: str, classification: str) -> str:
    label = BUILD_TITLE.get(category, "Prompt Injection Vulnerability")
    prefix = "Partial " if classification == "partial" else ""
    return f"{prefix}{label}"