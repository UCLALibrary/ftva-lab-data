import pandas as pd
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport


def parse_status_info(status_info: str) -> tuple[int]:
    """Parse status info string into a list of `ItemStatus` IDs.

    :param status_info: The status info string as it comes from the Google Sheet.
    :return: A tuple of `ItemStatus` IDs.
    """

    # Column A in the Google Sheet uses key sub-strings consistently
    # to describe the status of the record.
    # Below is a map between these sub-strings
    # and the IDs of the corresponding `ItemStatus` objects.
    # This map is used to parse a normalized status
    # from the `status_info` string passed in as a parameter.
    status_info_to_model_id_map = [
        (
            "Inventory number in filename is incorrect",
            1,
        ),
        ("Duplicated in Source Data", 2),
        ("invalid vault", 3),
        ("invalid inventory_no", 4),
        ("Presence of multiple Inventory_nos", 5),
        (
            "Multiple corresponding Inventory_no in PD",
            6,
        ),
    ]

    status_id_list = []
    for substring, status_id in status_info_to_model_id_map:
        if substring.lower() in status_info.lower():
            status_id_list.append(status_id)
    # Pandas wants a hashable type to make dropping duplicates possible,
    # so return a tuple rather than a list
    return tuple(status_id_list)


def match_record(
    file_name: str, sub_folder: str, file_folder_name: str
) -> tuple[SheetImport | None, str]:
    """Try to get a matching `SheetImport` object using data from the Google Sheet."""

    # First try uses file name only
    try:
        record = SheetImport.objects.get(file_name=file_name)
        return record, "unique match"
    # Keep trying if these exceptions are raised
    except (SheetImport.MultipleObjectsReturned, SheetImport.DoesNotExist):
        pass

    # Second try uses file name and sub-folder
    try:
        record = SheetImport.objects.get(
            file_name=file_name, sub_folder_name=sub_folder
        )
        return record, "unique match"
    except (SheetImport.MultipleObjectsReturned, SheetImport.DoesNotExist):
        pass

    # Third and final try uses file name, sub-folder, and folder name
    try:
        record = SheetImport.objects.get(
            file_name=file_name,
            sub_folder_name=sub_folder,
            file_folder_name=file_folder_name,
        )
        return record, "unique match"
    except SheetImport.MultipleObjectsReturned:
        return None, "multiple matches"
    except SheetImport.DoesNotExist:
        pass

    return None, "no matches"


class Command(BaseCommand):
    help = "Import status information from `Copy of DL Sheet_10_18_2024` Google Sheet"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "-f",
            "--file_name",
            type=str,
            required=True,
            help="Path to XLSX copy of Google Sheet",
        )

    def handle(self, *args, **options) -> None:
        file_name = options["file_name"]
        tapes_data = pd.read_excel(
            file_name, sheet_name="Tapes(row 4560-24712)"
        )  # NOTE: sheet name is hard-coded here

        # Create a new column of status IDs parsed from status information
        tapes_data["status_ids"] = (
            tapes_data["Requires Manual Intervention"]
            .fillna("")
            .apply(parse_status_info)
        )

        # Drop completely duplicate rows, if any
        tapes_data.drop_duplicates(inplace=True)

        # Call `match_record` for each row in DataFrame
        # and set status on `SheetImport` records only if unique match.
        objects_updated = 0
        multiple_objects_returned = 0
        does_not_exist = 0
        for _, row in tapes_data.iterrows():
            record, result = match_record(
                row["File Name"], row["Sub Folder"], row["File Folder Name"]
            )

            if record and result == "unique match":
                record.status.set(row["status_ids"])
                objects_updated += 1

            if result == "multiple matches":
                multiple_objects_returned += 1

            if result == "no matches":
                does_not_exist += 1

        print(f"{objects_updated} objects found")
        print(f"{multiple_objects_returned} objects returned more than one")
        print(f"{does_not_exist} objects do not exist")
