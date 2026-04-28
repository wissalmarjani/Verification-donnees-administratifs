from PIL import Image
import pytesseract


def extract_text_from_image(image_path: str) -> str:
    """
    Extract text from a single image using Tesseract OCR.
    """

    with Image.open(image_path) as img:
        text = pytesseract.image_to_string(img)
    return (text or "").strip()
