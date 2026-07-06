"""Classical Chinese Parallage profile specifications."""

from __future__ import annotations

BASE_INSTRUCTIONS = """You are translating Classical Chinese into English for the Parallage project.
Translate only the supplied source passage. No recogniser or external guidance pass is available.
Preserve uncertainty visibly instead of hiding it. Do not invent historical context, source citation,
or named entities not present in the supplied text."""


def prompt(body: str) -> str:
    return f"{BASE_INSTRUCTIONS}\n\n{body.strip()}"


PROFILE_SPECS: list[dict[str, object]] = [
    {
        "name": "classical_chinese_focal_scholarly",
        "label": "Focal Scholarly Translation",
        "style_kind": "focal",
        "description": "Main review translation: clear scholarly English without helper apparatus.",
        "priority": 1,
        "is_focal": True,
        "prompt_text": prompt(
            """Produce one clear scholarly English translation. Keep the source's compression where it matters,
            but make the argument readable. Do not add commentary, a glossary, or a table."""
        ),
    },
    {
        "name": "parallage_01_diplomatic_literal",
        "label": "Diplomatic Literal",
        "style_kind": "literal",
        "description": "Structure-mirroring literal translation.",
        "priority": 4,
        "prompt_text": prompt("Translate as literally as English allows. Preserve word order and clause order. Do not smooth."),
    },
    {
        "name": "parallage_02_interlinear_gloss",
        "label": "Interlinear Gloss",
        "style_kind": "analysis",
        "description": "Token-aligned gloss table and aligned gloss translation.",
        "priority": 4,
        "prompt_text": prompt(
            "Output a table: character or short phrase | function | gloss | notes. Then provide an aligned gloss translation."
        ),
    },
    {
        "name": "parallage_03_syntax_scaffold",
        "label": "Syntax Scaffold",
        "style_kind": "analysis",
        "description": "Bracketed syntax scaffold with translation support.",
        "priority": 4,
        "prompt_text": prompt("Preserve subordinate and parallel structure with brackets. Add a short syntax map at the end."),
    },
    {
        "name": "parallage_04_minimal_inference",
        "label": "Minimal Inference",
        "style_kind": "literal",
        "description": "Conservative translation marking unavoidable inference.",
        "priority": 4,
        "prompt_text": prompt("Do not add implied details. If inference is unavoidable, mark it with [INFERENCE]. Preserve vagueness."),
    },
    {
        "name": "parallage_05_scholarly_readable",
        "label": "Scholarly Readable",
        "style_kind": "readable",
        "description": "Commentary-grade academic English with glossary.",
        "priority": 4,
        "prompt_text": prompt("Produce clear academic English, translate idioms cautiously, keep terminology consistent, and add a short glossary."),
    },
    {
        "name": "parallage_06_smooth_idiomatic",
        "label": "Smooth Idiomatic",
        "style_kind": "readable",
        "description": "Natural modern English preserving meaning.",
        "priority": 4,
        "prompt_text": prompt("Make it natural modern English while preserving meaning. Keep conceptual slots stable."),
    },
    {
        "name": "parallage_07_message_paraphrase",
        "label": "Message Paraphrase",
        "style_kind": "paraphrase",
        "description": "Conceptual paraphrase with anchor notes.",
        "priority": 4,
        "prompt_text": prompt("Paraphrase ideas into contemporary English. Add 6-10 anchor notes mapping source phrases to paraphrase choices."),
    },
    {
        "name": "parallage_08_controlled_english",
        "label": "Controlled English",
        "style_kind": "readable",
        "description": "Machine-friendly controlled English.",
        "priority": 4,
        "prompt_text": prompt("Use one claim per sentence. Avoid pronouns where possible. Make uncertainty explicit. Do not use metaphors."),
    },
    {
        "name": "parallage_09_analyst_brief",
        "label": "Analyst Brief",
        "style_kind": "analysis",
        "description": "Brief identifying core claims and risks.",
        "priority": 4,
        "prompt_text": prompt("Write 3-5 bullet points: main claim, agency, causal relation, uncertainty, and interpretive risk."),
    },
    {
        "name": "parallage_10_plain_language",
        "label": "Plain Language",
        "style_kind": "pedagogical",
        "description": "School-level plain-language translation.",
        "priority": 4,
        "prompt_text": prompt("Use Year 10 readability, short sentences, minimal jargon, and parenthetical glosses for cultural terms."),
    },
    {
        "name": "parallage_11_learners_translation",
        "label": "Learner's Translation",
        "style_kind": "pedagogical",
        "description": "Teaching translation with grammar notes and vocabulary.",
        "priority": 4,
        "prompt_text": prompt("Give a close translation, 8-12 grammar notes, and a mini vocabulary list of key characters or compounds."),
    },
    {
        "name": "parallage_12_named_entity_explicit",
        "label": "Named Entity Explicit",
        "style_kind": "analysis",
        "description": "Translation plus explicit entity and concept list.",
        "priority": 4,
        "prompt_text": prompt("Translate, then list all named entities and abstract concepts with roles and confidence."),
    },
    {
        "name": "parallage_13_forked_lattice",
        "label": "Forked Lattice",
        "style_kind": "analysis",
        "description": "Alternative readings and coherent full translations.",
        "priority": 4,
        "prompt_text": prompt("Identify ambiguous spans, give 2-3 alternatives for each, then provide 2-3 coherent full translations labelled A/B/C."),
    },
    {
        "name": "parallage_14_uncertainty_annotated",
        "label": "Uncertainty Annotated",
        "style_kind": "analysis",
        "description": "Confidence-scored translation with risk phrases.",
        "priority": 4,
        "prompt_text": prompt("For each sentence, give confidence 0-100 with reasons. List the top 5 risk phrases with alternatives."),
    },
    {
        "name": "parallage_15_decision_log",
        "label": "Decision Log",
        "style_kind": "analysis",
        "description": "Apparatus-first translation decisions.",
        "priority": 4,
        "prompt_text": prompt("List decision points, alternatives, justification, and then a final translation."),
    },
    {
        "name": "parallage_16_adversarial_red_team",
        "label": "Adversarial Red Team",
        "style_kind": "analysis",
        "description": "Sceptical alternative translation and divergence notes.",
        "priority": 4,
        "prompt_text": prompt("Produce a deliberately sceptical alternative translation. Highlight where it diverges and why."),
    },
    {
        "name": "parallage_17_back_translation_audit",
        "label": "Back Translation Audit",
        "style_kind": "analysis",
        "description": "Translation plus back-translation audit.",
        "priority": 4,
        "prompt_text": prompt("Translate to English, then back-translate into a Classical-Chinese-like literal gloss. List mismatches indicating drift."),
    },
    {
        "name": "parallage_audit_pack",
        "label": "Audit Pack",
        "style_kind": "analysis",
        "description": "Single-call reliability pack.",
        "priority": 4,
        "prompt_text": prompt("Produce: translation, uncertainty notes, red-team alternative, and back-translation audit."),
    },
    {
        "name": "parallage_compact_literal",
        "label": "Compact Literal",
        "style_kind": "literal",
        "description": "Compact dictionary-style literal translation.",
        "priority": 4,
        "prompt_text": prompt("Translate into compact, fairly literal English. Use short, telegraphic sentences close to source order."),
    },
    {
        "name": "parallage_idiomatic_reader",
        "label": "Idiomatic Reader",
        "style_kind": "readable",
        "description": "Educated-reader prose translation.",
        "priority": 4,
        "prompt_text": prompt("Translate into clear, idiomatic English for an educated reader. Clarify elliptical links only when necessary."),
    },
    {
        "name": "parallage_lattice_pack",
        "label": "Lattice Pack",
        "style_kind": "analysis",
        "description": "Ambiguity lattice with full translations.",
        "priority": 4,
        "prompt_text": prompt("Build an ambiguity lattice, then give multiple coherent full translations that make different defensible choices."),
    },
    {
        "name": "parallage_scholarly_edition",
        "label": "Scholarly Edition",
        "style_kind": "readable",
        "description": "Scholarly-edition prose translation.",
        "priority": 4,
        "prompt_text": prompt("Translate into scholarly-edition English with light explanatory clarification. Do not invent citations."),
    },
    {
        "name": "parallage_spectrum_pack",
        "label": "Spectrum Pack",
        "style_kind": "analysis",
        "description": "Contrasted register spectrum.",
        "priority": 4,
        "prompt_text": prompt("Produce sharply contrasted versions: literal, scholarly, plain-language, sceptical, and uncertainty-marked."),
    },
    {
        "name": "parallage_18_mnemonic_translation",
        "label": "Mnemonic Translation",
        "style_kind": "creative",
        "description": "Memorable rendering with factual anchors.",
        "priority": 5,
        "prompt_text": prompt("Create a memorable rendering with vivid but non-anachronistic phrasing. Include a factual anchors box."),
    },
    {
        "name": "parallage_19_alliterative_mnemonic",
        "label": "Alliterative Mnemonic",
        "style_kind": "creative",
        "description": "Rhythmic alliterative memory version.",
        "priority": 5,
        "prompt_text": prompt("Produce a rhythmic, alliterative version that preserves facts. Include a factual anchors box."),
    },
    {
        "name": "parallage_20_rhyming_poetry",
        "label": "Rhyming Poetry",
        "style_kind": "creative",
        "description": "Short poetic rendering.",
        "priority": 5,
        "prompt_text": prompt("Write a short rhyming poem or stanza that accurately conveys the passage. Label it explicitly as poetic."),
    },
    {
        "name": "parallage_memory_pack",
        "label": "Memory Pack",
        "style_kind": "creative",
        "description": "Non-critical memory pack.",
        "priority": 5,
        "prompt_text": prompt("Produce a mnemonic rendering, an alliterative version, and a short rhyme. Mark all as memory aids, not critical translations."),
    },
]


def helper_profile_names(max_priority: int | None = None) -> list[str]:
    names: list[str] = []
    for spec in PROFILE_SPECS:
        if spec.get("is_focal"):
            continue
        if max_priority is not None and int(spec["priority"]) > max_priority:
            continue
        names.append(str(spec["name"]))
    return names
