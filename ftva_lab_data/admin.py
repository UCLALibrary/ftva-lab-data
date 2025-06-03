from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import SheetImport

admin.site.register(SheetImport, SimpleHistoryAdmin)
