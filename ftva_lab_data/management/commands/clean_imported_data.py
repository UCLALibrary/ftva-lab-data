import re
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport, ItemStatus
from django.db.models import Q


def _is_header_record(record: SheetImport) -> bool:
    """Determines whether a record contains a header row from the imported data.

    :param record: A `SheetImport` record.
    :return bool:
    """
    return record.file_folder_name == "File Folder Name"


def _get_carrier_info(record: SheetImport | None) -> tuple[str, str]:
    """Gets record's relevant carrier fields, for convenient use elsewhere.

    :param record: A `SheetImport` record, or None.
    :return tuple[str, str]: A tuple of values from the input record, or a tuple of
    empty strings if no record was provided.
    """
    if record:
        return (
            record.carrier_a,
            record.carrier_b,
        )
    else:
        return ("", "")


def _get_combined_field_data(record: SheetImport) -> str:
    """Combines all string fields into one big string for some checks elsewhere.

    :param record: A `SheetImport` record.
    :return str:
    """
    # All SheetImport fields are string (CharField) except the system-assigned id
    # and the foreign key relations to assigned_user, status, asset_type,
    # file_type, media_type, and no_ingest_reason (which do not matter
    # at this stage for imported, empty records).
    # Combine all of these string fields into one big string.
    combined_field_data = "".join(
        [
            getattr(record, field.name)
            for field in record._meta.get_fields()
            if field.name
            not in (
                "id",
                "assigned_user",
                "status",
                "date_of_ingest",
                "uuid",
                "asset_type",
                "file_type",
                "media_type",
                "no_ingest_reason",
                "audio_class",
            )
        ]
    )
    # Remove any leading/trailing spaces and return the result.
    return combined_field_data.strip()


def _is_empty_record(record: SheetImport) -> bool:
    """Determines whether all string fields in a record are empty.

    :param record: A `SheetImport` record.
    :return bool:
    """
    return _get_combined_field_data(record) == ""


def _has_file_info(record: SheetImport) -> bool:
    """Determines whether a record has at least one of the attributes needed to indicate file/path
    information.

    :param record: A `SheetImport` record.
    :return bool:
    """
    file_info = "".join(
        [record.file_folder_name, record.sub_folder_name, record.file_name]
    )
    return file_info != ""


def delete_empty_records() -> int:
    """Deletes SheetImport records which contain no data other than
    the system-assigned id.

    :return int: Count of records changed.
    """
    records_changed = 0
    for record in SheetImport.objects.all().order_by("id"):
        if _is_empty_record(record):
            record.delete()
            records_changed += 1

    return records_changed


def set_hard_drive_names() -> int:
    """Sets the hard drive name for rows which can be associated with hard drives,
    based on the presence of a specific header row value.

    :return int: Count of records changed.
    """
    records_changed = 0
    current_drive_name = None
    for record in SheetImport.objects.all().order_by("id"):
        # Ignore empty records.
        if _is_empty_record(record):
            continue
        # Check for value indicating this is a valid hard drive name:
        # "Digital Lab " or "DigitalLab " followed by at least one digit.
        if re.match("Digital[ ]?Lab [0-9]", record.hard_drive_name):
            current_drive_name = record.hard_drive_name
        else:
            if _is_header_record(record):
                # Clear the value so we know to stop if appropriate.
                current_drive_name = None
            # Otherwise, if we still have a value, apply it to the current row.
            else:
                if current_drive_name:
                    record.hard_drive_name = current_drive_name
                    record.save()
                    records_changed += 1

    return records_changed


def set_file_folder_names() -> int:
    """Sets the file folder name for rows which don't have one, but
    do have other file info (subfolder and/or file names).

    :return int: Count of records changed.
    """
    records_changed = 0
    current_file_folder_name = None
    for record in SheetImport.objects.all().order_by("id"):
        # Ignore empty records.
        if _is_empty_record(record):
            continue

        if _is_header_record(record):
            # Clear the value, to avoid copying folder names from a previous device.
            # We also don't want the header value itself, "File Folder Name".
            current_file_folder_name = None
        else:
            if record.file_folder_name:
                # Use this later if needed, but change nothing in this record.
                current_file_folder_name = record.file_folder_name
            else:
                # Since we're here, the record currently has no file_folder_name.
                # Only make updates when the record does have other file info
                # (subfolder and/or file name).
                # current_file_folder_name must also be set, via a previous iteration.
                if current_file_folder_name and _has_file_info(record):
                    record.file_folder_name = current_file_folder_name
                    record.save()
                    records_changed += 1

    return records_changed


def set_carrier_info() -> int:
    """Sets several carrier-related fields for rows which don't have it, but
    do have file info (subfolder and/or file names).
    Applies only to rows which are not associated with hard drives.

    :return int: Count of records changed.
    """
    records_changed = 0
    # Initialize with empty values.
    prev_carrier_a, prev_carrier_b = _get_carrier_info(None)

    # Look only at non-hard-drive records, as carrier / tape info is spotty for media which
    # is also on hard drives.
    # Also exclude records which have carrier locations set, which are only the Hearst ML Tapes;
    # those all have carrier_a_location == "Digital Lab", already have carrier_a filled in,
    # and don't have carrier_b.
    for record in (
        SheetImport.objects.filter(hard_drive_name="")
        .exclude(carrier_a_location="Digital Lab")
        .order_by("id")
    ):
        # Ignore empty records.
        if _is_empty_record(record):
            continue

        # Ignore header records: there's only one in the tapes section (around row 4563)
        # and it's not relevant.
        if _is_header_record(record):
            continue

        carrier_a, carrier_b = _get_carrier_info(record)
        if carrier_a and carrier_b:
            # Records with both need no update, but save this data updating other records.
            prev_carrier_a, prev_carrier_b = carrier_a, carrier_b
        else:
            # Current record is missing at least one carrier.
            # Only update if both (all()) previous carrier values exist.
            # Only update records with real file info.
            # Only fill in empty carrier fields with previous value(s).
            if all((prev_carrier_a, prev_carrier_b)) and _has_file_info(record):
                # Both prev_carrier_a and prev_carrier_b have values.
                # Keep the current carrier value(s) if they exist (are not the default ""),
                # otherwise use the value(s) from the previous record that has both.
                record.carrier_a = (
                    record.carrier_a if record.carrier_a else prev_carrier_a
                )
                record.carrier_b = (
                    record.carrier_b if record.carrier_b else prev_carrier_b
                )
                record.save()
                records_changed += 1

    return records_changed


def delete_header_records() -> int:
    """Deletes header rows that are embedded throughout the original imported data.

    :return int: Count of records deleted.
    """
    records_deleted = 0
    for record in SheetImport.objects.all().order_by("id"):
        if _is_header_record(record):
            record.delete()
            records_deleted += 1
    return records_deleted


def delete_hard_drive_only_records() -> int:
    """Deletes records which only have a value in the hard_drive_name field.

    :return int: Count of records deleted.
    """
    records_deleted = 0
    for record in SheetImport.objects.all().order_by("id"):
        combined_field_data = _get_combined_field_data(record)
        if combined_field_data == record.hard_drive_name:
            record.delete()
            records_deleted += 1
    return records_deleted


def set_status_for_records_with_inline_notes() -> int:
    """Adds `Needs review` status to records with inline notes in the path fields.

    :return int: Count of records updated.
    """
    # Thus far, the fields representing path components are the only fields
    # where we need to flag inline notes. Other fields may have inline notes,
    # but these are the ones that have been identified as most potentially problematic.
    fields_to_query = ["file_folder_name", "sub_folder_name", "file_name"]
    # The pattern matches any character between square brackets zero or more times.
    # These are presumed to be inline notes, rather than actual sub-strings of the paths
    # represented in the fields.
    pattern = r"\[.*?\]"

    query = Q()
    for field in fields_to_query:
        # Add OR statements to the Q object,
        # unpacking the dynamic dict to keyword arguments.
        query |= Q(**{f"{field}__regex": pattern})

    records = SheetImport.objects.filter(query)

    need_review_status = ItemStatus.objects.get(status="Needs review")
    for record in records:
        record.status.add(need_review_status.id)

    return records.count()


class Command(BaseCommand):
    help = "Clean up imported Digital Labs Google Sheet data"

    def handle(self, *args, **options) -> None:

        records_deleted = delete_empty_records()
        self.stdout.write(f"Empty records deleted: {records_deleted}")

        records_changed = set_hard_drive_names()
        self.stdout.write(f"Hard drive names set: {records_changed}")

        records_changed = set_file_folder_names()
        self.stdout.write(f"Folder names set: {records_changed}")

        records_changed = set_carrier_info()
        self.stdout.write(f"Carrier info set: {records_changed}")

        # This must be done after some of the methods above, which rely on header info.
        records_deleted = delete_header_records()
        self.stdout.write(f"Header records deleted: {records_deleted}")

        records_deleted = delete_hard_drive_only_records()
        self.stdout.write(f"Hard drive only records deleted: {records_deleted}")

        records_updated = set_status_for_records_with_inline_notes()
        self.stdout.write(f"Records with inline notes status set: {records_updated}")
