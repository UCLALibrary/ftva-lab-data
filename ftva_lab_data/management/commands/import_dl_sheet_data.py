import pandas as pd
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport


class Command(BaseCommand):
    help = "Import Digital Labs Google Sheet data"

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
        print(len(rows))
