from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from ftva_etl import AlmaSRUClient, FilemakerClient, get_mams_metadata
import pandas as pd
import io

from .forms import ItemForm
from .models import SheetImport
from .table_config import COLUMNS
from .views_utils import (
    get_item_display_dicts,
    get_add_edit_item_fields,
    get_search_result_data,
    get_search_result_items,
    get_items_per_page_options,
    format_data_for_export,
    build_url_parameters,
    basic_auth_required,
    process_full_alma_data,
    get_specific_filemaker_fields,
    transform_filemaker_field_name,
)


@login_required
@permission_required(
    "ftva_lab_data.add_sheetimport",
    raise_exception=True,
)
def add_item(request: HttpRequest) -> HttpResponse:
    """Add a new item to the database.

    :param request: The HTTP request object.
    :return: Rendered template for adding an item.
    """
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
def edit_item(request: HttpRequest, item_id: int) -> HttpResponse:
    """Edit an existing item in the database.

    :param request: The HTTP request object.
    :param item_id: The ID of the item to edit.
    :return: Rendered template for editing an item.
    """
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
        "url_parameters": build_url_parameters(
            search=search, search_column=search_column, page=page
        ),  # encode values to be safe for use in URLs
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
                f"?{build_url_parameters(search=search, search_column=search_column, page=page)}"
            )
            return redirect(url)

        else:
            messages.error(request, "Please correct the errors below.")
            return render(request, "add_edit_item.html", edit_item_context)
    else:
        return render(request, "add_edit_item.html", edit_item_context)


@login_required
def view_item(request: HttpRequest, item_id: int) -> HttpResponse:
    """View details of a specific item.

    :param request: The HTTP request object.
    :param item_id: The ID of the item to view.
    :return: Rendered template for viewing an item.
    """
    # Retrieve the item to view
    item = SheetImport.objects.get(id=item_id)

    # Retrieve search params
    search = request.GET.get("search", "")
    search_column = request.GET.get("search_column", "")
    page = request.GET.get("page", "")

    # For easier parsing in the template, separate attributes into dictionaries
    display_dicts = get_item_display_dicts(item)

    view_item_context = {
        "url_parameters": build_url_parameters(
            search=search, search_column=search_column, page=page
        ),  # encode values to be safe for use in URLs
        **display_dicts,
    }

    return render(request, "view_item.html", view_item_context)


@login_required
def search_results(request: HttpRequest) -> HttpResponse:
    """Render search results page.
    This view handles the initial rendering of the search results page,
    including the user list and search parameters, but not the actual search
    results table.

    :param request: The HTTP request object.
    :return: Rendered template for search results.
    """

    users = get_user_model().objects.all().order_by("username")

    # Retrieve search params
    search = request.GET.get("search", "")
    search_column = request.GET.get("search_column", "")
    page = request.GET.get("page", "")

    # The search parameters, while encoded as a query string elsewhere,
    # need to be returned individually here to sync with input element values.
    search_results_context = {
        "columns": COLUMNS,
        "users": users,
        "search": search,
        "search_column": search_column,
        "page": page,
    }

    # Pass search params from GET to template context,
    # so we can consistently render the results table after navigation
    return render(request, "search_results.html", search_results_context)


@login_required
def render_search_results_table(request: HttpRequest) -> HttpResponse:
    """Handles search and pagination of table.

    Search can either be column-specific, determined by dropdown,
    or broad, CTRL-F-style across all fields.

    :param request: The HTTP request object.
    :return: Rendered HTML for the search results table.
    """
    search = request.GET.get("search", "")
    search_column = request.GET.get("search_column", "")
    page = request.GET.get("page", 1)
    items_per_page = request.GET.get("items_per_page")

    display_fields = [field for field, _ in COLUMNS]
    # If there's a specific search column, use it;
    # otherwise, search in all display fields.
    search_fields = [search_column] if search_column else display_fields

    items = get_search_result_items(search, search_fields)

    items_per_page_options = get_items_per_page_options()
    default_per_page = items_per_page_options[0]
    # If `items_per_page` comes from request
    # overwrite value in session object
    if items_per_page:
        try:  # handle cases where request value cannot be coerced to int
            request.session["items_per_page"] = int(items_per_page)
        except ValueError:
            request.session["items_per_page"] = default_per_page
    # Else if `items_per_page` is not defined on session
    # default to first value in options list
    elif "items_per_page" not in request.session:
        request.session["items_per_page"] = default_per_page
    # Finally, defer to session for `items_per_page`
    items_per_page = request.session["items_per_page"]

    paginator = Paginator(items, items_per_page)
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

    search_results_table_context = {
        "page_obj": page_obj,
        "elided_page_range": elided_page_range,
        "columns": COLUMNS,
        "rows": rows,
        "items_per_page_options": items_per_page_options,
        "url_parameters": build_url_parameters(
            search=search, search_column=search_column, page=page
        ),  # encode values to be safe for use in URLs
    }

    return render(
        request, "partials/search_results_table.html", search_results_table_context
    )


@login_required
@permission_required(
    "ftva_lab_data.assign_user",
    raise_exception=True,
)
def assign_to_user(request: HttpRequest) -> HttpResponse:
    """Assigns a SheetImport item to a user.

    :param request: The HTTP request object.
    :return: Redirects to search results,
        or returns updated table HTML for HTMX requests.
    """
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


@login_required
def export_search_results(request: HttpRequest) -> StreamingHttpResponse:
    """Exports search results to a CSV file.

    :param request: The HTTP request object.
    :return: a streaming HTTP response with the CSV file attachment.
    """
    search = request.GET.get("search", "")
    search_column = request.GET.get("search_column", "")
    search_fields = (
        [search_column] if search_column else [field for field, _ in COLUMNS]
    )

    rows = get_search_result_items(search, search_fields)

    # Include all fields in the DataFrame, even if they are not displayed
    data_dicts = [row.__dict__ for row in rows]
    # Add, remove, and reorder fields as needed
    export_dicts = format_data_for_export(data_dicts)

    filename_base = "FTVA_DL_search_results"
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_base}_{timestamp}.csv"

    # Format dicts into CSV so we can use a streaming response
    csv_buffer = io.StringIO()
    df = pd.DataFrame(export_dicts)
    df.to_csv(csv_buffer, index=False)
    # Reset the buffer to the beginning so it can be read from the start
    csv_buffer.seek(0)
    response = StreamingHttpResponse(
        csv_buffer,  # type: ignore
        content_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )

    return response


@login_required
def show_log(request: HttpRequest, line_count: int = 200) -> HttpResponse:
    """Display log file in the browser.

    :param request: The HTTP request object.
    :param line_count: The most recent lines in the log. If not provided, shows the whole log.
    :return: Rendered HTML for the logs.
    """
    log_file = settings.LOG_FILE
    try:
        with open(log_file, "r") as f:
            # Get just the last line_count lines in the log.
            lines = f.readlines()[-line_count:]
            # Template prints these as a single block, so join lines into one chunk.
            log_data = "".join(lines)
    except FileNotFoundError:
        log_data = f"Log file {log_file} not found"

    return render(request, "log.html", {"log_data": log_data})


@login_required
def release_notes(request: HttpRequest) -> HttpResponse:
    """Display release notes.

    :param request: The HTTP request object.
    :return: Rendered HTML for the release notes.
    """
    return render(request, "release_notes.html")


@basic_auth_required
def get_record(request: HttpRequest, record_id: int) -> JsonResponse:
    """Retrieve a specific record by ID as JSON, intended for API use.

    :param request: The HTTP request object.
    :param record_id: The ID of the record to retrieve.
    :return: JSON response containing the record data.
    """
    try:
        record = SheetImport.objects.get(id=record_id)
        record_data = {
            field.name: getattr(record, field.name) for field in record._meta.fields
        }
        # Add Status many-to-many field data
        record_data["status"] = [status.status for status in record.status.all()]
        # Add Assigned User data if it exists
        if record.assigned_user:
            record_data["assigned_user"] = {
                "id": record.assigned_user.id,
                "username": record.assigned_user.username,
                "full_name": record.assigned_user.get_full_name(),
            }
        return JsonResponse(record_data)
    except SheetImport.DoesNotExist:
        return JsonResponse({"error": "Record not found"}, status=404)


def get_alma_data(request: HttpRequest, inventory_number: str) -> HttpResponse:
    """Fetch Alma records using SRU client.

    :param request: The HTTP request object.
    :param inventory_number: The inventory number to search for in Alma.
    :return: a list of dictionaries containing Alma record data, each with keys
        "record_id", "title", and "full_data".
    """
    sru_client = AlmaSRUClient()
    records = sru_client.search_by_call_number(inventory_number)

    # List of required fields, as defined by FTVA
    marc_fields = ["001", "008", "245", "246", "260", "655"]
    full_data_dicts = []

    for record in records:
        record_dict = {}
        # Extract the record ID and title, used for search results display
        record_dict["record_id"] = record.get("001").value()
        # Get relevant subfields from the 245 field for the title
        title_subfields = ["a", "b", "n", "p"]
        title_components = record.get("245").get_subfields(*title_subfields)
        record_dict["title"] = " ".join(
            [subfield for subfield in title_components if subfield]
        )

        # Process the full MARC data to get relevant fields processed into a dict
        record_fields = sru_client.get_fields(record, marc_fields)
        record_dict["full_data"] = process_full_alma_data(record_fields)

        full_data_dicts.append(record_dict)

    return render(
        request,
        "external_search_results.html",
        {
            "records": full_data_dicts,
            "inventory_number": inventory_number,
            "search_type": "alma",
        },
    )


def get_filemaker_data(request: HttpRequest, inventory_number: str) -> HttpResponse:
    """Fetch records using FilemakerClient.

    :param request: The HTTP request object.
    :param inventory_number: The inventory number to search for in Filemaker.
    :return: a list of dictionaries containing Filemaker record data, each with keys
        "record_id", "title", and "full_data".
    """

    user = settings.FILEMAKER_USER
    password = settings.FILEMAKER_PASSWORD
    fm_client = FilemakerClient(user=user, password=password)

    records = fm_client.search_by_inventory_number(inventory_number)

    # List of required fields, as defined by FTVA
    specific_fields = [
        "type",
        "inventory_no",
        "inventory_id",
        "format_type",
        "title",
        "aka",
        "director",
        "episode_title",
        "production_type",
        "Acquisition type",
        "Alma",
        "availability",
        "release_broadcast_year",
        "notes",
        "element_info",
        "spac",
        "episode no.",
        "film base",
        "donor_code",
    ]
    full_data_dicts = []

    for record in records:
        filemaker_fields = get_specific_filemaker_fields(record, specific_fields)
        data_dict = {}

        data_dict["record_id"] = filemaker_fields.get("inventory_id", "NO INVENTORY ID")
        data_dict["title"] = filemaker_fields.get("title", "NO TITLE")
        # Transform the raw FM field names to be cleaner and more consistent
        data_dict["full_data"] = {
            transform_filemaker_field_name(k): v for k, v in filemaker_fields.items()
        }

        full_data_dicts.append(data_dict)

    return render(
        request,
        "external_search_results.html",
        {
            "records": full_data_dicts,
            "inventory_number": inventory_number,
            "search_type": "filemaker",
        },
    )


def get_external_search_results(
    request: HttpRequest, inventory_number: str, search_type: str
) -> HttpResponse:
    """Fetch external search results for a given inventory number.

    :param request: The HTTP request object.
    :param inventory_number: The inventory number to search for.
    :return: Rendered HTML for the external search results.
    """
    if search_type == "alma":
        return get_alma_data(request, inventory_number)

    elif search_type == "fm":
        return get_filemaker_data(request, inventory_number)
    else:
        return HttpResponse(
            "Invalid search type specified.",
            status=400,
        )


def generate_metadata_json(
    request: HttpRequest, record_id: int, inventory_number: str
) -> JsonResponse | str:
    """Generate a  JSON metadata record for a given inventory number,
    by combining data from Alma, Filemaker, and Django.

    :param request: The HTTP request object.
    :param record_id: The ID of the Django record to use.
    :param inventory_number: The inventory number to search for in Alma and Filemaker.
    :return: A JSON record containing the combined metadata.
    """

    # Get Django record
    django_record = SheetImport.objects.get(pk=record_id)
    # Transform the Django record into a dict
    django_record_data = {
        field.name: getattr(django_record, field.name)
        for field in django_record._meta.fields
    }

    # Get Alma records
    sru_client = AlmaSRUClient()
    bib_records = sru_client.search_by_call_number(inventory_number)

    # Get Filemaker records
    user = settings.FILEMAKER_USER
    password = settings.FILEMAKER_PASSWORD
    fm_client = FilemakerClient(user=user, password=password)
    fm_records = fm_client.search_by_inventory_number(inventory_number)

    # If Alma and FM records are unique, generate JSON metadata
    if len(bib_records) == 1 and len(fm_records) == 1:
        metadata = get_mams_metadata(bib_records[0], fm_records[0], django_record_data)
        # TODO: render a template with the metadata. Returning JSON for now.
        return JsonResponse(metadata)

    # If either Alma or FM records are not unique, return a message
    if len(bib_records) > 1 or len(fm_records) > 1:
        message = (
            f"Metadata not generated because the search for {inventory_number} "
            "did not find unique records in Alma and/or Filemaker."
        )
        # TODO: render a template with the message. Returning JSON for now.
        return JsonResponse({"message": message}, status=400)
