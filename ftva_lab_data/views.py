from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string


from .forms import ItemForm
from .models import SheetImport
from .table_config import COLUMNS
from .views_utils import get_field_value, get_item_display_dicts


@login_required
@permission_required(
    "ftva_lab_data.add_sheetimport",
    raise_exception=True,
)
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


@login_required
@permission_required(
    "ftva_lab_data.change_sheetimport",
    raise_exception=True,
)
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
            return render(request, "view_item.html", get_item_display_dicts(item))
        else:
            messages.error(request, "Please correct the errors below.")
            return render(request, "add_edit_item.html", edit_item_context)
    else:
        return render(request, "add_edit_item.html", edit_item_context)


@login_required
def view_item(request, item_id):
    # Retrieve the item to view
    item = SheetImport.objects.get(id=item_id)
    # For easier parsing in the template, separate attributes into dictionaries
    display_dicts = get_item_display_dicts(item)

    return render(
        request,
        "view_item.html",
        display_dicts 
    )


@login_required
def search_results(request: HttpRequest) -> HttpResponse:
    users = get_user_model().objects.all().order_by("username")
    return render(
        request, "search_results.html", context={"columns": COLUMNS, "users": users}
    )


@login_required
def render_search_results_table(request: HttpRequest) -> HttpResponse:
    """Handles search and pagination of table

    Search can either be column-specific, determined by dropdown,
    or broad, CTRL-F-style across all fields
    """
    display_fields = [field for field, _ in COLUMNS]

    search = request.GET.get("search", "")
    search_column = request.GET.get("search_column", "")
    page = request.GET.get("page", 1)

    # Only need display fields, plus ID for creating links
    items = SheetImport.objects.only(*display_fields, "id").order_by("id")
    if search:
        if search_column and search_column in display_fields:
            # Scoped search to selected column
            items = items.filter(**{f"{search_column}__icontains": search})
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
            "data": {field: get_field_value(item, field) for field in display_fields},
            "id": item.id,
        }
        for item in page_obj.object_list
    ]

    # Get all users for the dropdown in the table
    users = get_user_model().objects.all().order_by("username")

    return render(
        request,
        "partials/search_results_table.html",
        {
            "page_obj": page_obj,
            "search": search,
            "search_column": search_column,
            "columns": COLUMNS,
            "rows": rows,
            "users": users,
        },
    )


def assign_to_user(request: HttpRequest) -> HttpResponse:
    """Assigns a SheetImport item to a user."""
    ids = request.POST.get("ids", "").split(",")
    user_id = request.POST.get("user_id")
    if ids and user_id:
        if user_id == "__unassign__":
            SheetImport.objects.filter(id__in=ids).update(assigned_user=None)
            messages.success(request, "Items unassigned successfully!")
        else:
            user = get_user_model().objects.get(id=user_id)
            SheetImport.objects.filter(id__in=ids).update(assigned_user=user)
            messages.success(request, "Items assigned successfully!")
    # If this is an HTMX request, return only the updated table partial
    if request.headers.get("HX-Request"):
        # Preserve filters and pagination by copying POST data to GET
        mutable_get = request.GET.copy()
        for param in ["search", "search_column", "page"]:
            value = request.POST.get(param)
            if value is not None:
                mutable_get[param] = value
        request.GET = mutable_get
        # In order to display messages, we need to render the messages template
        # separately and combine it with the table HTML.
        messages_html = render_to_string(
            "partials/messages.html",
            {"messages": messages.get_messages(request)},
            request=request,
        )
        table_html = render_search_results_table(request).content.decode()
        combined_html = f"{messages_html}{table_html}"
        return HttpResponse(combined_html)

    # Otherwise, do a normal redirect
    return redirect("search_results")
