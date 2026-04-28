from django.db import models
from django.utils import timezone


class DocumentSet(models.Model):
    """
    Represents one analysis request containing a core PDF and optional supporting images.
    """

    title = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to="documents/pdfs/")
    pdf_extracted_text = models.TextField(blank=True, default="")
    image_extracted_text = models.TextField(blank=True, default="")
    pdf_structured_data = models.JSONField(default=dict, blank=True)
    image_structured_data = models.JSONField(default=dict, blank=True)
    validation_result = models.JSONField(default=dict, blank=True)
    upload_date = models.DateTimeField(default=timezone.now, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=30, default="UPLOADED")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"


class SupportingImage(models.Model):
    """
    Stores one image associated with a DocumentSet.
    """

    document_set = models.ForeignKey(
        DocumentSet, related_name="image_files", on_delete=models.CASCADE
    )
    image_file = models.ImageField(upload_to="documents/images/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Image #{self.pk} for set #{self.document_set_id}"
