from typing import Any
from django.db import models
from .models import SheetImport
from .forms import ItemForm


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
    # Special case for status field, which is a ManyToMany field
    if field == "status":
        return [str(status) for status in obj.status.all()]
    fields = field.split("__")
    if len(fields) == 1:
        return getattr(obj, fields[0], "")
    else:
        first_field = fields[0]
        remaining_fields = "__".join(fields[1:])
        return get_field_value(getattr(obj, first_field), remaining_fields)


def get_item_display_dicts(item: SheetImport) -> dict[str, Any]:
    """Returns a dictionary of dictionaries. Each top-level dict represents a display section for
    the view_item.html template."""
    header_info = {
        "file_name": item.file_name,
        "title": item.title,
        "status": [str(status) for status in item.status.all()],
        "id": item.id,
    }
    storage_info = {
        "Hard Drive Name": item.hard_drive_name,
        "DML LTO Tape ID": item.dml_lto_tape_id,
        "ARSC LTO Tape ID": item.arsc_lto_tape_id,
        "Hard Drive Barcode ID": item.hard_drive_barcode_id,
    }
    file_info = {
        "File/Folder Name": item.file_folder_name,
        "Sub-Folder Name": item.sub_folder_name,
        "File Name": item.file_name,
    }
    inventory_info = {
        "Inventory Number": item.inventory_number,
        "Source Barcode": item.source_barcode,
        "Title": item.title,
        "Notes": item.notes,
    }
    advanced_info = {
        "Source Inventory Number": item.source_inventory_number,
        "Job Number": item.job_number,
        "Source Type": item.source_type,
        "Resolution": item.resolution,
        "Compression": item.compression,
        "File Format": item.file_format,
        "File Size": item.file_size,
        "Frame Rate": item.frame_rate,
        "Total Running Time": item.total_running_time,
        "Source Frame Rate": item.source_frame_rate,
        "Aspect Ratio": item.aspect_ratio,
        "Color Bit Depth": item.color_bit_depth,
        "Color Type": item.color_type,
        "Frame Layout": item.frame_layout,
        "Sample Structure": item.sample_structure,
        "Sample Rate": item.sample_rate,
        "Capture Device Make and Model": item.capture_device_make_and_model,
        "Capture Device Settings": item.capture_device_settings,
        "Date Capture Completed": item.date_capture_completed,
        "Video Edit Software and Settings": item.video_edit_software_and_settings,
        "Date Edit Completed": item.date_edit_completed,
        "Color Grading Software": item.color_grading_software,
        "Color Grading Settings": item.color_grading_settings,
        "Audio File Format": item.audio_file_format,
        "Date Audio Edit Completed": item.date_audio_edit_completed,
        "Remaster Platform": item.remaster_platform,
        "Remaster Software": item.remaster_software,
        "Remaster Settings": item.remaster_settings,
        "Date Remaster Completed": item.date_remaster_completed,
        "Subtitles": item.subtitles,
        "Watermark Type": item.watermark_type,
        "Security Data Encrypted": item.security_data_encrypted,
        "Migration or Preservation Record": item.migration_or_preservation_record,
        "Hard Drive Location": item.hard_drive_location,
        "Date Job Started": item.date_job_started,
        "Date Job Completed": item.date_job_completed,
        "General Entry Cataloged By": item.general_entry_cataloged_by,
    }
    return {
        "header_info": header_info,
        "storage_info": storage_info,
        "file_info": file_info,
        "inventory_info": inventory_info,
        "advanced_info": advanced_info,
    }


def get_add_edit_item_fields(form: ItemForm) -> dict[str, list[str]]:
    """Returns a dict with keys "basic_fields" and "advanced_fields",
    each containing a list of field names to be used in the add/edit item form."""
    basic_fields = [
        "status",
        "hard_drive_name",
        "dml_lto_tape_id",
        "arsc_lto_tape_id",
        "hard_drive_barcode_id",
        "title",
        "file_folder_name",
        "sub_folder_name",
        "file_name",
        "inventory_number",
        "notes",
    ]
    advanced_fields = [f for f in form.fields if f not in basic_fields]

    return {"basic_fields": basic_fields, "advanced_fields": advanced_fields}
