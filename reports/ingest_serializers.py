from rest_framework import serializers

from .models import ScrapedReport


class ScrapedReportSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ScrapedReport
        fields = [
            "id",
            "url_source",
            "title",
            "content",
            "image_url",
            "source_site",
            "published_label",
            "date_scraped",
            "longitude",
            "latitude",
            "location_label",
            "status",
            "status_display",
            "reject_reason",
            "report_id",
        ]
