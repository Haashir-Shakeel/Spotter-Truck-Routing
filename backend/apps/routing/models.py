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
    # Corridor forecast for the 0-48 h slider, computed on first request and then reused so
    # moving between analyses never re-hits the weather provider.
    corridor = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Trip analysis {self.id}"
