import pandas as pd
from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from ftva_lab_data.models import SheetImport


def parse_status_info(status_info: str) -> tuple[int] | tuple:
    """Parse status info string into a list of `ItemStatus` IDs.

    :param status_info: The status info string as it comes from the Google Sheet.
    :return: A tuple of `ItemStatus` IDs, which can be empty.
    """
    # Begin by checking if the status_info is empty or NaN
    if not status_info or pd.isna(status_info):
        # If it is empty or NaN, return an empty tuple
        return ()

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


def match_record(row: pd.Series) -> QuerySet[SheetImport]:
    """Try to get a matching `SheetImport` object using data from the Google Sheet.

    :param row: A Pandas Series representing a row of data from the Google Sheet.
    :return: A Django QuerySet with 0 or more records matching the relevant row data.
    """

    # These three fields alone uniquely match most (6460 out of 6741)
    # of the unique rows with status info in the `Copy of DL` sheet.
    # Using `filter()` over `get()` provides more flexibility to operate
    # on the return value in the calling `handle` function.
    file_folder = str(row["File Folder Name"]).strip()
    sub_folder = str(row["Sub Folder"]).strip()
    file_name = str(row["File Name"]).strip()

    return SheetImport.objects.filter(
        file_folder_name=file_folder,
        sub_folder_name=sub_folder,
        file_name=file_name,
    )


def get_tapes_data(
    file_name: str, process_inventory: bool, process_status: bool
) -> pd.DataFrame:
    """Load data from `file_name` and update it based on other parameters.

    :param file_name: Path to the Excel file from which Pandas will read data.
    :param process_inventory: Whether updates based on inventory number should be done.
    :param process_status: Whether updates based on status should be done.
    :return tapes_data: A Pandas DataFrame with updated data, ready for comparison with
      the database.
    """

    tapes_data = pd.read_excel(
        file_name,
        sheet_name="Tapes(row 4560-24712)",  # NOTE: sheet name is hard-coded here
    )

    # Provide total row count for tapes data
    total_rows = len(tapes_data.index)
    print(f"There are {total_rows} rows in source data.")

    # # Count duplicated rows, then drop them
    duplicate_count = tapes_data.duplicated().sum()
    print(f"Found {duplicate_count} duplicated rows in source data. Dropping them...")
    tapes_data.drop_duplicates(inplace=True)

    # Fill NA values with empty string, to avoid type issues with Django.
    # Being explicit with columns, because Pandas complains otherwise.
    tapes_data.fillna(
        {"File Folder Name": "", "Sub Folder": "", "File Name": ""}, inplace=True
    )

    # Prepare to drop rows and create columns as needed
    drop_na_cols = []
    if process_inventory:
        drop_na_cols.append("Inventory_no")
    if process_status:
        drop_na_cols.append("Requires Manual Intervention")

    # Drop rows missing required info
    if drop_na_cols:
        missing_count = tapes_data[drop_na_cols].isna().all(axis=1).sum()
        print(
            f"Found {missing_count} rows missing all of {drop_na_cols} in source data. ",
            "Dropping them...",
        )
        tapes_data.dropna(subset=drop_na_cols, how="all", inplace=True)

    # Create new columns as needed
    if process_inventory:
        tapes_data["inventory_number"] = tapes_data["Inventory_no"].apply(
            lambda x: str(x).strip() if pd.notna(x) else ""
        )
    if process_status:
        tapes_data["status_ids"] = tapes_data["Requires Manual Intervention"].apply(
            parse_status_info
        )

    return tapes_data


class Command(BaseCommand):
    help = (
        "Import status and inventory number information from "
        "`Copy of DL Sheet_10_18_2024` Google Sheet"
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "-f",
            "--file_name",
            type=str,
            required=True,
            help="Path to XLSX copy of Google Sheet",
        )
        parser.add_argument(
            "-i",
            "--inventory_numbers",
            action="store_true",
            help="If set, imports inventory numbers from the sheet",
        )
        parser.add_argument(
            "-s",
            "--status_info",
            action="store_true",
            help="If set, imports status info from the sheet",
        )

    def handle(self, *args, **options) -> None:

        file_name: str = options["file_name"]

        # Determine which columns to process.
        process_inventory: bool = options["inventory_numbers"]
        process_status: bool = options["status_info"]

        # User must provide at least one of the inventory_numbers / status_info arguments,
        # else there's nothing to update.
        if not process_inventory and not process_status:
            raise ValueError(
                "At least one of --inventory_numbers or --status_info must be used."
            )

        tapes_data = get_tapes_data(file_name, process_inventory, process_status)
        remaining_records_count = len(tapes_data.index)
        print(
            f"There are {remaining_records_count} remaining rows.",
            "Attempting to match them to SheetImport records...",
        )

        records_updated = 0
        multiple_matches = []
        no_matches = []
        changed_inventory_numbers = []
        for _, row in tapes_data.iterrows():
            matched_records = match_record(row)
            count = matched_records.count()

            if count == 1:
                record = matched_records.first()
                if process_inventory:
                    # If the record already has an inventory number, and it is different
                    # from the one in the sheet, add it to the report with before and after values.
                    if (
                        record.inventory_number
                        and record.inventory_number != row["inventory_number"]
                    ):
                        changed_inventory_numbers.append(
                            {
                                "file_folder_name": record.file_folder_name,
                                "sub_folder_name": record.sub_folder_name,
                                "file_name": record.file_name,
                                "before": record.inventory_number,
                                "after": row["inventory_number"],
                            }
                        )
                    record.inventory_number = row["inventory_number"]
                    record.save()
                if process_status:
                    # Updating with many-to-many with .set() saves automatically.
                    record.status.set(row["status_ids"])
                records_updated += 1

            if count > 1:
                multiple_matches.append(row)

            if count == 0:
                no_matches.append(row)

        print(f"{records_updated} records updated")
        print(f"{len(multiple_matches)} rows returned more than one match")
        print(f"{len(no_matches)} rows returned no match")
        if process_inventory:
            print(
                f"{len(changed_inventory_numbers)} records had changed inventory numbers"
            )

        report_filename = "import_status_inventory_no_report.xlsx"
        print(f"Writing report to {report_filename}...")
        with pd.ExcelWriter(report_filename) as writer:
            pd.DataFrame(multiple_matches).to_excel(
                writer, sheet_name="multiple_matches", index=False
            )
            pd.DataFrame(no_matches).to_excel(
                writer, sheet_name="no_matches", index=False
            )
            if changed_inventory_numbers:
                pd.DataFrame(changed_inventory_numbers).to_excel(
                    writer, sheet_name="changed_inventory_numbers", index=False
                )
