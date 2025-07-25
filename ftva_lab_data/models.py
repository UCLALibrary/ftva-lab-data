from django.db import models
from django.conf import settings
from simple_history.models import HistoricalRecords


class SheetImport(models.Model):
    """Represents rows of the original DL Google Sheet.
    By design, this model does not attempt to validate data;
    it just stores the original source data, almost entirely as-is.

    WARNING: If you add any fields to this model, be sure to add them to the
    "excluded" list in `convert_dl_sheet_data._get_field_names()`.
    """

    # By default, null=False and blank=False.
    hard_drive_name = models.CharField(max_length=100, blank=True)
    # These 3 "id" fields seem to often contain longer notes...
    # dml_lto_tape_id is now carrier_a; arsc_lto_tape_id is now carrier_b
    carrier_a = models.CharField(max_length=100, blank=True)
    carrier_a_location = models.CharField(max_length=25, blank=True)
    carrier_b = models.CharField(max_length=100, blank=True)
    carrier_b_location = models.CharField(max_length=25, blank=True)
    hard_drive_barcode_id = models.CharField(max_length=100, blank=True)
    file_folder_name = models.CharField(max_length=200, blank=True)
    sub_folder_name = models.CharField(max_length=200, blank=True)
    file_name = models.CharField(max_length=200, blank=False)
    inventory_number = models.CharField(max_length=100, blank=True)
    source_inventory_number = models.CharField(max_length=50, blank=True)
    source_barcode = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=250, blank=True)
    job_number = models.CharField(max_length=25, blank=True)
    source_type = models.CharField(max_length=25, blank=True)
    resolution = models.CharField(max_length=25, blank=True)
    compression = models.CharField(max_length=25, blank=True)
    file_format = models.CharField(max_length=25, blank=True)
    # This currently is a string
    file_size = models.CharField(max_length=50, blank=True)
    frame_rate = models.CharField(max_length=25, blank=True)
    total_running_time = models.CharField(max_length=25, blank=True)
    source_frame_rate = models.CharField(max_length=25, blank=True)
    aspect_ratio = models.CharField(max_length=25, blank=True)
    color_bit_depth = models.CharField(max_length=25, blank=True)
    color_type = models.CharField(max_length=25, blank=True)
    frame_layout = models.CharField(max_length=25, blank=True)
    sample_structure = models.CharField(max_length=25, blank=True)
    sample_rate = models.CharField(max_length=25, blank=True)
    capture_device_make_and_model = models.CharField(max_length=50, blank=True)
    capture_device_settings = models.CharField(max_length=50, blank=True)
    date_capture_completed = models.CharField(max_length=50, blank=True)
    video_edit_software_and_settings = models.CharField(max_length=50, blank=True)
    date_edit_completed = models.CharField(max_length=50, blank=True)
    color_grading_software = models.CharField(max_length=50, blank=True)
    color_grading_settings = models.CharField(max_length=50, blank=True)
    audio_file_format = models.CharField(max_length=50, blank=True)
    date_audio_edit_completed = models.CharField(max_length=50, blank=True)
    remaster_platform = models.CharField(max_length=50, blank=True)
    remaster_software = models.CharField(max_length=50, blank=True)
    remaster_settings = models.CharField(max_length=50, blank=True)
    date_remaster_completed = models.CharField(max_length=50, blank=True)
    subtitles = models.CharField(max_length=50, blank=True)
    watermark_type = models.CharField(max_length=50, blank=True)
    security_data_encrypted = models.CharField(max_length=50, blank=True)
    migration_or_preservation_record = models.CharField(max_length=50, blank=True)
    hard_drive_location = models.CharField(max_length=50, blank=True)
    date_job_started = models.CharField(max_length=50, blank=True)
    date_job_completed = models.CharField(max_length=50, blank=True)
    general_entry_cataloged_by = models.CharField(max_length=50, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    status = models.ManyToManyField(
        "ItemStatus", blank=True, related_name="sheet_imports"
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sheet_imports",
    )
    date_of_ingest = models.DateField(blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"id: {self.id} --- file: {self.file_name} --- title: {self.title}"

    @property
    def assigned_user_full_name(self) -> str:
        return self.assigned_user.get_full_name()

    @property
    def carrier_a_with_location(self) -> str:
        return (
            f"{self.carrier_a} ({self.carrier_a_location})"
            if self.carrier_a_location
            else self.carrier_a
        )

    @property
    def carrier_b_with_location(self) -> str:
        return (
            f"{self.carrier_b} ({self.carrier_b_location})"
            if self.carrier_b_location
            else self.carrier_b
        )

    class Meta:
        permissions = [("assign_user", "Can assign user to SheetImport")]


class ItemStatus(models.Model):
    """Represents the status of an item in the SheetImport model."""

    status = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.status

    class Meta:
        verbose_name_plural = "Item statuses"
        ordering = ["status"]
