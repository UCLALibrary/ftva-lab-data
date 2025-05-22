from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse

from .forms import ItemForm
from .models import SheetImport


def add_item(request):
    # context values to be passed to the add_edit_item template
    add_item_context = {
        "form": ItemForm(),
        "title": "Add Item",
        "button_text": "Add Item",
    }

    if request.method == "POST":
        # save a new SheetImport object
        form = ItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Item added successfully!")
            return redirect("view_item", item_id=form.instance.id)
        else:
            # Handle form errors, if needed
            messages.error(request, "Please correct the errors below.")
            return render(request, "add_edit_item.html", add_item_context)
    else:
        # For GET requests, display the empty form
        return render(request, "add_edit_item.html", add_item_context)


def edit_item(request, item_id):
    # Retrieve the item to edit
    item = SheetImport.objects.get(id=item_id)
    # context values to be passed to the add_edit_item template
    edit_item_context = {
        "form": ItemForm(instance=item),
        "item": item,
        "title": "Edit Item",
        "button_text": "Save Changes",
    }

    if request.method == "POST":
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Item updated successfully!")
            return render(request, "view_item.html", {"item": item})
        else:
            messages.error(request, "Please correct the errors below.")
            return render(request, "add_edit_item.html", edit_item_context)
    else:
        return render(request, "add_edit_item.html", edit_item_context)


def view_item(request, item_id):
    # Retrieve the item to view
    item = SheetImport.objects.get(id=item_id)

    return render(request, "view_item.html", {"item": item})


def view_items(request: HttpRequest) -> HttpResponse:
    return render(request, "view_items.html")


def render_table(request: HttpRequest) -> HttpResponse:
    """Handles search and pagination of table"""
    search = request.GET.get("search", "")
    page = request.GET.get("page", 1)

    records = SheetImport.objects.all().order_by("id")
    if search:
        records = records.filter(
            Q(hard_drive_name__icontains=search) | Q(file_name__icontains=search)
        )

    paginator = Paginator(records, 10)  # TODO: make configurable
    page_obj = paginator.get_page(page)

    return render(
        request,
        "partials/table.html",
        {"page_obj": page_obj, "search": search},
    )
