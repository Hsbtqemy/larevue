import os
import secrets

from django.http import FileResponse, HttpResponse

MAX_UPLOAD_MB = 25


def generate_temp_password() -> str:
    """Return a random URL-safe password (~24 chars). Strong enough for a temporary credential."""
    return secrets.token_urlsafe(18)


def actor_name(user):
    return user.get_full_name() or user.email


def create_audit_note(*, issue=None, article=None, author, message):
    from apps.articles.models import InternalNote  # avoid circular import
    InternalNote.objects.create(
        issue=issue,
        article=article,
        author=author,
        content=message,
        is_automatic=True,
    )

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
