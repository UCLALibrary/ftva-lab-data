import re
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport


def get_tape_info_parts(tape_info: str) -> tuple:
    """Determines whether the given tape_info is valid, per the following rules:

    Starts with a tape id (required).  This is 6 or 7 alphanumeric characters:
    * 6 digits (e.g., 000022, 820020)
    * 3 uppercase letters and 3 digits (e.g., AAB952, AAD075)
    * 4 uppercase letters and 2 digits (e.g., CLNU00, CLNU04)
    * 1 uppercase letter and 6 digits (e.g., M258178, T161092)

    The tape id may be followed by other information, including other tape ids, notes,
    and vault locations.  However, for this project, any additional information must be
    identifiable as a single vault location.  This must follow the valid tape id:
    * 0 or more spaces
    * (in vault) OR (to vault)
    * 1 or more spaces
    * A valid vault location

    Vault locations consist of 12 characters, always in this format:
    * S217-01
    * 1 uppercase letter
    * 1 space or - # Should be a hyphen; match both, but update when saving the data.
    * 2 digits
    * 1 uppercase letter

    Examples of valid inputs:
    * 820001
    * AAB963
    * 000027 (in vault) S217-01A 11C
    * CLNU00 (in vault) S217-01A 11A
    * M265154 (to vault) S217-01A-13D

    Examples of invalid inputs:
    * 000028 & AAB967
    * AAC018- LTO Corrupted- Will not mount (4/25/2018)
    * CLNU02/AAC062 (in vault) S217-01A 11A
    * Not on LTO AAB969
    * M258145 Part 01 of 03 (to vault) S217-01A-13C

    Returns a tuple of (tape_id, vault_location), or None.
    """

    # Trim leading & trailing spaces from input.
    tape_info = tape_info.strip()

    # These must always be at the start of the tape_info input.
    tape_id_formats = [
        r"^\d{6}",
        r"^[A-Z]{3}\d{3}",
        r"^[A-Z]{4}\d{2}",
        r"^[A-Z]{1}\d{6}",
    ]
    tape_id_format = r"|".join(tape_id_formats)
    vault_designator_format = r"(\(in vault\)|\(to vault\))"
    vault_location_format = r"(S217-01[A-Z]{1}[ -]{1}\d{2}[A-Z]{1})"

    combined_format = "".join(
        [
            rf"({tape_id_format})",
            r"\s*",  # 0 or more spaces
            vault_designator_format,
            r"\s*",  # 0 or more spaces
            vault_location_format,
        ]
    )

    # For matching tape_id only, input must fully match, so change delimiter to $|
    # (e.g., ^A$|^B$|^C, not ^A|^B|^C).  Final $ will be added when compiling the pattern.
    tape_id_format_standalone = tape_id_format.replace("|", "$|")

    # tape_info input is valid if it fully matches either tape_id_format alone,
    # or combined_format.
    tape_id_pattern = re.compile(rf"^{tape_id_format_standalone}$")
    combined_pattern = re.compile(rf"^{combined_format}$")

    # Check simple cases first.
    matches = tape_id_pattern.search(tape_info)
    if matches:
        # tape_id_pattern finds only a tape_id (if anything);
        # return a tuple of (tape_id, None) for the absent vault location.
        return (matches.group(0), None)

    # If no simple case match, try the combined one.
    matches = combined_pattern.search(tape_info)
    if matches:
        # There should only be 1 group, a tuple of (tape_id, vault_designator, vault_location).
        # Return a tuple of (tape_id, vault_location).
        return matches.group(1, 3)

    # Nothing matches.
    return (None, None)


def process_carrier_fields(
    carrier_field_name: str, update_records: bool, report_problems: bool
) -> int:
    """Processes carrier fields associated with carrier_field_name,
    either updating or reporting on problems.
    If update_records is True, the database will be updated when valid data is found.
    If report_problems is True, info about invalid data will be written to stdout.

    Returns the number of records updated.
    """
    carrier_location_field_name = f"{carrier_field_name}_location"
    tape_id: str = ""
    vault_location: str = ""
    records_changed = 0
    # Use a dynamic filter to find records which don't have an empty carrier field.
    for record in SheetImport.objects.exclude(**{carrier_field_name: ""}).order_by(
        "id"
    ):
        tape_info = getattr(record, carrier_field_name)
        tape_id, vault_location = get_tape_info_parts(tape_info)
        if tape_id:
            if update_records:
                setattr(record, carrier_field_name, tape_id)
                if vault_location:
                    # Update spaces to be hyphens.
                    vault_location = vault_location.replace(" ", "-")
                    setattr(record, carrier_location_field_name, vault_location)
                record.save()
                records_changed += 1
        else:
            if report_problems:
                print(
                    f"{carrier_field_name.capitalize()} unsupported format: #"
                    f"{record.id}: {tape_info}"
                )

    return records_changed


class Command(BaseCommand):
    help = "Clean up imported Digital Labs Google Sheet tape information"

    def add_arguments(self, parser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--report_problems",
            action="store_true",
            help="Report on tape (carrier) fields which can't be updated",
        )
        group.add_argument(
            "--update_records",
            action="store_true",
            help="Update records",
        )

    def handle(self, *args, **options) -> None:

        report_problems = options["report_problems"]
        update_records = options["update_records"]

        for carrier_field_name in ["carrier_a", "carrier_b"]:
            records_changed = process_carrier_fields(
                carrier_field_name, update_records, report_problems
            )
            self.stdout.write(
                f"Carrier info updated for {carrier_field_name}: {records_changed}"
            )
