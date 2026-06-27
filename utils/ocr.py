from pathlib import Path


def extract_text_from_image_or_pdf(path):
    """
    Extract text from image or PDF using OCR.
    """
    extension = Path(path).suffix.lower()
    
    if extension == ".pdf":
        return _extract_pdf_text(path)
    
    return _extract_image_text(path)


def _extract_image_text(path):
    """
    Use EasyOCR or Tesseract for image OCR.
    """
    # Try Tesseract first
    try:
        from PIL import Image
        import pytesseract
        return pytesseract.image_to_string(Image.open(path))
    except Exception:
        pass
    
    # Fallback to EasyOCR
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
        results = reader.readtext(path, detail=0)
        return "\n".join(results)
    except Exception as exc:
        raise RuntimeError(
            "OCR not available. Install pytesseract or easyocr."
        ) from exc


def _extract_pdf_text(path):
    """
    Extract text from PDF (embedded text first, then OCR).
    """
    text = _extract_embedded_pdf_text(path)
    if text.strip():
        return text
    
    # Fallback to OCR
    try:
        from pdf2image import convert_from_path
        import pytesseract
        
        pages = convert_from_path(path, dpi=250)
        return "\n".join(pytesseract.image_to_string(page) for page in pages)
    except Exception as exc:
        raise RuntimeError(
            "PDF OCR requires pdf2image and pytesseract."
        ) from exc


def _extract_embedded_pdf_text(path):
    """
    Extract selectable text from PDF.
    """
    try:
        import fitz
        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""
