from django.contrib import admin
from .models import DocumentSet, SupportingImage


class SupportingImageInline(admin.TabularInline):
    model = SupportingImage
    extra = 0


@admin.register(DocumentSet)
class DocumentSetAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "created_at")
    search_fields = ("title",)
    list_filter = ("status", "created_at")
    inlines = [SupportingImageInline]
