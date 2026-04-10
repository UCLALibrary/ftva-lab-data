from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from .models import SheetImport, RelationshipType


def _parse_relationship_type_choice(value: str) -> tuple[bool, int] | None:
    """Parse value of `relationship_type` field to determine direction of relationship.

    The information parsed from the value is used in the custom `clean` method
    on the `RelationshipForm` to determine which `RelationshipType` object
    should be used for the relationship at hand, and whether the relationship is
    "outgoing" or "incoming". This direction is then used by the view to determine
    whether the item currently in context should be
    the source or target of the new or updated `Relationship` object.

    :param value: Value of `relationship_type` field with prefix indicating direction,
        e.g. "outgoing:123" to reference `RelationshipType` ID 123 in outgoing direction,
        or "incoming:456" to reference `RelationshipType` ID 456 in incoming direction.
    :return: Tuple containing a boolean indicating whether the relationship is outgoing
        and the ID of the `RelationshipType` object, or `None` if the value is invalid.
    """
    prefix, remainder = value.split(":", 1)
    if prefix not in ("outgoing", "incoming") or not remainder.isdigit():
        return None
    return (prefix == "outgoing", int(remainder))


class ItemForm(forms.ModelForm):
    class Meta:
        model = SheetImport
        fields = [
            "status",
            "notes",
            "batch_number",
            "hard_drive_name",
            "carrier_a",
            "carrier_a_location",
            "carrier_b",
            "carrier_b_location",
            "hard_drive_barcode_id",
            "file_folder_name",
            "sub_folder_name",
            "file_name",
            "file_type",
            "media_type",
            "asset_type",
            "audio_class",
            "inventory_number",
            "date_of_ingest",
            "no_ingest_reason",
            "source_inventory_number",
            "source_barcode",
            "title",
            "job_number",
            "source_type",
            "resolution",
            "compression",
            "file_format",
            "file_size",
            "frame_rate",
            "total_running_time",
            "source_frame_rate",
            "aspect_ratio",
            "color_bit_depth",
            "color_type",
            "frame_layout",
            "sample_structure",
            "sample_rate",
            "capture_device_make_and_model",
            "capture_device_settings",
            "date_capture_completed",
            "video_edit_software_and_settings",
            "date_edit_completed",
            "color_grading_software",
            "color_grading_settings",
            "audio_file_format",
            "date_audio_edit_completed",
            "remaster_platform",
            "remaster_software",
            "remaster_settings",
            "date_remaster_completed",
            "subtitles",
            "watermark_type",
            "security_data_encrypted",
            "migration_or_preservation_record",
            "hard_drive_location",
            "date_job_started",
            "date_job_completed",
            "general_entry_cataloged_by",
        ]

        labels = {
            # for now, only adding custom labels for fields with initials (for capitalization)
            "hard_drive_barcode_id": "Hard drive barcode ID",
            "carrier_a": "Carrier A",
            "carrier_a_location": "Carrier A location",
            "carrier_b": "Carrier B",
            "carrier_b_location": "Carrier B location",
        }

        widgets = {
            "status": forms.CheckboxSelectMultiple,
            "notes": forms.Textarea(attrs={"rows": 4, "cols": 40}),
            "date_of_ingest": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
        }


class RelationshipForm(forms.Form):
    """Form used to add or edit relationships between records in the relationship modal.

    The choices for the `relationship_type` field are set via a custom `__init__` method.
    See below for more details.
    """

    relationship_type = forms.ChoiceField(label="Relationship type")
    target = forms.IntegerField(
        label="Related record ID",
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "placeholder": "Enter record ID",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        """Set the choices for the `relationship_type` field.

        The choices are derived from the `RelationshipType` model,
        with the `type` field for "outgoing" relationships
        and the `reverse_type` field for "incoming" relationships.
        """
        super().__init__(*args, **kwargs)
        outgoing: list[tuple[str, str]] = []
        incoming: list[tuple[str, str]] = []
        # Set the choices for the `relationship_type` field,
        # with prefixes indicating the relationship direction they represent.
        for relationship_type in RelationshipType.objects.order_by("id"):
            outgoing.append(
                (f"outgoing:{relationship_type.pk}", relationship_type.type)
            )
            incoming.append(
                (f"incoming:{relationship_type.pk}", relationship_type.reverse_type)
            )
        # Set the choices with two option groups for the dropdown: "Outgoing" and "Incoming".
        self.fields["relationship_type"].choices = [
            ("Outgoing", outgoing),
            ("Incoming", incoming),
        ]
        # Set initial relationship type to the first outgoing relationship type,
        # if not already set by the caller.
        if not self.is_bound and outgoing and not self.initial.get("relationship_type"):
            self.initial["relationship_type"] = outgoing[0][0]

    def clean(self):
        """Use prefixes on the relationship type choices
        to determine the direction of the relationship.
        """
        cleaned_data = super().clean()
        choice = cleaned_data.get("relationship_type")
        if choice in (None, ""):
            return cleaned_data
        parsed = _parse_relationship_type_choice(choice)
        if parsed is None:
            raise ValidationError(
                {"relationship_type": ["Invalid relationship type selection."]}
            )
        is_outgoing, pk = parsed
        try:
            relationship_type = RelationshipType.objects.get(pk=pk)
        except RelationshipType.DoesNotExist:
            raise ValidationError(
                {"relationship_type": ["Invalid relationship type selection."]}
            )
        cleaned_data["relationship_type"] = relationship_type
        cleaned_data["is_outgoing"] = is_outgoing
        return cleaned_data


class BatchUpdateForm(forms.Form):
    file = forms.FileField(
        label="Select an XLSX file to upload",
        required=True,
        validators=[FileExtensionValidator(allowed_extensions=["xlsx"])],
        widget=forms.FileInput(
            attrs={
                "class": "form-control",
                "accept": (
                    ".xlsx,"
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            }
        ),
    )
