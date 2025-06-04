from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import SheetImport, ItemStatus

admin.site.register(SheetImport, SimpleHistoryAdmin)
admin.site.register(ItemStatus)


class ItemStatusAdmin(admin.ModelAdmin):
    list_display = ("status", "display_name")
    search_fields = ("status", "display_name")
