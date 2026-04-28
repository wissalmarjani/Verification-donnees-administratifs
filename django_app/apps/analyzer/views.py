import logging

from django.contrib import messages
from django.shortcuts import render

from services.exceptions import ServiceError
from services.pipeline_service import run_document_pipeline
from .forms import DocumentUploadForm
from .models import DocumentSet, SupportingImage

logger = logging.getLogger("analyzer.web")


def upload_documents(request):
    """
    Main upload page: accepts one PDF and multiple images.
    """

    final_result = None

    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document_set = form.save(commit=False)
            document_set.status = "READY_FOR_OCR"
            document_set.save()

            for image in request.FILES.getlist("image_files"):
                SupportingImage.objects.create(document_set=document_set, image_file=image)
            try:
                final_result = run_document_pipeline(document_set)
                messages.success(request, "Files uploaded and analyzed successfully.")
            except ServiceError as exc:
                document_set.status = "ERROR"
                document_set.save(update_fields=["status", "updated_at"])
                messages.error(request, str(exc))
                logger.warning("Pipeline business error for document_set=%s: %s", document_set.id, exc)
            except Exception:
                document_set.status = "ERROR"
                document_set.save(update_fields=["status", "updated_at"])
                messages.error(request, "Unexpected error occurred during processing.")
                logger.exception("Unhandled pipeline error for document_set=%s", document_set.id)
            form = DocumentUploadForm()
    else:
        form = DocumentUploadForm()

    recent_sets = DocumentSet.objects.prefetch_related("image_files").all()[:10]
    latest_set = recent_sets[0] if recent_sets else None
    if not final_result and latest_set:
        final_result = latest_set.validation_result or None

    kpis = {
        "total_uploads": DocumentSet.objects.count(),
        "valid_count": DocumentSet.objects.filter(status="VALID").count(),
        "error_count": DocumentSet.objects.filter(status="ERROR").count(),
        "ready_count": DocumentSet.objects.filter(status="READY_FOR_OCR").count(),
    }
    return render(
        request,
        "analyzer/upload.html",
        {
            "form": form,
            "recent_sets": recent_sets,
            "latest_set": latest_set,
            "final_result": final_result,
            "kpis": kpis,
        },
    )
