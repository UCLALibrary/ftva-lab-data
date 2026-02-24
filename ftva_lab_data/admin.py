from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import (
    SheetImport,
    ItemStatus,
    AssetType,
    FileType,
    MediaType,
    NoIngestReason,
    AudioClass,
    Relationship,
    RelationshipType,
)


class RelationshipInline(admin.TabularInline):
    model = Relationship
    fk_name = "source"
    extra = 1
    autocomplete_fields = ("target",)
    fields = ("target", "relationship_type")
    verbose_name = "Relationship"
    verbose_name_plural = "Relationships"


@admin.register(ItemStatus)
class ItemStatusAdmin(admin.ModelAdmin):
    list_display = ("status",)
    search_fields = ("status",)


@admin.register(SheetImport)
class SheetImportAdmin(SimpleHistoryAdmin):
    search_fields = ("id__exact",)
    inlines = [RelationshipInline]


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


@admin.register(AudioClass)
class AudioClassAdmin(admin.ModelAdmin):
    list_display = ("audio_class",)
    search_fields = ("audio_class",)


@admin.register(RelationshipType)
class RelationshipTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "inverse")
    search_fields = ("name",)
