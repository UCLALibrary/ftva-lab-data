from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import SheetImport, ItemStatus


@admin.register(ItemStatus)
class ItemStatusAdmin(admin.ModelAdmin):
    list_display = ("status",)
    search_fields = ("status",)


@admin.register(SheetImport)
class SheetImportAdmin(SimpleHistoryAdmin):
    search_fields = ("id",)
