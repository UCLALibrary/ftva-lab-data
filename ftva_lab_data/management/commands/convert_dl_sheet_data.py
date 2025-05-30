import json
import pandas as pd
import re
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport


class Command(BaseCommand):
    help = "Import Digital Labs Google Sheet data"

    def _get_field_names(self) -> list[str]:
        """Returns a list of the field names for the SheetImport model.  Field names
        are in the same order they're defined on the model, which is the same order they
        occur in the Google sheet.
        """
        # Ignore model _state, id (part of model but not in source data), and hard_drive_barcode_id
        # (which will be handled as a special case when reading the data).
        field_names = [
            key
            for key in SheetImport().__dict__
            if key not in ["_state", "id", "hard_drive_barcode_id"]
        ]
        return field_names

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "-f",
            "--file_name",
            type=str,
            required=True,
            help="Name of the Excel file with data",
        )
        parser.add_argument(
            "-s",
            "--sheet_name",
            type=str,
            required=True,
            help="Name of the sheet to import",
        )

    def handle(self, *args, **options) -> None:
        file_name = options["file_name"]
        sheet_name = options["sheet_name"]
        df = pd.read_excel(file_name, sheet_name=sheet_name, dtype="string").fillna("")
        rows = df.values.tolist()
        self.stdout.write(f"Read {len(rows)} rows from {file_name} / {sheet_name}")

        records = []
        field_names = self._get_field_names()
        # Loop through the rows of data, creating an object for all of the relevant ones.
        for row_number, row in enumerate(rows, start=1):
            if row_number % 1000 == 0:
                self.stdout.write(f"Processed {row_number} rows")
            # Always ignore pseudo-header rows, which are repeated in the source document
            # and are inconsistent.  These can be identified by a specific value in column D,
            # which is always the same. (Column A header is not completely consistent....)
            if row[3] == "File Folder Name":
                continue

            # Copy all of the fields as-is, to start
            fields = {
                field_name: row[field_number]
                for field_number, field_name in enumerate(field_names, start=0)
            }
            # Make changes as needed
            # re.match("Digital[ ]?Lab [0-9]"

            # Finally, put it in the format needed for a fixture to load later.
            record = {
                "model": "ftva_lab_data.sheetimport",
                "pk": row_number,
                "fields": fields,
            }
            records.append(record)

        self.stdout.write(f"Finished: processed {len(records)} records")

        with open("sheet_data.json", "w") as f:
            json.dump(records, f, indent=2)
