import os
import uuid


class VersionedUploadTo:
    def __init__(self, prefix):
        self.prefix = prefix

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()
        return f"{self.prefix}/{uuid.uuid4().hex}{ext}"

    def deconstruct(self):
        return ("apps.core.storage.VersionedUploadTo", [self.prefix], {})
