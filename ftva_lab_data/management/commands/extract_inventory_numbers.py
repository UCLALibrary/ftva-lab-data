from django.core.management.base import BaseCommand
from django.db.models import QuerySet, Q
from ftva_lab_data.models import SheetImport

from pathlib import Path
from datetime import datetime
import re
import csv


def compile_regex() -> re.Pattern:
    """Return a compiled RegEx pattern for matching inventory numbers.

    NOTE: the pattern works in most cases, but will return false positives
    where the input contains a substring that syntactically matches pattern
    but is not actually a valid inventory number, according to FTVA
    e.g. "Title_T01ASYNC_Surround" matches T01, which is a valid pattern,
    but not an actual inventory number.

    :return: A compiled regex Pattern object.
    """

    regex_components = [
        r"(?<![A-Z])",  # pattern not preceded by capital letter, to mitigate false positives
        r"(?:M|T|DVD|FE|HFA|VA|XFE|XFF|XVE)",  # non-capturing group of 8 prefixes defined by FTVA
        r"\d{2,}",  # 2 or more digits, as many as possible
        r"(?:[A-Z](?![A-Za-z]))?",  # optional suffix 1 capital not followed by another letter
    ]

    return re.compile("".join(regex_components))


def remove_false_positives(unique_inventory_numbers: list) -> list:
    """Given a list of unique inventory numbers, returns the list with
    known false positive inventory numbers removed.

    NOTE: the list of known false-positives, i.e. strings that match the regex pattern
    but are known to not be actual inv #s, are hard-coded in this function.

    :param list unique_inventory_numbers: A list of unique inventory numbers.
    :return: The list of unique inventory numbers with known false-positives removed.
    """

    known_false_positives = ["T01", "FE3018T"]
    for false_positive in known_false_positives:
        if false_positive in unique_inventory_numbers:
            unique_inventory_numbers.remove(false_positive)

    return unique_inventory_numbers


def build_inventory_number_string(matches: list) -> str:
    """Given a list of regex matches, formats an inventory number output string
    according to FTVA specs, which require inventory numbers be unique and pipe-delimited.
    This function also removes

    :param list matches: A list of inventory number matches from a regex evaluation.
    :return: The prepared inventory number string, per FTVA specs.
    """

    # Uses dict.fromkeys() to get unique values while maintaining list order
    unique_inventory_numbers = list(dict.fromkeys(matches))
    unique_without_false_positives = remove_false_positives(unique_inventory_numbers)
    # per FTVA spec, provide pipe-delimited string
    # if multiple matches in a single input value
    return "|".join(unique_without_false_positives)


def extract_inventory_numbers(
    records: QuerySet, inventory_number_pattern: re.Pattern = compile_regex()
) -> list[SheetImport]:
    """Given a QuerySet of records without inventory numbers,
    extract any available inventory numbers matching the provided regex pattern
    from the path-like fields, then return a list of updated records.

    :param QuerySet records: A QuerySet of records with empty or invalid inventory numbers.
    :param re.Pattern inventory_number_pattern: A regex pattern for inventory numbers.
    :return: A list of updated SheetImport objects.
    """

    updated_records = []
    for record in records:
        # Inventory numbers are extracted from the path-like fields,
        # so concatenate them together here to match against
        path_string = "/".join(
            [record.file_folder_name, record.sub_folder_name, record.file_name]
        )

        matches = re.findall(inventory_number_pattern, path_string)
        if matches:
            inventory_number_string = build_inventory_number_string(matches)
            # Avoid updating records where building inv no string yields empty string
            if not inventory_number_string:
                continue
            record.inventory_number = inventory_number_string
            updated_records.append(record)

    return updated_records


def get_records_without_inventory_numbers() -> QuerySet:
    """Returns Django records that have empty or invalid inventory numbers.

    :return: A QuerySet of records with empty or invalid inventory numbers.
    """

    return SheetImport.objects.filter(
        # Filter for records where inventory number is empty string ("")
        # or contains the case-insensitive sub-string "invalid"
        Q(inventory_number__exact="")
        | Q(inventory_number__icontains="invalid")
    ).order_by("id")


def write_summary_to_file(updated_records: list[SheetImport], is_dry_run: bool) -> str:
    """Writes a summary report of the updated records
    in the form of a CSV file named `{SCRIPT_NAME}_{TIMESTAMP}.csv`.

    :param list[SheetImport] updated_records: A list of SheetImport objects
    with updated inventory numbers.
    :param bool is_dry_run: If True, mark summary as dry run, else mark it as live.
    :return: The filename for the output summary.
    """

    # Include relevant fields for FTVA staff reference
    summary_headers = [
        "id",
        "inventory_number",
        "file_folder_name",
        "sub_folder",
        "file_name",
    ]
    summary_rows = [summary_headers]
    for record in updated_records:
        summary_rows.append(
            [
                record.pk,
                record.inventory_number,
                record.file_folder_name,
                record.sub_folder_name,
                record.file_name,
            ]
        )

    filename_base = Path(__file__).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{filename_base}_{timestamp}.csv"
    if is_dry_run:
        summary_rows.insert(0, ["DRY RUN--NO RECORDS UPDATED"])
        output_filename = "DRY_RUN_" + output_filename
    with open(output_filename, "w") as output:
        csv_writer = csv.writer(output)
        csv_writer.writerows(summary_rows)

    return output_filename


class Command(BaseCommand):
    help = "Extract inventory numbers from path info for existing records."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry_run",
            help="Run in dry run mode. "
            "Returns a summary of changes that would be applied, "
            "but does not apply them.",
            action="store_true",
        )

    def handle(self, *args, **options) -> None:
        records_without_inv_nos = get_records_without_inventory_numbers()
        updated_records = extract_inventory_numbers(records_without_inv_nos)

        print(f"Total records to update: {len(updated_records)}")
        output_filename = write_summary_to_file(updated_records, options["dry_run"])

        if options["dry_run"]:
            print("Running in dry run mode...")
            print(f"Writing summary to {output_filename}")
            return

        print("Updating records...")
        updated_count = SheetImport.objects.bulk_update(
            updated_records, ["inventory_number"]
        )
        print(f"Successfully updated {updated_count} records.")
