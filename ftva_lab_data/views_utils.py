import base64
import binascii
from typing import Any
from pymarc import Field
from django.db.models import Model, Q
from django.db.models.query import QuerySet
from django.contrib.auth import authenticate, login
from django.http import HttpResponse, HttpRequest
from urllib.parse import urlencode
from .models import SheetImport
from .forms import ItemForm
from fmrest.record import Record


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
        # For use in external search links
        "inventory_number": item.inventory_number,
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
        "File Type": item.file_type,
        "Asset Type": item.asset_type,
    }
    inventory_info = {
        "Inventory Number": item.inventory_number,
        "UUID": item.uuid,
        "Date of Ingest": item.date_of_ingest,
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
        "file_type",
        "asset_type",
        "inventory_number",
        "date_of_ingest",
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


def format_data_for_export(data_dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Formats a list of dictionaries of SheetImport data for export to Excel.

    :param data_dicts: A list of dictionaries, each representing a row of data.
    :return: A list of dicts with added status and assigned_user fields.
    """

    if not data_dicts:
        return []

    # Gather all IDs
    ids = [d["id"] for d in data_dicts]

    # Bulk fetch all SheetImport objects with related fields
    items = (
        SheetImport.objects.filter(id__in=ids)
        .prefetch_related("status")
        .select_related("assigned_user")
    )
    # Build lookup dicts
    status_map = {
        item.id: ", ".join(item.status.values_list("status", flat=True))
        for item in items
    }
    user_map = {item.id: getattr(item, "assigned_user_full_name", "") for item in items}

    for data_dict in data_dicts:
        item_id = data_dict["id"]
        # Add status display values as a concatenated string
        data_dict["status"] = status_map.get(item_id, "")
        # Replace the assigned_user_id with the full name
        data_dict.pop("assigned_user_id", None)
        data_dict["assigned_user"] = user_map.get(item_id, "")
        # Remove the '_state' field added by Django
        data_dict.pop("_state", None)

    return data_dicts


def build_url_parameters(**kwargs) -> str:
    """Encodes URL parameters as a string ready for use as a query string in the templates.

    :param **kwargs: Keyword arguments representing URL parameters.
    :return: An encoded URL query string.
    """
    return urlencode(kwargs)


def basic_auth_required(view_function: Any) -> Any:
    """Decorator to require basic authentication for a view.
    If the user is authenticated, they can access the view; otherwise,
    they will be prompted to log in using basic auth.

    :param view_func: The view function to decorate.
    :return: A wrapped view function that checks for basic authentication.
    """

    def _wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # Assume request is unauthorized, until proven otherwise.
        # If so, prompt for login via HTTP basic auth.
        unauthorized_response = HttpResponse("Unauthorized", status=401)
        unauthorized_response["WWW-Authenticate"] = 'Basic realm="API"'

        # Start checking for proper authorization.
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header and auth_header.startswith("Basic "):
            try:
                # Decode the auth header
                # First 6 characters are "Basic ", remainder is user:password base64 encoded
                auth_decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                username, password = auth_decoded.split(":", 1)
            except binascii.Error:
                return HttpResponse("Invalid basic auth header", status=400)
            # Authenticate using Django's authenticate function
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_active:
                request.user = user
                login(request, user)
                return view_function(request, *args, **kwargs)
            else:
                # If Django authentication fails, return 401 Unauthorized
                return unauthorized_response
        else:
            return unauthorized_response

    return _wrapped_view


def count_tags(fields: list[Field], tag: str) -> int:
    """Give a list of Pymarc fields, count how many fields have a specific tag.

    :param fields: A list of Pymarc fields to count.
    :param tag: The tag to count in the fields.
    :return: The count of fields with the specified tag."""

    return sum(1 for field in fields if field.tag == tag)


def get_tag_labels(fields: list[Field], tag: str) -> list[str]:
    """Get a list of unique labels for a specific tag in a list of Pymarc fields.
    If there are multiple fields with the same tag, labels will be generated
    as "Field {tag} #1", "Field {tag} #2", etc.
    If there is only one field with the tag, the label will be "Field {tag}".

    :param fields: A list of Pymarc fields to process.
    :param tag: The tag to generate lables for.
    :return: A list of labels for the specified tag.
    """
    count = count_tags(fields, tag)
    if count == 1:
        return [f"Field {tag}"]
    labels = []
    for i in range(count):
        labels.append(f"Field {tag} #{i + 1}")
    return labels


def process_full_alma_data(field_list: list[Field]) -> dict[str, str]:
    """Process a list of Pymarc fields and return a dictionary with processed field tags
    as unique keys, and formatted Pymarc Field values as their values.

    :param field_list: A list of Pymarc Field objects to process.
    :return: A dictionary with keys like "Field 100", "Field 200 #1", etc.,
    and their corresponding formatted values.
    """
    # Initialize an empty dictionary to hold the full record data
    full_record_dict = {}
    # Keep track of which tags we've completed
    completed_tags = set()

    for record_field in field_list:
        if record_field.tag not in completed_tags:
            # Get the labels we will use for this tag, guaranteed to be unique
            # even if there are multiple fields with the same tag
            labels = get_tag_labels(field_list, record_field.tag)

            # Get all other fields from record_fields with the same tag
            current_fields = [f for f in field_list if f.tag == record_field.tag]
            # Update dict with labels and formatted values
            # Vaules are formatted with format_field(), which removes subfield delimiters
            full_record_dict.update(
                {
                    labels[i]: field.format_field()
                    for i, field in enumerate(current_fields)
                }
            )
            completed_tags.add(record_field.tag)

    return full_record_dict


def get_specific_filemaker_fields(
    fm_record: Record, specific_fields: list[str]
) -> dict:
    """Gets the provided specific fields from a Filemaker Record instance.

    :param Record fm_record: A fmrest Record instance.
    :param list[str] specific_fields: A list of specific fields to get from the Record.
    :return: A dict with the specific fields from the Filemaker Record.
    Fields are only included if they exist in the Record.
    """
    record_fields = fm_record.to_dict()
    return {
        field: fm_record[field] for field in specific_fields if field in record_fields
    }


def transform_filemaker_field_name(filemaker_field_name: str) -> str:
    """Transforms a filemaker field name to be more friendly and consistent.

    :param str filemaker_field_name: A Filemaker field name.
    :return: The transformed field name.
    """

    # Certain field names are acronyms, so return them all caps.
    # Otherwise, return sentence case with spaces rather than underscores.
    to_uppercase = ["spac"]

    if filemaker_field_name in to_uppercase:
        filemaker_field_name = filemaker_field_name.upper()
    else:
        filemaker_field_name = filemaker_field_name.replace("_", " ").capitalize()

    return filemaker_field_name


def transform_record_to_dict(record_id: int) -> dict:
    """Transforms a Django record to a dictionary.

    :param int record_id: The ID of the record to transform.
    :return: A dictionary with the record data.
    """

    record = SheetImport.objects.get(id=record_id)
    record_data = {
        field.name: getattr(record, field.name) for field in record._meta.fields
    }
    # Add Status many-to-many field data
    record_data["status"] = [status.status for status in record.status.all()]
    # Add Assigned User data if it exists
    if record.assigned_user:
        record_data["assigned_user"] = {
            "id": record.assigned_user.id,
            "username": record.assigned_user.username,
            "full_name": record.assigned_user.get_full_name(),
        }

    return record_data
