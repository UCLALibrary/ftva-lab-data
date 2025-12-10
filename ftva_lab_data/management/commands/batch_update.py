import pandas as pd

from django.core.management.base import BaseCommand
from pathlib import Path
from ftva_lab_data.models import SheetImport
from django.db.models import ForeignKey, ManyToManyField


def load_input_data(input_file: str) -> list[list[dict]]:
    """Load input data from the input file into a list of sheets,
    as an input file may contain multiple sheets .

    :param input_file: Path to the spreadsheet containing records to update, as an XLSX file.
    :return: A list of lists of dicts, each representing a sheet with rows of input data.
    :raises ValueError: If the input file is not an XLSX file.
    """
    input_suffix = Path(input_file).suffix
    if input_suffix != ".xlsx":
        raise ValueError(f"Unsupported file type: {input_suffix}")
    # `sheet_name=None` reads all sheets
    sheets = pd.read_excel(input_file, sheet_name=None)
    # Convert each sheet DataFrame to a list of dicts, each representing a sheet of input data,
    # filling NA with empty string to avoid type issues with Django
    return [
        sheet_data.fillna("").to_dict(orient="records")
        for sheet_data in sheets.values()
    ]


def validate_input_data(records: list[dict]) -> None:
    """Validate that the fields in the input data exist in the SheetImport model,
    and that each ID exists in the database.

    :param records: A list of dicts, each representing a row of input data.
    :raises ValueError: If the fields in the input data do not exist on the SheetImport model,
    or if the targeted record IDs do not exist in the database.
    """
    model_fields = [field.name for field in SheetImport._meta.get_fields()]
    fields_not_found = []
    ids_not_found = []
    for record in records:
        for field in record.keys():
            # Input data may have foreign key fields with an "_id" suffix,
            # so remove it to get the field name.
            if field.endswith("_id"):
                field = field.replace("_id", "")
            if field not in model_fields:
                fields_not_found.append(field)
            if field == "id":
                # Need a `try-except` here, since `get()` raises a `DoesNotExist` exception
                # if the record is not found, rather than returning `None`.
                try:
                    SheetImport.objects.get(id=record["id"])
                except SheetImport.DoesNotExist:
                    ids_not_found.append(record["id"])
    if fields_not_found:
        raise ValueError(
            f"Input validation failed: "
            f"fields {', '.join(set(fields_not_found))} do not exist in database."
        )
    if ids_not_found:
        raise ValueError(
            f"Input validation failed: "
            f"record IDs {', '.join(set(ids_not_found))} do not exist in database."
        )
    return


def batch_update(input_data: list[dict], dry_run: bool) -> int:
    """Batch update the SheetImport model, using the provided spreadsheet.

    :param input_data: A list of dicts, each representing a row of input data.
    :param dry_run: If True, runs the update but does not save the changes to the database.
    :return: The number of records updated.
    """
    records_updated = 0
    for row in input_data:
        record = SheetImport.objects.get(id=row["id"])
        has_changes = False
        for field, value in row.items():
            # Guard against changes to IDs or UUIDs
            if field.lower() in ["id", "pk", "uuid"]:
                continue
            # Input data may have ForeignKey or ManyToMany fields
            # with an "_id" suffix, so remove it to get the field name.
            if field.endswith("_id"):
                field = field.replace("_id", "")

            # Now get the field object itself
            field_object = SheetImport._meta.get_field(field)

            # If the field is a ForeignKey, get the related object and set it
            if isinstance(field_object, ForeignKey):
                current_value = getattr(record, field)
                # Empty string should nullify ForeignKey field
                if value == "":
                    update = None
                else:
                    update = field_object.related_model.objects.get(
                        # Using case-insensitive startswith because
                        # input data may not exactly match the database value.
                        # Same below for ManyToManyField.
                        **{f"{field}__istartswith": value}
                    )
                if current_value != update:
                    has_changes = True
                    setattr(record, field, update)
                    print(
                        f"Record {row['id']} updated: "
                        f"{field} changed from {current_value} to {update}"
                    )

            # Else if the field is a ManyToManyField,
            # get the related object and add it to the many-to-many relationship.
            elif isinstance(field_object, ManyToManyField):
                current_related_objects = getattr(record, field).all()
                # Nothing should be done for empty string values on ManyToMany fields
                if value == "":
                    update = None
                else:
                    update = field_object.related_model.objects.get(
                        **{f"{field}__istartswith": value}
                    )
                # Only apply update if there is one and it's not already in the m2m relationship
                if update and update not in current_related_objects:
                    has_changes = True
                    # Need to use `getattr().add()` here rather than `setattr()`,
                    # since we're adding an object to a many-to-many relationship,
                    # rather than setting a single foreign key as we do above.
                    # `add()` immediately saves the change to the database though,
                    # so we need an additional `dry_run` check.
                    if not dry_run:
                        getattr(record, field).add(update)
                    print(f"Record {row['id']} updated: " f"added {update} to {field}")

            # Otherwise, just set the value directly
            else:
                # Replace any empty strings in `file_name` with "NO FILE NAME"
                if field == "file_name" and value == "":
                    value = "NO FILE NAME"
                current_value = getattr(record, field)
                if current_value != value:
                    has_changes = True
                    setattr(record, field, value)
                    print(
                        f"Record {row['id']} updated: "
                        f"{field} changed from {current_value} to {value}"
                    )

        # Compare the original record to the updated record
        if not has_changes:
            print(f"No changes were made to record {row['id']}")
            continue
        if not dry_run:
            record.save()
        records_updated += 1

    return records_updated


class Command(BaseCommand):
    help = "Runs a batch update on the SheetImport model, "
    "using a spreadsheet as input."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "-i",
            "--input_file",
            type=str,
            required=True,
            help="Path to the spreadsheet containing records to update, as an XLSX file.",
        )
        parser.add_argument(
            "--dry_run",
            action="store_true",
            help="If set, runs the update but does not save the changes to the database.",
            required=False,
            default=False,
        )

    def handle(self, *args, **options) -> None:
        input_file = options["input_file"]
        input_data = load_input_data(input_file)

        dry_run = options["dry_run"]

        print(
            f"{'#' * 20} STARTING BATCH UPDATE "
            f"{'(DRY RUN)' if dry_run else ''}{'#' * 20}"
        )
        print(f"Loaded {len(input_data)} sheets from {input_file}")
        total_records_updated = 0
        for i, sheet_data in enumerate(input_data, start=1):
            sheet_number = f"{i} of {len(input_data)}"
            try:
                print(f"Validating input data for sheet {sheet_number}")
                validate_input_data(sheet_data)

                print(f"Applying updates from sheet {sheet_number}")
                records_updated = batch_update(sheet_data, dry_run)

                print(f"Updated {records_updated} records from sheet {sheet_number}")
                total_records_updated += records_updated
            except ValueError as e:
                print(e)
                return
        print(f"Total records updated: {total_records_updated}")
        print(
            f"{'#' * 20} BATCH UPDATE COMPLETE "
            f"{'(DRY RUN)' if dry_run else ''}{'#' * 20}"
        )
