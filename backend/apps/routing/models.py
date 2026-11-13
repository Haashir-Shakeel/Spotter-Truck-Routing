import uuid

from django.db import models


class TripAnalysisRecord(models.Model):
    """A completed analysis, stored as JSON so it can be re-opened and its corridor fetched.

    Checkpoints and geometry stay inside ``result``; nothing queries them individually.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    request = models.JSONField()
    result = models.JSONField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Trip analysis {self.id}"
