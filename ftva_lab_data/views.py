from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string


from .forms import ItemForm
from .models import SheetImport
from .table_config import COLUMNS
from .views_utils import (
    get_item_display_dicts,
    get_add_edit_item_fields,
    get_search_result_data,
    get_search_result_items,
)


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
    # Get form fields, divided into basic and advanced sections
    fields = get_add_edit_item_fields(ItemForm())
    # Add the fields to the context for rendering in the template
    add_item_context.update(fields)

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
    # Get search params from GET or POST, to be used to help navigate back
    # to the search results after editing
    search = request.GET.get("search", request.POST.get("search", ""))
    search_column = request.GET.get(
        "search_column", request.POST.get("search_column", "")
    )
    page = request.GET.get("page", request.POST.get("page", ""))

    # context values to be passed to the add_edit_item template
    edit_item_context = {
        "form": ItemForm(instance=item),
        "item": item,
        "title": "Edit Item",
        "button_text": "Save Changes",
        "search": search,
        "search_column": search_column,
        "page": page,
    }
    # Get form fields, divided into basic and advanced sections
    fields = get_add_edit_item_fields(ItemForm(instance=item))
    # Add the fields to the context for rendering in the template
    edit_item_context.update(fields)

    if request.method == "POST":
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Item updated successfully!")
            url = (
                f"{reverse('view_item', args=[item.id])}"
                f"?search={search}&search_column={search_column}&page={page}"
            )
            return redirect(url)

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
    # Pass search params to template, so they can be preserved
    # if using the "Back to Search" button
    display_dicts.update(
        {
            "search": request.GET.get("search", ""),
            "search_column": request.GET.get("search_column", ""),
            "page": request.GET.get("page", ""),
        }
    )
    return render(request, "view_item.html", display_dicts)


@login_required
def search_results(request: HttpRequest) -> HttpResponse:
    users = get_user_model().objects.all().order_by("username")
    # Pass search params from GET to template context,
    # so we can consistently render the results table after navigation
    return render(
        request,
        "search_results.html",
        context={
            "columns": COLUMNS,
            "users": users,
            "search": request.GET.get("search", ""),
            "search_column": request.GET.get("search_column", ""),
            "page": request.GET.get("page", 1),
        },
    )


@login_required
def render_search_results_table(request: HttpRequest) -> HttpResponse:
    """Handles search and pagination of table.

    Search can either be column-specific, determined by dropdown,
    or broad, CTRL-F-style across all fields
    """
    search = request.GET.get("search", "")
    search_column = request.GET.get("search_column", "")
    page = request.GET.get("page", 1)
    records_per_page = request.GET.get("records_per_page", 10)
    display_fields = [field for field, _ in COLUMNS]
    records_per_page_options = [10, 20, 50, 100]

    # If there's a specific search column, use it;
    # otherwise, search in all display fields.
    search_fields = [search_column] if search_column else display_fields

    items = get_search_result_items(search, search_fields)

    paginator = Paginator(items, records_per_page)
    page_obj = paginator.get_page(page)
    # Convert elided page range to list to allow multiple iterations in template
    elided_page_range = list(
        paginator.get_elided_page_range(
            number=page_obj.number, on_each_side=5, on_ends=1
        )
    )

    # Construct of list of dicts to use as table rows instead of QuerySets
    # allowing row[field] to be accessed, rather than specifying each field literal.
    rows = get_search_result_data(
        item_list=page_obj.object_list, display_fields=display_fields
    )

    return render(
        request,
        "partials/search_results_table.html",
        {
            "page_obj": page_obj,
            "elided_page_range": elided_page_range,
            "search": search,
            "search_column": search_column,
            "columns": COLUMNS,
            "rows": rows,
            "records_per_page_options": records_per_page_options,
        },
    )


@login_required
@permission_required(
    "ftva_lab_data.assign_user",
    raise_exception=True,
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
