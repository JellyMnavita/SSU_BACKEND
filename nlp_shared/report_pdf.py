"""Génération du rapport PDF — pipeline NLP SSU."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from nlp_shared.lexicon_data import INCIDENT_TYPES
from nlp_shared.report_assets import NlpReportAssets, prepare_report_assets
from nlp_shared.training.dataset import resolve_nlp_data_dir


def _para(text: str, style) -> Any:
    from reportlab.platypus import Paragraph

    return Paragraph(text.replace("\n", "<br/>"), style)


def _table(rows: list[list[str]], col_widths: list[float] | None = None) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return tbl


def _img(path: Path, width_cm: float = 14) -> Any | None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Image

    if not path.is_file():
        return None
    return Image(str(path), width=width_cm * cm, height=width_cm * 0.65 * cm)


def generate_comprehensive_pdf(
    output: Path,
    data_dir: Path | None = None,
    assets: NlpReportAssets | None = None,
    *,
    api_url: str | None = None,
) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

    root = data_dir or resolve_nlp_data_dir()
    assets = assets or prepare_report_assets(root, api_url=api_url)
    profile = assets.profile
    training = assets.training
    metrics = assets.metrics
    comparison = training.get("comparison") or {}

    doc = SimpleDocTemplate(str(output), pagesize=A4, title="Rapport NLP SSU Bokengi")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#1e3a5f")
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=10)
    body = styles["BodyText"]

    story: list[Any] = []
    totals = profile.get("totals") or {}

    story.append(_para("<b>Rapport NLP — classification de signalements SSU Bokengi</b>", title_style))
    story.append(
        _para(
            f"<i>Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — "
            "corpus, règles lexique, comparaison TF-IDF / LSTM / DistilCamemBERT, gold_eval.</i>",
            body,
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        _table(
            [
                ["Indicateur", "Valeur"],
                ["Textes corpus", str(totals.get("all", "—"))],
                ["Train / Val / Test / Gold", f"{totals.get('train')} / {totals.get('val')} / {totals.get('test')} / {totals.get('gold')}"],
                ["Modèle ML retenu", str(training.get("primary_ml") or "—")],
                ["F1 macro (gold, pipeline)", str(metrics.get("f1_macro", "—"))],
                ["Règles lexique (eval)", f"{assets.rules_eval.get('ok', 0)}/{assets.rules_eval.get('total', 0)}"],
                ["Filtres anodins (eval)", f"{assets.benign_eval.get('ok', 0)}/{assets.benign_eval.get('total', 0)}"],
            ],
            [6 * cm, 9 * cm],
        )
    )
    story.append(PageBreak())

    story.append(_para("1. Objectif", h2))
    story.append(
        _para(
            "Classifier les descriptions de signalements en types d'incident "
            f"({', '.join(INCIDENT_TYPES)}). "
            "Pipeline production : filtres anodins → règles lexique Kinshasa → "
            "modèle ML (TF-IDF, LSTM ou DistilCamemBERT) → fusion avec la vision (62 % / 38 %).",
            body,
        )
    )

    story.append(_para("2. Corpus et prétraitement", h2))
    sources = profile.get("sources") or {}
    story.append(
        _para(
            f"Sources : synthetic={sources.get('synthetic', 0)}, humvi={sources.get('humvi', 0)}, "
            f"ssu_db={sources.get('ssu', 0)}, seed={sources.get('seed', 0)}. "
            f"Déséquilibre classes (ratio max/min) : {profile.get('class_imbalance_ratio', '—')}. "
            f"Longueur moyenne : {profile.get('text_length_words', {}).get('mean', '—')} mots.",
            body,
        )
    )
    img = _img(assets.eda_plots.get("label_distribution", Path()))
    if img:
        story.append(img)

    story.append(_para("3. Comparaison modèles et sélection", h2))
    story.append(
        _para(
            training.get("selection_reason")
            or "Sélection automatique : meilleur F1 macro sur validation.",
            body,
        )
    )
    comp_rows = [["Modèle", "Val F1 macro", "Test F1 macro"]]
    for name, entry in comparison.items():
        comp_rows.append([
            name,
            f"{(entry.get('val_f1_macro') or 0):.4f}",
            f"{(entry.get('test_f1_macro') or 0):.4f}",
        ])
    if len(comp_rows) > 1:
        story.append(_table(comp_rows, [5 * cm, 4 * cm, 4 * cm]))
    img = _img(assets.eda_plots.get("model_comparison", Path()))
    if img:
        story.append(Spacer(1, 0.3 * cm))
        story.append(img)

    story.append(_para("4. Règles lexique et filtres", h2))
    story.append(
        _para(
            f"{profile.get('rules_count', 0)} règles regex prioritaires (armes, violence, vol, etc.). "
            f"Précision jeu rules_eval : {assets.rules_eval.get('accuracy', 0):.0%}. "
            f"Précision filtres anodins : {assets.benign_eval.get('accuracy', 0):.0%}.",
            body,
        )
    )

    story.append(_para("5. Résultats gold_eval (pipeline complet)", h2))
    story.append(
        _para(
            f"Échantillons : {assets.gold.get('samples', '—')}. "
            f"Accuracy : {metrics.get('accuracy', '—')}. "
            f"F1 macro : {metrics.get('f1_macro', '—')}. "
            f"F1 weighted : {metrics.get('f1_weighted', '—')}.",
            body,
        )
    )
    dist = assets.gold.get("model_used_distribution") or {}
    if dist:
        story.append(_para("Répartition model_used : " + ", ".join(f"{k}={v}" for k, v in dist.items()), body))
    for path in (assets.cm_path, assets.f1_path):
        img = _img(path)
        if img:
            story.append(Spacer(1, 0.2 * cm))
            story.append(img)

    story.append(_para("6. Recommandations", h2))
    story.append(
        _para(
            "• Enrichir le corpus <b>violence</b> et <b>arme</b> avec signalements terrain validés.<br/>"
            "• Réentraîner après corrections admin (Paramètres → NLP ou Celery).<br/>"
            "• LSTM sous-performant sur petit corpus — TF-IDF + règles reste robuste.<br/>"
            "• Commandes : <font name='Courier'>bash scripts/run_nlp_retrain.sh</font>, "
            "<font name='Courier'>python scripts/generate_nlp_report.py --api http://localhost:8002</font>",
            body,
        )
    )

    doc.build(story)
    return output
