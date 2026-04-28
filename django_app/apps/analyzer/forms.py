from django import forms

from .models import DocumentSet


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class DocumentUploadForm(forms.ModelForm):
    """
    Upload form for one PDF + multiple images.
    """

    image_files = forms.FileField(
        required=False,
        widget=MultipleFileInput(attrs={"accept": ".jpg,.jpeg,.png,image/jpeg,image/png"}),
        help_text="Upload multiple images (JPG or PNG only).",
    )

    class Meta:
        model = DocumentSet
        fields = ["title", "pdf_file", "image_files"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "pdf_file": forms.ClearableFileInput(attrs={"accept": ".pdf"}),
        }

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data["pdf_file"]
        if not pdf_file.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Only PDF files are allowed.")
        return pdf_file

    def clean_image_files(self):
        images = self.files.getlist("image_files")
        allowed_ext = {".jpg", ".jpeg", ".png"}
        for image in images:
            name = image.name.lower()
            if not any(name.endswith(ext) for ext in allowed_ext):
                raise forms.ValidationError("Only JPG and PNG images are allowed.")
        return images
