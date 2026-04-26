import os

from django.http import FileResponse, HttpResponse

MAX_UPLOAD_MB = 25

try:
    import weasyprint
except OSError:
    weasyprint = None


def file_response(field_file):
    filename = os.path.basename(field_file.name)
    return FileResponse(field_file.open("rb"), as_attachment=True, filename=filename)


def html_or_pdf_response(html: str, *, filename: str) -> HttpResponse:
    if weasyprint is not None:
        pdf = weasyprint.HTML(string=html).write_pdf()
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse(html, content_type="text/html")
