import json
import pandas as pd
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport


class Command(BaseCommand):
    help = "Convert Digital Labs Google Sheet (Excel) data to a JSON fixture."

    def _get_field_names(self, sheet_id: str) -> list[str]:
        """Returns a list of the `SheetImport` model fields expected for data coming from
        `sheet_id`.  These must be in the same order that the source data will be, as these
        serve as the mapping for source data with inconsistent column headers.

        :param sheet_id: The generic name of the data source to be mapped.
        :return: A list of strings representing the relevant `SheetImport` field names.
        """

        field_names = []
        if sheet_id == "main_sheet":
            # Get all field names from SheetImport model, except for a few specific ones
            # which are not in the source data.  This is slightly fragile, as adding new
            # fields to SheetImport will affect this; I added a comment to the model definition
            # warning that excluded_fields must be updated if fields are added to the model.
            # I still prefer this approach to explicitly naming all 40+ fields here.
            excluded_fields = [
                "_state",
                "id",
                "hard_drive_barcode_id",  # special case handled when processing the data.
                "assigned_user_id",
                "carrier_a_location",
                "carrier_b_location",
            ]

            field_names = [
                key for key in SheetImport().__dict__ if key not in excluded_fields
            ]

        elif sheet_id == "hearst_sheet":
            # Only 7 fields in this source data (only 5 relevant ones, as the final 2
            # (NetApp and TruNas)) will not be imported.
            # The fields are in a different order, so be explicit here.
            field_names = [
                "carrier_a",
                "carrier_a_location",
                "file_folder_name",
                "file_name",
                "notes",
            ]

        return field_names

    def _get_sheet_data(self, file_name: str, sheet_name: str) -> list:
        """Reads data from a sheet in an Excel file.

        :param file_name: The name of the Excel file.
        :param sheet_name: The name of the sheet within the Excel file.
        :return rows: A list of rows, each containing the value.

        """
        df = pd.read_excel(file_name, sheet_name=sheet_name, dtype="string").fillna("")
        rows = df.values.tolist()
        self.stdout.write(f"Read {len(rows)} rows from {file_name} / {sheet_name}")
        return rows

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "-f",
            "--file_name",
            type=str,
            required=True,
            help="Name of the Excel file with DL data",
        )

    def handle(self, *args, **options) -> None:
        file_name = options["file_name"]
        # Process all specified sheets together, always;
        # sheet names needed to read data from Excel are mapped here
        # to generic identifiers used elsewhere in the program.
        sheet_names = {
            "main_sheet": "LTO-Backup",
            "hearst_sheet": "Hearst ML Tapes",
        }

        records = []
        for sheet_id, sheet_name in sheet_names.items():
            rows = self._get_sheet_data(file_name, sheet_name)
            field_names = self._get_field_names(sheet_id)

            # Loop through the rows of data, creating an object for all of the relevant ones.
            for _, row in enumerate(rows, start=1):
                # Copy all of the fields as-is, except for stripping leading / trailing whitespace.
                fields = {
                    field_name: row[field_number].strip()
                    for field_number, field_name in enumerate(field_names, start=0)
                }

                # Finally, put it in the format needed for a fixture to load later.
                record = {
                    "model": "ftva_lab_data.sheetimport",
                    "fields": fields,
                }
                records.append(record)

        output_file = "sheet_data.json"
        with open(output_file, "w") as f:
            json.dump(records, f, indent=2)

        self.stdout.write(
            f"Finished: Wrote {len(records)} records from all sheets to {output_file}."
        )
