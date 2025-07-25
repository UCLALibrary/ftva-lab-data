import logging
from django.core.management.base import BaseCommand
from ftva_lab_data.models import SheetImport, ItemStatus

logger = logging.getLogger(__name__)


def set_empty_inv_no_status() -> None:
    # Get all SheetImport records with an empty inventory number
    records = SheetImport.objects.filter(inventory_number="")
    if not records.exists():
        logger.info("No records with empty inventory number found.")
        return
    logger.info(f"Found {records.count()} records with empty inventory number.")

    # Filter out records that already have the 'Invalid inv no' status
    records_to_update = records.exclude(status__status="Invalid inv no")
    logger.info(
        f"Filtered down to {records_to_update.count()} records without 'Invalid inv no' status."
    )

    invalid_inv_no_status = ItemStatus.objects.get(status="Invalid inv no")
    for record in records_to_update:
        # Django's .add() method will save the change to the database automatically
        record.status.add(invalid_inv_no_status)

    logger.info(
        f"Added 'Invalid inv no' status to {records_to_update.count()} records."
    )


class Command(BaseCommand):
    help = (
        "Set a status of 'Invalid inv no' "
        "for all SheetImport records with an empty inventory number."
    )

    def handle(self, *args, **options) -> None:
        set_empty_inv_no_status()
