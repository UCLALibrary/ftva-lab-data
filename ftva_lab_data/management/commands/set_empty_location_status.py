import logging
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport, ItemStatus

logger = logging.getLogger(__name__)


def set_empty_location_status() -> None:
    """Set the status of records with empty locations."""
    # Get all records where all of the location fields are empty:
    # hard_drive_location, carrier_a_location, and carrier_b_location.
    records = SheetImport.objects.filter(
        hard_drive_location="",
        carrier_a_location="",
        carrier_b_location="",
    )
    logger.info(f"Found {records.count()} records with empty locations.")

    # Filter out records that already have the 'Invalid vault' status
    records_to_update = records.exclude(status__status="Invalid vault")
    logger.info(
        f"Filtered down to {records_to_update.count()} records without 'Invalid vault' status."
    )
    invalid_vault_status = ItemStatus.objects.get(status="Invalid vault")
    for record in records_to_update:
        # Django's .add() method will save the change to the database automatically
        record.status.add(invalid_vault_status)
    logger.info(f"Added 'Invalid vault' status to {records_to_update.count()} records.")


class Command(BaseCommand):
    help = (
        "Set a status of 'Invalid vault' for all SheetImport records with an empty"
        " hard_drive_location, or an empty carrier_a_location AND an empty carrier_b_location."
    )

    def handle(self, *args, **options) -> None:
        set_empty_location_status()
