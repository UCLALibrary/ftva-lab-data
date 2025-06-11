import re
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport


def _is_header_record(record: SheetImport) -> bool:
    """Determines whether a record contains a header row from the imported data."""
    return record.file_folder_name == "File Folder Name"


def _get_combined_field_data(record: SheetImport) -> str:
    """Combines all string fields into one big string for some checks elsewhere."""
    # All SheetImport fields are string (CharField) except the system-assigned id
    # and the foreign key relations to assigned_user and status (which does not matter
    # at this stage for imported, empty records).
    # Combine all of these string fields into one big string.
    combined_field_data = "".join(
        [
            getattr(record, field.name)
            for field in record._meta.get_fields()
            if field.name not in ("id", "assigned_user", "status")
        ]
    )
    # Remove any leading/trailing spaces and return the result.
    return combined_field_data.strip()


def delete_empty_records() -> int:
    """Deletes SheetImport records which contain no data other than
    the system-assigned id.
    """
    records_changed = 0
    for record in SheetImport.objects.all().order_by("id"):
        # All SheetImport fields are string (CharField) except the system-assigned id
        # and the foreign key relations to assigned_user and status (which does not matter
        # at this stage for imported, empty records).
        # Combine all of these string fields into one big string.
        combined_field_data = _get_combined_field_data(record)
        # If the resulting string is empty, delete the record.
        if combined_field_data == "":
            record.delete()
            records_changed += 1

    return records_changed


def set_hard_drive_names() -> int:
    """Sets the hard drive name for rows which can be associated with hard drives,
    based on the presence of a specific header row value.
    """
    records_changed = 0
    current_drive_name = None
    for record in SheetImport.objects.all().order_by("id"):
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
    do have file names."""
    records_changed = 0
    current_file_folder_name = None
    for record in SheetImport.objects.all().order_by("id"):
        if _is_header_record(record):
            # Clear the value, to avoid copying folder names from a previous device.
            # We also don't want the header value itself, "File Folder Name".
            current_file_folder_name = None
        else:
            if record.file_folder_name:
                # Use this later if needed, but change nothing in this record.
                current_file_folder_name = record.file_folder_name
            else:
                if current_file_folder_name:
                    record.file_folder_name = current_file_folder_name
                    record.save()
                    records_changed += 1

    return records_changed


def delete_header_records() -> int:
    """Deletes header rows that are embedded throughout the original imported data."""
    records_deleted = 0
    for record in SheetImport.objects.all().order_by("id"):
        if _is_header_record(record):
            record.delete()
            records_deleted += 1
    return records_deleted


def delete_hard_drive_only_records() -> int:
    """Deletes records which only have a value in the hard_drive_name field."""
    records_deleted = 0
    for record in SheetImport.objects.all().order_by("id"):
        combined_field_data = _get_combined_field_data(record)
        if combined_field_data == record.hard_drive_name:
            record.delete()
            records_deleted += 1
    return records_deleted


class Command(BaseCommand):
    help = "Clean up imported Digital Labs Google Sheet data"

    def handle(self, *args, **options) -> None:

        records_deleted = delete_empty_records()
        self.stdout.write(f"Empty records deleted: {records_deleted}")

        records_changed = set_hard_drive_names()
        self.stdout.write(f"Hard drive names set: {records_changed}")

        records_changed = set_file_folder_names()
        self.stdout.write(f"Folder names set: {records_changed}")

        # This must be done after some of the methods above, which rely on header info.
        records_deleted = delete_header_records()
        self.stdout.write(f"Header records deleted: {records_deleted}")

        records_deleted = delete_hard_drive_only_records()
        self.stdout.write(f"Hard drive only records deleted: {records_deleted}")
