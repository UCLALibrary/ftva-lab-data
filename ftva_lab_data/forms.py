from django import forms
from .models import SheetImport


class ItemForm(forms.ModelForm):
    class Meta:
        model = SheetImport
        fields = [
            "status",
            "notes",
            "hard_drive_name",
            "carrier_a",
            "carrier_a_location",
            "carrier_b",
            "carrier_b_location",
            "hard_drive_barcode_id",
            "file_folder_name",
            "sub_folder_name",
            "file_name",
            "inventory_number",
            "date_of_ingest",
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
