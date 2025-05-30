from typing import Any
from django.db import models


# Recursive implementation adapted from:
# https://stackoverflow.com/a/74613925
def get_field_value(obj: models.Model, field: str) -> Any:
    """Recursive getattr function to traverse foreign key relations.
    Default getattr only works for direct fields.
    This function allows you to access nested fields using the "__" notation.

    For example:
    get_foreign_key_attr(
        <SheetImport: SheetImport object (2)>, "assigned_user__username"
    )
    splits the "field" string by "__" and finds the value of the "username"
    field of the "assigned_user" foreign key relation.

    Returns the value of the field, or an empty string if the field does not exist
    or is None.
    """
    fields = field.split("__")
    if len(fields) == 1:
        return getattr(obj, fields[0], "")
    else:
        first_field = fields[0]
        remaining_fields = "__".join(fields[1:])
        return get_field_value(getattr(obj, first_field), remaining_fields)
