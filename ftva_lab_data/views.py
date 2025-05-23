from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse

from .forms import ItemForm
from .models import SheetImport
from .table_config import COLUMNS


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


def search_results(request: HttpRequest) -> HttpResponse:
    return render(request, "search_results.html", context={"columns": COLUMNS})


def render_search_results_table(request: HttpRequest) -> HttpResponse:
    """Handles search and pagination of table

    Search can either be column-specific, determined by dropdown,
    or broad, CTRL-F-style across all fields
    """
    display_fields = [field for field, _ in COLUMNS]

    search = request.GET.get("search", "")
    column = request.GET.get("column", "")
    page = request.GET.get("page", 1)

    # Only need display fields, plus ID for creating links
    items = SheetImport.objects.only(*display_fields, "id").order_by("id")
    if search:
        if column and column in display_fields:
            # Scoped search to selected column
            items = items.filter(**{f"{column}__icontains": search})
        else:
            # General CTRL-F-style search across all configured fields
            query = Q()  # start with empty Q() object, always True
            for field in display_fields:  # then add queries for all valid fields
                query |= Q(**{f"{field}__icontains": search})
            items = items.filter(query)

    paginator = Paginator(items, 10)
    page_obj = paginator.get_page(page)

    # Construct of list of dicts to use as table rows instead of QuerySets
    # allowing row[field] to be accessed, rather than specifying each field literal.
    # Set ID as a seperate property so it is not displayed as column header,
    # but can still be accessed for links.
    rows = [
        {
            "data": {field: getattr(item, field, "") for field in display_fields},
            "id": item.id,
        }
        for item in page_obj.object_list
    ]

    return render(
        request,
        "partials/search_results_table.html",
        {"page_obj": page_obj, "search": search, "columns": COLUMNS, "rows": rows},
    )
