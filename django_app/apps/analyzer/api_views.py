from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from services.exceptions import ServiceError
from services.pipeline_service import run_document_pipeline
from .models import DocumentSet, SupportingImage
from .serializers import DocumentSetSerializer


class DocumentSetListCreateAPI(generics.ListCreateAPIView):
    queryset = DocumentSet.objects.prefetch_related("image_files").all()
    serializer_class = DocumentSetSerializer
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        title = request.data.get("title", "").strip()
        pdf_file = request.FILES.get("pdf_file")
        images = request.FILES.getlist("image_files")

        if not title:
            return Response({"detail": "title is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not pdf_file:
            return Response({"detail": "pdf_file is required"}, status=status.HTTP_400_BAD_REQUEST)

        document_set = DocumentSet.objects.create(title=title, pdf_file=pdf_file, status="READY_FOR_OCR")
        for image in images:
            SupportingImage.objects.create(document_set=document_set, image_file=image)

        try:
            run_document_pipeline(document_set)
        except ServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(document_set)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DocumentSetDetailAPI(generics.RetrieveAPIView):
    queryset = DocumentSet.objects.prefetch_related("image_files").all()
    serializer_class = DocumentSetSerializer
