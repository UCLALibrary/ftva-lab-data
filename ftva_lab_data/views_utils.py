from typing import Any
from django.db import models


def get_field_value(obj: models.Model, field_name: str) -> Any:
    """
    Helper function to get the value of a field from an object.
    Useful for double underscore prefixed fields.
    """
    for part in field_name.split("__"):
        obj = getattr(obj, part, None)
        if obj is None:
            return ""
    return obj if obj is not None else ""
