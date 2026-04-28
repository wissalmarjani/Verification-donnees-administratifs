from rest_framework import serializers

from .models import DocumentSet, SupportingImage


class SupportingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportingImage
        fields = ["id", "image_file", "created_at"]


class DocumentSetSerializer(serializers.ModelSerializer):
    image_files = SupportingImageSerializer(many=True, read_only=True)

    class Meta:
        model = DocumentSet
        fields = [
            "id",
            "title",
            "status",
            "upload_date",
            "pdf_file",
            "pdf_structured_data",
            "image_structured_data",
            "validation_result",
            "image_files",
            "created_at",
            "updated_at",
        ]
