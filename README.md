# HR Attendance Correction Portal

A production-ready Flask web application for generating professional employee attendance correction forms.

## Features

✅ **Three Input Methods**
- Manual Entry: Enter employee data directly
- Upload Excel: Bulk import from Excel files
- Upload Image/PDF: OCR-powered scanned document processing

✅ **Document Generation**
- Professional Word documents (.docx)
- PDF export (requires LibreOffice or MS Word)
- Automatic compliance with attendance policies
- Bulk ZIP file downloads

✅ **Attendance Policy Enforcement**
- Maximum 3 Mispunch entries
- Maximum 3 Early Out entries
- Automatic escalation to "Technical Error" after limits

✅ **Production Ready**
- Error logging and traceback capture
- Timeout protection on long operations
- Responsive Bootstrap 5 UI
- Cloud-ready (Render, Heroku, AWS)

## Local Setup

### Prerequisites
- Python 3.8+
- Git
- For PDF output: LibreOffice or Microsoft Word
- For OCR: Tesseract or EasyOCR

### Installation

```bash
# Clone the repository
git clone https://github.com/amolikatwork/attendance_form_generator.git
cd attendance_form_generator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Then open: http://127.0.0.1:5000

## Usage

### Manual Entry
1. Go to **Manual Entry** on the home page
2. Fill in company and employee information
3. Add attendance issues (date + reason)
4. Click "Generate Word" to download

### Upload Excel
1. Go to **Upload Excel** on the home page
2. Provide company name and Excel file
3. Choose output format (Word or PDF)
4. System generates forms for all employees in the file

### Upload Image/PDF
1. Go to **Upload Image/PDF** on the home page
2. Provide company name and scanned document
3. OCR extracts attendance data automatically
4. Download generated forms

## Excel Format

The system expects these columns (flexible naming):

| Column | Examples |
|--------|----------|
| Employee Name | Employee Name, Emp Name, Name |
| Employee Code | Employee Code, Emp Code, ID, Employee ID |
| Date | Date, Day |
| Reason | Reason, Remarks, Status, Attendance Issue, Exception |

## Deployment

### Deploy to Render

1. Push code to GitHub:
   ```bash
   git push origin main
   ```

2. Go to https://render.com

3. Connect your GitHub account

4. Create new **Web Service**
   - Select this repository
   - Environment: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`

5. Set environment variables (optional):
   - `FLASK_ENV=production`
   - `SECRET_KEY=your-secret-key`

6. Deploy!

### Deploy to Heroku

```bash
# Login
heroku login

# Create app
heroku create your-app-name

# Deploy
git push heroku main

# View logs
heroku logs --tail
```

## Project Structure

```
attendance_form_generator/
├── app.py                          # Main Flask application
├── requirements.txt                # Python dependencies
├── Procfile                        # Heroku/Render deployment config
├── render.yaml                     # Render-specific config
├── README.md                       # This file
├── static/
│   └── style.css                   # Custom Bootstrap styles
├── templates/
│   ├── index.html                  # Homepage with 3 cards
│   ├── manual.html                 # Manual entry form
│   ├── upload_excel.html           # Excel upload form
│   └── upload_image.html           # Image/PDF upload form
├── utils/
│   ├── __init__.py
│   ├── attendance_parser.py        # Excel/OCR parsing logic
│   ├── document_generator.py       # Word/PDF generation
│   └── ocr.py                      # OCR text extraction
├── uploads/                        # Temporary upload storage
└── outputs/                        # Generated documents
```

## API Routes

| Route | Method | Purpose |
|-------|--------|----------|
| `/` | GET | Homepage with navigation |
| `/manual` | GET/POST | Manual entry form |
| `/upload-excel` | GET/POST | Excel file upload |
| `/upload-image` | GET/POST | Image/PDF upload |

## Logging

All operations are logged with timestamps:

```
[2026-06-27 14:30:45] INFO: [MANUAL] Request received
[2026-06-27 14:30:45] INFO: [MANUAL] Employee information received: John Doe (EMP-001), Dept: HR, Month: June 2026
[2026-06-27 14:30:46] INFO: [MANUAL] Word generation started
[2026-06-27 14:30:46] INFO: [MANUAL] Word document saved: /outputs/xyz123/EMP-001_John_Doe.docx
[2026-06-27 14:30:46] INFO: [MANUAL] Sending file to user
```

## Configuration

### Upload Limits
- Maximum file size: 25 MB
- Allowed extensions: .xlsx, .xls, .png, .jpg, .jpeg, .pdf

### Attendance Policy
- Maximum Mispunch entries: 3
- Maximum Early Out entries: 3
- Overflow becomes: "Technical Error"

### Output Formats
- **Word (.docx)**: Always available
- **PDF**: Requires LibreOffice (`soffice`) or MS Word

## Troubleshooting

### "PDF output needs Microsoft Word or LibreOffice"
**Solution:** Install LibreOffice
- Ubuntu: `sudo apt-get install libreoffice`
- macOS: `brew install libreoffice`
- Windows: Download from https://www.libreoffice.org

### "OCR is not available"
**Solution:** Install Tesseract or EasyOCR
- **Tesseract:**
  - Ubuntu: `sudo apt-get install tesseract-ocr`
  - macOS: `brew install tesseract`
  - Windows: https://github.com/UB-Mannheim/tesseract/wiki

- **EasyOCR:** Installed via pip (automatic fallback)

### File upload fails
- Check file size (max 25 MB)
- Verify file format (.xlsx, .xls, .png, .jpg, .jpeg, .pdf)
- Check disk space

## Performance

- Manual entry: < 1 second
- Excel parsing (100 records): 2-3 seconds
- Image OCR: 10-30 seconds (depends on file size)
- PDF conversion: 5-15 seconds per document
- Bulk generation (10 employees): 20-40 seconds

## Security

- CSRF protection via Flask session
- File upload validation (extension + size)
- Secure filename generation
- Error messages don't expose system paths
- Uploaded files in isolated directories

## License

MIT License - Feel free to use this project for personal or commercial purposes.

## Support

For issues or questions:
1. Check the logs: `tail -f app.log`
2. Review error messages in the UI
3. Visit: https://github.com/amolikatwork/attendance_form_generator/issues

## Contributors

- Developed with ❤️ for HR teams

---

**Version:** 1.0.0  
**Last Updated:** June 2026
