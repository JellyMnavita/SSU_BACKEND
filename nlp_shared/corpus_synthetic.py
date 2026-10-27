"""Génération de phrases synthétiques Kinshasa pour le corpus NLP."""

from __future__ import annotations

import itertools
import random

from nlp_shared.corpus_utils import CorpusRow, normalize_text
from nlp_shared.lexicon_data import SEED_SAMPLES

KINSHASA_COMMUNES = [
    "Bandalungwa",
    "Barumbu",
    "Bumbu",
    "Gombe",
    "Kalamu",
    "Kasa-Vubu",
    "Kimbanseke",
    "Kintambo",
    "Kisenso",
    "Lemba",
    "Limete",
    "Lingwala",
    "Makala",
    "Maluku",
    "Masina",
    "Matete",
    "Mont Ngafula",
    "Ndjili",
    "Ngaba",
    "Ngaliema",
    "Ngiri-Ngiri",
    "Nsele",
    "Selembao",
]

KINSHASA_QUARTIERS = [
    "Menkao",
    "Binza",
    "Delvaux",
    "Salongo",
    "Kingabwa",
    "Mombele",
    "Funa",
    "Victoire",
]

TEMPLATES: dict[str, list[str]] = {
    "violence": [
        "Braquage armé signalé à {place} ce soir",
        "Fusillade entendue vers {place}, les passants fuient",
        "Des kulunas attaquent les motards à {place}",
        "Il y a trop de bandits et de voyous à {place}",
        "Coups de feu près de {place}, situation très tendue",
        "Gang armé terrorise le quartier {place}",
        "Insécurité totale à {place}, on n'ose plus sortir",
        "Criminels armés bloquent la route vers {place}",
        "Zone rouge à {place}, plusieurs blessés signalés",
        "Attaque à main armée à la station de {place}",
    ],
    "vol": [
        "Vol de téléphone à l'arrêt de bus à {place}",
        "Pickpocket actif sur l'avenue de {place}",
        "Cambriolage nocturne signalé à {place}",
        "Voleur de moto en fuite vers {place}",
        "Vol à l'arraché d'un sac à {place}",
        "Plusieurs vols de portables rapportés à {place}",
        "Tentative de cambriolage à {place}, porte forcée",
        "Arracheur de sac près du marché de {place}",
    ],
    "kidnapping": [
        "Tentative d'enlèvement signalée à {place}",
        "Kidnapping d'un citoyen sur la route de {place}",
        "Rumeur d'otage à {place}, la population est inquiète",
        "Enlèvement avorté à {place} ce matin",
        "Séquestration signalée dans le quartier {place}",
    ],
    "agression": [
        "Bagarre entre jeunes à {place}",
        "Agression dans la rue à {place}",
        "Tabassage signalé près de {place}",
        "Menaces et intimidation à {place}",
        "Rixe violente à {place}, intervention demandée",
        "Agression sexuelle signalée à {place}",
    ],
    "vandalisme": [
        "Vandalisme de véhicules à {place}",
        "Panneaux publics dégradés à {place}",
        "Voitures incendiées au quartier {place}",
        "Destruction de biens publics à {place}",
        "Pillage signalé près de {place}",
    ],
    "autre": [
        "Lancement officiel du RDC-PASS à {place}",
        "Le président inaugure un projet numérique national",
        "Commission nationale des droits de l'homme en séance de travail",
        "Match de football très attendu ce dimanche",
        "Le chanteur annonce une tournée internationale",
        "Arnaque internet et ransomware en hausse",
        "Violations des droits humains dans l'Ituri selon un rapport",
        "c'est un test depuis {place}",
        "J'ai vu un canard dans la rue à {place}",
        "Rien à signaler, tout va bien à {place}",
    ],
}


def _places() -> list[str]:
    places = [f"{q}, {c}" for q in KINSHASA_QUARTIERS for c in KINSHASA_COMMUNES[:8]]
    places += [f"commune de {c}" for c in KINSHASA_COMMUNES]
    places += [f"quartier {q}" for q in KINSHASA_QUARTIERS]
    return places


def generate_synthetic_rows(per_label: int = 40, seed: int = 42) -> list[CorpusRow]:
    rng = random.Random(seed)
    places = _places()
    rows: list[CorpusRow] = []

    for label, templates in TEMPLATES.items():
        combos = list(itertools.product(templates, places))
        rng.shuffle(combos)
        for template, place in combos[:per_label]:
            text = normalize_text(template.format(place=place))
            if len(text) < 15:
                continue
            rows.append(CorpusRow(text=text, label=label, source="synthetic"))

    # Variantes orthographiques simples
    extra: list[CorpusRow] = []
    for row in list(rows):
        if row.label == "kidnapping":
            extra.append(
                CorpusRow(
                    text=row.text.replace("enlèvement", "enlevement"),
                    label=row.label,
                    source="synthetic_variant",
                )
            )
        if row.label == "violence" and "bandits" not in row.text.lower():
            extra.append(
                CorpusRow(
                    text=row.text + " — bandits armés",
                    label=row.label,
                    source="synthetic_variant",
                )
            )
    rows.extend(extra[: per_label // 2])

    # Réinjecter le seed officiel
    for text, label in SEED_SAMPLES:
        rows.append(
            CorpusRow(text=normalize_text(text), label=label, source="seed")
        )

    return rows
