from django.urls import path, re_path
from . import views

urlpatterns = [
    path("", views.add_item, name="add_item"),
    path("add_item/", views.add_item, name="add_item"),
    path("edit_item/<int:item_id>/", views.edit_item, name="edit_item"),
    path("view_item/<int:item_id>/", views.view_item, name="view_item"),
]
