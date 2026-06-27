"""API admin — dataset vision et corrections de classe."""

from __future__ import annotations

from pathlib import Path

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminUserType

from .models import Report
from .vision_dataset import VISION_LABELS, dataset_stats, import_uploaded_files
from .vision_feedback import apply_vision_label_correction


class VisionDatasetStatsView(APIView):
    permission_classes = [IsAdminUserType]

    def get(self, request):
        stats = dataset_stats()
        stats["labels"] = list(VISION_LABELS)
        return Response(stats)


class VisionDatasetImportView(APIView):
    permission_classes = [IsAdminUserType]

    def post(self, request):
        label = (request.data.get("label") or request.POST.get("label") or "").strip().lower()
        if label not in VISION_LABELS:
            return Response(
                {"error": f"label requis parmi : {', '.join(VISION_LABELS)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        files = request.FILES.getlist("images") or request.FILES.getlist("files")
        if not files:
            single = request.FILES.get("image") or request.FILES.get("file")
            if single:
                files = [single]
        if not files:
            return Response(
                {"error": "Aucune image reçue (champ images[] ou file)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = import_uploaded_files(files, label)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)


class ReportVisionFeedbackView(APIView):
    """Corrige la classe vision d'un signalement et exporte la photo au dataset."""

    permission_classes = [IsAdminUserType]

    def post(self, request, pk: int):
        report = Report.objects.filter(pk=pk).first()
        if not report:
            return Response({"error": "Signalement introuvable"}, status=status.HTTP_404_NOT_FOUND)

        label = (request.data.get("correct_label") or request.data.get("label") or "").strip().lower()
        if not label:
            return Response({"error": "correct_label requis"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = apply_vision_label_correction(
                report,
                label,
                reviewer_id=getattr(request.user, "id", None),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "report_id": report.id,
                "correct_label": label,
                "predicted_label": result.get("predicted_label"),
                "exported_path": result.get("path"),
                "duplicate": result.get("duplicate", False),
                "retrain_queued": result.get("retrain_queued", False),
                "ai_vision_results": report.ai_vision_results,
                "vision_dataset_export": (report.ai_enrichment_summary or {}).get(
                    "vision_dataset_export"
                ),
            }
        )

    def get(self, request, pk: int):
        report = Report.objects.filter(pk=pk).first()
        if not report:
            return Response({"error": "Signalement introuvable"}, status=status.HTTP_404_NOT_FOUND)
        summary = report.ai_enrichment_summary or {}
        return Response(
            {
                "report_id": report.id,
                "predicted_label": (report.ai_vision_results or {}).get("detected_objects", [{}])[0].get("label")
                if report.ai_vision_results
                else None,
                "vision_dataset_export": summary.get("vision_dataset_export"),
                "vision_corrected_label": summary.get("vision_corrected_label"),
                "labels": list(VISION_LABELS),
            }
        )
