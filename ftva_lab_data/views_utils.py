from typing import Any
from django.db.models import Model, Q
from django.db.models.query import QuerySet
from .models import SheetImport
from .forms import ItemForm


# Recursive implementation adapted from:
# https://stackoverflow.com/a/74613925
def get_field_value(obj: Model, field: str) -> Any:
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


def get_carrier_with_location(item: SheetImport, carrier_field_name: str) -> str:
    carrier_location_field_name = f"{carrier_field_name}_location"
    carrier = getattr(item, carrier_field_name)
    carrier_location = getattr(item, carrier_location_field_name)
    carrier_info = f"{carrier} ({carrier_location})" if carrier_location else carrier
    return carrier_info


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
        "Carrier A": item.carrier_a,
        "Carrier A Location": item.carrier_a_location,
        "Carrier B": item.carrier_b,
        "Carrier B Location": item.carrier_b_location,
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
        "Notes": item.notes,
    }
    advanced_info = {
        "Source Inventory Number": item.source_inventory_number,
        "Title": item.title,
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
        "carrier_a",
        "carrier_a_location",
        "carrier_b",
        "carrier_b_location",
        "hard_drive_barcode_id",
        "file_folder_name",
        "sub_folder_name",
        "file_name",
        "inventory_number",
        "notes",
    ]
    advanced_fields = [f for f in form.fields if f not in basic_fields]

    return {"basic_fields": basic_fields, "advanced_fields": advanced_fields}


def get_search_result_items(search: str, search_fields: list[str]) -> QuerySet:
    """Searches for `search` term in `search_fields`.  Field names must be present
    in ftva_lab_data.table_config.

    Returns a QuerySet of SheetImport objects matching the search.
    """

    # Use all() here instead of only(specific fields) to allow separation
    # of search from display.
    items = SheetImport.objects.all().order_by("id")

    # General CTRL-F-style substring search across requested fields.
    # Start with empty Q() object, then add queries for all requested fields.
    query = Q()
    for field in search_fields:
        if field == "status":
            # Handle status field separately since it is a ManyToMany field
            query |= Q(status__status__icontains=search)
        elif field == "assigned_user_full_name":
            # Assigned user: allow search by first name, last name, and username
            query |= Q(assigned_user__last_name__icontains=search)
            query |= Q(assigned_user__first_name__icontains=search)
            query |= Q(assigned_user__username__icontains=search)
        elif field == "carrier_a":
            query |= Q(carrier_a__icontains=search)
            query |= Q(carrier_a_location__icontains=search)
        elif field == "carrier_b":
            query |= Q(carrier_b__icontains=search)
            query |= Q(carrier_b_location__icontains=search)
        else:
            query |= Q(**{f"{field}__icontains": search})
    # Finally, apply the query, using distinct() to remove dups possible with multiple statuses.
    items = items.filter(query).distinct()

    return items


def get_search_result_data(
    item_list: QuerySet[SheetImport], display_fields: list[str]
) -> list[dict]:
    """Constructs a list of dicts to use as table rows. Each dict contains two keys:
    * data: a dictionary of field: value, for each field in display_fields.
    * id: the record id.

    `data` simplifies template output, allowing `row[field]` to be accessed instead of specifying
    each field explicitly.
    `id` is separate so it is not displayed as a column header or explicit value, but can be
    accessed for links.
    """

    rows = []
    for item in item_list:
        data = {}
        for field in display_fields:
            if field in ["carrier_a", "carrier_b"]:
                # For carriers, we need to combine fields for display.
                value = get_carrier_with_location(item, field)
            else:
                value = get_field_value(item, field)
            data[field] = value
        rows.append({"id": item.id, "data": data})

    return rows
