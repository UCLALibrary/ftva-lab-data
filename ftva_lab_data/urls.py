from django.urls import path
from . import views

urlpatterns = [
    path("", views.search_results, name="search_results"),
    path("render_table/", views.render_search_results_table, name="render_table"),
    path("add_item/", views.add_item, name="add_item"),
    path("edit_item/<int:item_id>/", views.edit_item, name="edit_item"),
    path("view_item/<int:item_id>/", views.view_item, name="view_item"),
    path("assign/", views.assign_to_user, name="assign_to_user"),
    path(
        "export_search_results/",
        views.export_search_results,
        name="export_search_results",
    ),
    path("logs/", views.show_log, name="show_log"),
    path("logs/<int:line_count>", views.show_log, name="show_log"),
    path("release_notes/", views.release_notes, name="release_notes"),
    path("records/<int:record_id>", views.get_record, name="get_record"),
    path(
        "records/uuid/<str:uuid>", views.get_record_by_uuid, name="get_record_by_uuid"
    ),
    path(
        "external_search_results/<str:search_type>/<str:inventory_number>/",
        views.get_external_search_results,
        name="get_external_search_results",
    ),
    path(
        "metadata_json/<int:record_id>/",
        views.generate_metadata_json,
        name="generate_metadata_json",
    ),
    path(
        "set_carrier_location/", views.set_carrier_location, name="set_carrier_location"
    ),
    path("carrier-suggestions/", views.carrier_suggestions, name="carrier_suggestions"),
]
