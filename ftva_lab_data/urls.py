from django.urls import path
from . import views

urlpatterns = [
    path("", views.search_results, name="search_results"),
    path("render_table/", views.render_search_results_table, name="render_table"),
    path("add_item/", views.add_item, name="add_item"),
    path("edit_item/<int:item_id>/", views.edit_item, name="edit_item"),
    path("view_item/<int:item_id>/", views.view_item, name="view_item"),
    path("assign/", views.assign_to_user, name="assign_to_user"),
]
