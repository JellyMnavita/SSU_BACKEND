"""Génération du rapport PDF — pipeline prédiction spatiale SSU."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from prediction_shared.labels import CLASS_NAMES_FR, FEATURE_NAMES
from prediction_shared.report_assets import PredictionReportAssets, prepare_report_assets
from prediction_shared.dataset import resolve_prediction_data_dir


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
    assets: PredictionReportAssets | None = None,
) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

    root = data_dir or resolve_prediction_data_dir()
    assets = assets or prepare_report_assets(root)
    profile = assets.profile
    training = assets.training
    metrics = assets.metrics
    test_metrics = assets.test_metrics
    comparison = training.get("comparison") or {}
    splits = profile.get("splits") or {}
    cleaning = profile.get("cleaning") or {}
    class_dist = profile.get("class_distribution", {}).get("full") or {}

    doc = SimpleDocTemplate(str(output), pagesize=A4, title="Rapport Prédiction SSU Bokengi")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#1e3a5f")
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=10)
    body = styles["BodyText"]

    story: list[Any] = []
    story.append(_para("<b>Rapport Prédiction spatiale — SSU Bokengi</b>", title_style))
    story.append(
        _para(
            f"<i>Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — "
            "EDA, nettoyage, validation croisée, sélection modèle, gold_eval.</i>",
            body,
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        _table(
            [
                ["Indicateur", "Valeur"],
                ["Signalements (nettoyés)", str(profile.get("total_clean", "—"))],
                [
                    "Train / Val / Test / Gold",
                    f"{splits.get('train', '—')} / {splits.get('val', '—')} / "
                    f"{splits.get('test', '—')} / {splits.get('gold', '—')}",
                ],
                ["Modèle retenu", str(training.get("algorithm") or "—")],
                ["F1 macro (test hold-out)", str(test_metrics.get("f1_macro", "—"))],
                ["F1 macro (gold_eval)", str(metrics.get("f1_macro", "—"))],
                ["Accuracy (gold)", str(metrics.get("accuracy", "—"))],
            ],
            [6 * cm, 9 * cm],
        )
    )
    story.append(PageBreak())

    story.append(_para("1. Objectif", h2))
    story.append(
        _para(
            "Prédire le <b>degré de danger</b> (faible, modéré, élevé) à partir de la "
            "géolocalisation et du contexte spatio-temporel des signalements validés. "
            "Le modèle alimente la carte de chaleur 48×48 et le microservice prediction-service.",
            body,
        )
    )

    story.append(_para("2. Sources et nettoyage", h2))
    story.append(
        _para(
            f"Lignes lues : {cleaning.get('rows_read', '—')}. "
            f"Conservées : {cleaning.get('rows_kept', '—')}. "
            f"Rejet coords invalides : {cleaning.get('removed_invalid_coords', 0)}. "
            f"Hors bbox Kinshasa : {cleaning.get('removed_out_of_bbox', 0)}. "
            f"Degré invalide : {cleaning.get('removed_invalid_degree', 0)}. "
            f"Doublons : {cleaning.get('removed_duplicates', 0)}.",
            body,
        )
    )
    dist_rows = [["Classe", "Effectif"]]
    for name, count in class_dist.items():
        dist_rows.append([name, str(count)])
    if len(dist_rows) > 1:
        story.append(_table(dist_rows, [5 * cm, 4 * cm]))
    img = _img(assets.eda_plots.get("class_balance", Path()))
    if img:
        story.append(img)

    story.append(_para("3. Analyse exploratoire (EDA)", h2))
    spatial = profile.get("spatial") or {}
    story.append(
        _para(
            f"Centroïde approx. : lat {spatial.get('centroid_lat', '—')}, "
            f"lon {spatial.get('centroid_lon', '—')}. "
            f"Période : {profile.get('temporal', {}).get('date_min', '—')} → "
            f"{profile.get('temporal', {}).get('date_max', '—')}.",
            body,
        )
    )
    for key in ("spatial_scatter", "hour_distribution", "weekday_distribution", "top_locations"):
        img = _img(assets.eda_plots.get(key, Path()))
        if img:
            story.append(Spacer(1, 0.2 * cm))
            story.append(img)

    story.append(_para("4. Features et ingénierie", h2))
    story.append(
        _para(
            "Variables d'entrée (6) : " + ", ".join(FEATURE_NAMES) + ". "
            "La densité locale (rayon 500 m, BallTree haversine) et le degré moyen des voisins "
            "sont calculés en <b>leave-one-out</b> à l'entraînement pour éviter la fuite de label.",
            body,
        )
    )
    for step in assets.eda_summary.get("preprocessing") or []:
        story.append(_para(f"• {step}", body))

    story.append(_para("5. Validation croisée et sélection de modèles", h2))
    story.append(_para(training.get("selection_reason") or "Sélection par F1 macro CV.", body))
    comp_rows = [["Modèle", "F1 macro (moy.)", "Écart-type", "Accuracy (moy.)"]]
    for name, entry in comparison.items():
        comp_rows.append([
            name,
            f"{entry.get('f1_macro_mean', 0):.4f}",
            f"±{entry.get('f1_macro_std', 0):.4f}",
            f"{entry.get('accuracy_mean', 0):.4f}",
        ])
    if len(comp_rows) > 1:
        story.append(_table(comp_rows, [4.5 * cm, 3.5 * cm, 3 * cm, 3.5 * cm]))
    img = _img(assets.cv_path)
    if img:
        story.append(img)

    story.append(_para("6. Résultats hold-out (test)", h2))
    story.append(
        _para(
            f"Accuracy : {test_metrics.get('accuracy', '—')}. "
            f"F1 macro : {test_metrics.get('f1_macro', '—')}. "
            f"F1 weighted : {test_metrics.get('f1_weighted', '—')}.",
            body,
        )
    )

    story.append(_para("7. Résultats gold_eval", h2))
    story.append(
        _para(
            f"Échantillons gold : {assets.gold.get('samples', splits.get('gold', '—'))}. "
            f"Accuracy : {metrics.get('accuracy', '—')}. "
            f"F1 macro : {metrics.get('f1_macro', '—')}. "
            f"Précision macro : {metrics.get('precision_macro', '—')}. "
            f"Rappel macro : {metrics.get('recall_macro', '—')}.",
            body,
        )
    )
    report = metrics.get("report") or {}
    if report:
        perf_rows = [["Classe", "Precision", "Recall", "F1"]]
        for lbl in metrics.get("labels_order") or CLASS_NAMES_FR:
            entry = report.get(lbl, {})
            perf_rows.append([
                lbl,
                f"{entry.get('precision', 0):.3f}",
                f"{entry.get('recall', 0):.3f}",
                f"{entry.get('f1-score', 0):.3f}",
            ])
        story.append(_table(perf_rows, [3.5 * cm, 3 * cm, 3 * cm, 3 * cm]))
    for path in (assets.cm_path, assets.f1_path):
        img = _img(path)
        if img:
            story.append(Spacer(1, 0.2 * cm))
            story.append(img)

    story.append(_para("8. Recommandations", h2))
    story.append(
        _para(
            "• Augmenter le volume de signalements validés (statut V) pour stabiliser la CV.<br/>"
            "• Surveiller le déséquilibre entre classes faible / modéré / élevé.<br/>"
            "• Réentraîner après export CSV (Celery :05) ou manuellement.<br/>"
            "• Commandes : <font name='Courier'>bash scripts/run_prediction_retrain.sh</font>, "
            "<font name='Courier'>python scripts/generate_prediction_report.py</font>",
            body,
        )
    )

    doc.build(story)
    return output
