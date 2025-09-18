from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import (
    SheetImport,
    ItemStatus,
    AssetType,
    FileType,
    MediaType,
    NoIngestReason,
)


@admin.register(ItemStatus)
class ItemStatusAdmin(admin.ModelAdmin):
    list_display = ("status",)
    search_fields = ("status",)


@admin.register(SheetImport)
class SheetImportAdmin(SimpleHistoryAdmin):
    search_fields = ("id__exact",)


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ("asset_type",)
    search_fields = ("asset_type",)


@admin.register(FileType)
class FileTypeAdmin(admin.ModelAdmin):
    list_display = ("file_type",)
    search_fields = ("file_type",)


@admin.register(MediaType)
class MediaTypeAdmin(admin.ModelAdmin):
    list_display = ("media_type",)
    search_fields = ("media_type",)


@admin.register(NoIngestReason)
class NoIngestReasonAdmin(admin.ModelAdmin):
    list_display = ("no_ingest_reason",)
    search_fields = ("no_ingest_reason",)
