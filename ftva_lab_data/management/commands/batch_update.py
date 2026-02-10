import pandas as pd

from django.core.management.base import BaseCommand
from pathlib import Path
from ftva_lab_data.models import SheetImport
from django.db.models import ForeignKey, ManyToManyField, DateField
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import InMemoryUploadedFile


def load_input_data(input_file: str | InMemoryUploadedFile) -> list[list[dict]]:
    """Load input data from the input file into a list of sheets,
    as an input file may contain multiple sheets .

    :param input_file: Path to the spreadsheet containing records to update, as an XLSX file,
        or an InMemoryUploadedFile object passed from a Django form.
    :return: A list of lists of dicts, each representing a sheet with rows of input data.
    :raises ValueError: If the input file is not an XLSX file.
    """
    # Check extension if input_file is a string path
    if isinstance(input_file, str):
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
    :raises ValueError: If a related object does not exist in the database,
    or if no updates were made to any records.
    """
    records_updated = 0
    invalid_dates = []
    for row in input_data:
        record = SheetImport.objects.get(id=row["id"])
        record_changes = []
        many_to_many_changes = []
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

            try:
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
                        record_changes.append(
                            {
                                "field": field,
                                "from": current_value,
                                "to": update,
                            }
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
                        # Since we're adding an object to a many-to-many relationship,
                        # rather than setting a single foreign key as we do above,
                        # track these changes separately,
                        # and apply them later after all changes to record are collected.
                        many_to_many_changes.append(
                            {
                                "field": field,
                                "update": update,
                            }
                        )

                # Else if the field is a DateField,
                # try parsing the value as a date,
                # and collect invalid dates for later reporting.
                elif isinstance(field_object, DateField):
                    current_value = getattr(record, field)
                    if value == "":
                        update = None
                    else:
                        try:
                            update = pd.to_datetime(value).date()
                        except ValueError:
                            invalid_dates.append(
                                {
                                    "record_id": row["id"],
                                    "field": field,
                                    "value": value,
                                }
                            )
                            continue  # don't apply change if date is invalid
                    if current_value != update:
                        record_changes.append(
                            {
                                "field": field,
                                "from": current_value,
                                "to": update,
                            }
                        )

                # Otherwise, just set the value directly
                else:
                    # Replace any empty strings in `file_name` with "NO FILE NAME"
                    if field == "file_name" and value == "":
                        value = "NO FILE NAME"
                    # Coerce current database value to string for comparison
                    current_value = str(getattr(record, field))
                    if current_value != value:
                        record_changes.append(
                            {
                                "field": field,
                                "from": current_value,
                                "to": value,
                            }
                        )
            except ObjectDoesNotExist as e:
                # Handler expects a ValueError
                raise ValueError(
                    f"Error applying value {value} to field {field} on record {row['id']}: {e}"
                )

        # Continue if no changes made to current record
        if not record_changes and not many_to_many_changes:
            print(f"No changes made to record {row['id']}")
            continue
        # Save changes to record if not a dry run
        if not dry_run:
            # Apply record changes that can be set via `setattr()`...
            for change in record_changes:
                setattr(record, change["field"], change["to"])
            # then apply many-to-many changes,
            # which require use of `.add()` rather than `.setattr()`.
            # Note that `.add()` saves changes immediately.
            for change in many_to_many_changes:
                getattr(record, change["field"]).add(change["update"])
            # Now save record changes to the database.
            record.save()

        for change in record_changes:
            print(
                f"Record {row['id']} updated: "
                f"{change['field']} changed "
                f"from {change['from'] if change['from'] else '""'} "
                f"to {change['to'] if change['to'] else '""'}"
            )
        for change in many_to_many_changes:
            print(
                f"Record {row['id']} updated: "
                f"{change['update']} added to {change['field']}"
            )
        records_updated += 1

    # Report on invalid dates here so as not to prevent other valid changes from being applied
    if invalid_dates:
        report_lines = [
            f"Record {invalid_date['record_id']} {invalid_date['field']} {invalid_date['value']}"
            for invalid_date in invalid_dates
        ]
        raise ValueError(
            "Some date values could not be applied:\n" + "\n".join(report_lines)
        )

    if records_updated == 0:
        raise ValueError("All inputs match existing records; no updates to apply.")
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
