import re
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport


def _is_header_record(record: SheetImport) -> bool:
    """Determines whether a record contains a header row from the imported data."""
    return record.file_folder_name == "File Folder Name"


def delete_empty_records() -> int:
    """Deletes SheetImport records which contain no data other than
    the system-assigned id.
    """
    records_changed = 0
    for record in SheetImport.objects.all().order_by("id"):
        # All SheetImport fields are string (CharField) except the system-assigned id
        # and the foreign key relation to assigned_user (which does not matter at this stage
        # for imported, empty records).
        # Combine all of these string fields into one big string.
        combined_field_data = "".join(
            [
                getattr(record, field.name)
                for field in record._meta.get_fields()
                if field.name not in ("id", "assigned_user")
            ]
        )
        # If the resulting string is empty (or just spaces), delete the record.
        if combined_field_data.strip() == "":
            record.delete()
            records_changed += 1

    return records_changed


def set_hard_drive_names() -> int:
    """Sets the hard drive name for rows which can be associated with hard drives,
    based on the presence of a specific header row value.
    """
    records_deleted = 0
    current_drive_name = None
    for record in SheetImport.objects.all().order_by("id"):
        # Check for value indicating this is a hard drive name.
        if re.match("Digital[ ]?Lab [0-9]", record.hard_drive_name):
            current_drive_name = record.hard_drive_name
        else:
            # Is this a header row?
            if _is_header_record(record):
                # Clear the value so we know to stop if appropriate.
                current_drive_name = None
            # Otherwise, if we still have a value, apply it to the current row.
            else:
                if current_drive_name:
                    record.hard_drive_name = current_drive_name
                    record.save()
                    records_deleted += 1

    return records_deleted


def delete_header_records() -> int:
    """Deletes header rows that are embedded throughout the original imported data."""
    records_deleted = 0
    for record in SheetImport.objects.all().order_by("id"):
        if _is_header_record(record):
            record.delete()
            records_deleted += 1
    return records_deleted


class Command(BaseCommand):
    help = "Clean up imported Digital Labs Google Sheet data"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "-d",
            "--dry_run",
            action="store_true",
            help="Dry run only: show what would be changed",
        )

    def handle(self, *args, **options) -> None:
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("Performing dry run")

        records_deleted = delete_empty_records()
        self.stdout.write(f"Empty records deleted: {records_deleted}")

        records_changed = set_hard_drive_names()
        self.stdout.write(f"Hard drive names set: {records_changed}")

        # This must be done after set_hard_drive_names(), which uses header info.
        records_deleted = delete_header_records()
        self.stdout.write(f"Header records deleted: {records_deleted}")
