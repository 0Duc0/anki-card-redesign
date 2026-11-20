"""Field names: the code uses the original ("canonical") names; the user renamed fields on 2026-11-19.

`resolve(model, lang)` returns {canonical: actual} for every canonical field that is missing from the note type
but present under its new name. Old collections resolve to {} and work unchanged.
"""

from __future__ import annotations

import re

# canonical name -> name in the user's collection (backup 2026-11-19 15:49)
LIVE = {
    "cn": {
        "EntryKey": "EntryID", "ScriptDiff": "ScriptsDiffer", "PinyinMarked": "Pinyin",
        "PinyinNumbers": "PinyinNumbered", "DefinitionsHTML": "Senses", "MeaningPromptHTML": "ProductionPrompt",
        "AmbiguityHintS2T": "TraditionalDisambiguation", "AmbiguityHintT2S": "SimplifiedDisambiguation",
        "ClassifiersHTML": "Classifiers", "NotesHTML": "PronunciationNotes", "HSK": "HSKLevel", "POS": "PartOfSpeech",
        "MetadataHTML": "Metadata", "UserMnemonic": "Mnemonic", "ExampleSentence": "Examples",
        "ExampleTranslation": "ExampleSources", "RareUnicodeHTML": "RareUnicode", "LookupHTML": "ExternalLookups",
        "HumanAudio": "Audio", "HumanAudioSourceHTML": "AudioCredit", "AlternativeHumanAudioHTML": "AudioAlternatives",
        "RecognitionHintHTML": "ProductionHint", "Notizen": "PersonalNotes", "OrthographyHTML": "Orthography",
    },
    "jp": {
        "Word": "Headword (JP)", "MainMeaning": "Gloss", "MainSenses": "Senses", "OtherMeanings": "AdditionalSenses",
        "AllDefinitions": "DictionaryEntry", "PartOfSpeech": "PartOfSpeechDetailed", "ExampleJP": "Examples",
        "ExampleEN": "ExampleTranslations", "OtherForms": "Orthography", "WordType": "PartOfSpeech",
        "Source": "Sources", "AudioText": "Audio", "RecognitionAlternativesHTML": "Homographs",
    },
    "vn": {
        "Vietnamese": "Headword (VN)", "English": "Gloss", "Tier": "FrequencyBand", "Frequency": "FrequencyInfo",
        "ExampleVietnamese": "Examples", "ExampleEnglish": "ExampleTranslations", "ExampleSource": "ExampleSources",
        "DetailsHTML": "DictionaryEntry", "HumanAudioPrimaryHTML": "Audio",
        "HumanAudioAlternativesHTML": "AudioAlternatives", "SourcesHTML": "Sources", "OriginalGUID": "EntryID",
        "RecognitionHintHTML": "ProductionHint", "Notizen": "PersonalNotes",
        "RecognitionAlternativesHTML": "ContextHint",
    },
}


def resolve(model: dict, lang: str) -> dict[str, str]:
    names = {f["name"] for f in model["flds"]}
    out = {}
    for canon, new in LIVE[lang].items():
        if canon in names and canon not in LIVE[lang].values():
            continue                       # still the old name (old collection / tests)
        if new in names:
            out[canon] = new
    # a collection that still has *all* old names is the old layout: no mapping at all
    if all(c in names for c in LIVE[lang]):
        return {}
    return out


_REF = re.compile(r"{{([#^/]?)((?:[^{}:]*:)*)([^{}:]+)}}")


def map_template(text: str, mapping: dict[str, str]) -> str:
    """Rewrite field references ({{F}}, {{#F}}, {{^F}}, {{/F}}, {{filter:F}}) in one pass."""
    if not mapping:
        return text

    def sub(m):
        name = m.group(3).strip()
        return "{{" + m.group(1) + m.group(2) + mapping.get(name, name) + "}}" if name in mapping else m.group(0)
    return _REF.sub(sub, text)


def canonical_names(model: dict, lang: str) -> list[str]:
    """The note type's field names in order, translated back to canonical names."""
    inv = {v: k for k, v in resolve(model, lang).items()}
    return [inv.get(f["name"], f["name"]) for f in model["flds"]]
