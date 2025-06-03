from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport


def delete_empty_records() -> int:
    """Deletes SheetImport records which contain no data other than
    the system-assigned id.
    """
    records_affected = 0
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
            records_affected += 1
    return records_affected


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
        self.stdout.write(f"Records deleted: {records_deleted}")
