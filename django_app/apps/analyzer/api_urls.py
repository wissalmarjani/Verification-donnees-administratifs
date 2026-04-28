from django.urls import path

from .api_views import DocumentSetDetailAPI, DocumentSetListCreateAPI

app_name = "analyzer_api"

urlpatterns = [
    path("document-sets/", DocumentSetListCreateAPI.as_view(), name="document-set-list-create"),
    path("document-sets/<int:pk>/", DocumentSetDetailAPI.as_view(), name="document-set-detail"),
]
