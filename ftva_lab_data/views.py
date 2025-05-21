from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ItemForm
from .models import SheetImport


def add_item(request):
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
            return render(
                request,
                "add_edit_item.html",
                {"form": form, "title": "Add Item", "button_text": "Add Item"},
            )
    else:
        # For GET requests, display the empty form
        form = ItemForm()
        return render(
            request,
            "add_edit_item.html",
            {"form": form, "title": "Add Item", "button_text": "Add Item"},
        )


def edit_item(request, item_id):
    # Retrieve the item to edit
    item = SheetImport.objects.get(id=item_id)

    if request.method == "POST":
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Item updated successfully!")
            return render(request, "view_item.html", {"item": item})
        else:
            messages.error(request, "Please correct the errors below.")
            return render(
                request,
                "add_edit_item.html",
                {
                    "form": form,
                    "item": item,
                    "title": "Edit Item",
                    "button_text": "Save Changes",
                },
            )
    else:
        form = ItemForm(instance=item)

    return render(
        request,
        "add_edit_item.html",
        {
            "form": form,
            "item": item,
            "title": "Edit Item",
            "button_text": "Save Changes",
        },
    )


def view_item(request, item_id):
    # Retrieve the item to view
    item = SheetImport.objects.get(id=item_id)

    return render(request, "view_item.html", {"item": item})
