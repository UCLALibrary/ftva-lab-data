from typing import Any
from django.db.models import Model, Q
from django.db.models.query import QuerySet
from .models import SheetImport
from .forms import ItemForm
import pandas as pd


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

    :param obj: The model instance to get the field value from.
    :param field: The field name, which can include nested fields separated by "__".
    :return: The value of the field, or an empty string if the field does not exist or is None.
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
    the view_item.html template.

    :param item: The SheetImport object to get the display data for.
    :return: A dictionary with keys "header_info", "storage_info", "file_info",
    "inventory_info", and "advanced_info". Each key maps to a dictionary of field names and values
    for that section.
    """
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
        "Hard Drive Barcode ID": item.hard_drive_barcode_id,
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
    each containing a list of field names to be used in the add/edit item form.

    :param form: The ItemForm instance to get the fields from.
    :return: A dictionary with keys "basic_fields" and "advanced_fields".
    """
    basic_fields = [
        "status",
        "hard_drive_name",
        "carrier_a",
        "carrier_a_location",
        "carrier_b",
        "carrier_b_location",
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

    :param search: The search term to look for in the specified fields.
    :param search_fields: A list of field names to search in. These should be valid
    field names of the SheetImport model or its related models.
    :return: A QuerySet of SheetImport objects that match the search criteria.
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
            # Carriers: search both the carrier itself, and its location
        elif field == "carrier_a_with_location":
            query |= Q(carrier_a__icontains=search)
            query |= Q(carrier_a_location__icontains=search)
        elif field == "carrier_b_with_location":
            query |= Q(carrier_b__icontains=search)
            query |= Q(carrier_b_location__icontains=search)
        elif field == "id":
            # Record id: make this precise, not substring.
            # This is all dynamic, so search string might be empty at first;
            # id also must be numeric, not a string like the others.
            if search:
                try:
                    num_search = int(search)
                except ValueError:
                    # If user something not convertible to int for record id,
                    # treat it like 0 (finding nothing), with no errors.
                    num_search = 0
                query |= Q(id=num_search)
        else:
            query |= Q(**{f"{field}__icontains": search})
    # Finally, apply the query, using distinct() to remove dups possible with multiple statuses.
    items = items.filter(query).distinct()

    return items


def get_search_result_data(
    item_list: QuerySet[SheetImport], display_fields: list[str]
) -> list[dict]:
    """Constructs a list of dicts to use as table rows. Each dict contains two keys:
    * id: the record id.
    * data: a dictionary of field: value, for each field in display_fields.  `field` needs
    to be a field, or property, on `SheetImport`.

    `id` is separate so it is not displayed as a column header or explicit value, but can be
    accessed for links.
    `data` simplifies template output, allowing `row[field]` to be accessed instead of specifying
    each field explicitly.

    :param item_list: A QuerySet of SheetImport objects to process.
    :param display_fields: A list of field names to include in the data dicts.
    :return: A list of dictionaries, each representing a row in the table.
    """

    rows = [
        {
            "id": item.id,
            "data": {field: get_field_value(item, field) for field in display_fields},
        }
        for item in item_list
    ]

    return rows


def get_items_per_page_options() -> list[int]:
    """Returns options to use on the `items_per_page` control
    in `partials/pagination_controls.html`.

    :return list[int]: A list of integers representing per-page options.
    """

    return [10, 20, 50, 100]


def format_data_for_export(data_dicts: list[dict[str, Any]]) -> pd.DataFrame:
    """Formats a list of dictionaries of SheetImport data for export to Excel.

    :param data_dicts: A list of dictionaries, each representing a row of data.
    :return: A pandas DataFrame with the formatted data.
    """

    # Add and remove fields to match the expected output format:
    # Add a column for Status (ManyToMany relationship with Status model),
    # replace the Assigned User ID with assigned_user_full_name property, and
    # remove the '_state' field added by Django.
    for data_dict in data_dicts:
        current_item = SheetImport.objects.get(id=data_dict["id"])
        # Add status display values as a concatenated string
        statuses = current_item.status.values_list("status", flat=True)
        data_dict["status"] = ", ".join(statuses) if statuses else ""
        # Replace the assigned_user_id with the full name
        assigned_user_id = data_dict.pop("assigned_user_id")
        if assigned_user_id is not None:
            assigned_user_full_name = current_item.assigned_user_full_name
            data_dict["assigned_user"] = assigned_user_full_name
        else:
            data_dict["assigned_user"] = ""
        # Remove the '_state' field added by Django
        data_dict.pop("_state", None)

    # Convert rows to DataFrame for exporting
    df = pd.DataFrame(data_dicts)

    return df
