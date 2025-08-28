import logging
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport, ItemStatus
from simple_history.utils import bulk_update_with_history

logger = logging.getLogger(__name__)


def set_hard_drive_location() -> None:
    """Set the hard_drive_location field for all records with a value in hard_drive_name."""
    # Get all records where the hard_drive_name field has a value,
    # i.e. exclude empty strings.
    records = SheetImport.objects.exclude(hard_drive_name="")
    logger.info(f"Found {records.count()} records with a value in hard_drive_name.")

    # Get the "Invalid vault" status and a counter for later use.
    invalid_vault_status = ItemStatus.objects.get(status="Invalid vault")
    invalid_vault_count = 0

    # Set the hard_drive_location field to "217" for all matching records,
    # per instructions from FTVA.
    for record in records:
        record.hard_drive_location = "217"
        # If record has status "Invalid vault", remove it.
        if record.status.filter(status=invalid_vault_status).exists():
            record.status.remove(invalid_vault_status)
            invalid_vault_count += 1

    # Save the changes via history-aware bulk update.
    # The status field does not need to be included in the bulk update,
    # as the `remove()` method called above directly modifies the through table
    # between SheetImport and ItemStatus, and does not need to be saved.
    bulk_update_with_history(
        records,
        SheetImport,
        ["hard_drive_location"],
    )
    logger.info(f"Set hard_drive_location for {records.count()} records.")

    # Log the number of records that had the "Invalid vault" status removed.
    logger.info(f"Removed 'Invalid vault' status from {invalid_vault_count} records.")


class Command(BaseCommand):
    help = (
        "Sets value of hard_drive_location field for all records with a value in hard_drive_name. "
        "Intended as a one-off command to bulk update the relevant data."
    )

    def handle(self, *args, **options) -> None:
        set_hard_drive_location()
