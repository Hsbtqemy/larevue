import os

from django.http import FileResponse


def file_response(field_file):
    filename = os.path.basename(field_file.name)
    return FileResponse(field_file.open("rb"), as_attachment=True, filename=filename)
