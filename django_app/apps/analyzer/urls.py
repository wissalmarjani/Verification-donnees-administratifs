from django.urls import path

from .views import upload_documents

app_name = "analyzer"

urlpatterns = [
    path("", upload_documents, name="upload"),
]
