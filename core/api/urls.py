from django.urls import path

from core.api import views

urlpatterns = [
    # Workflow list
    path("workflows/", views.list_workflows, name="list_workflows"),
    # Workflow CRUD
    path("workflow/new/", views.new_workflow, name="new_workflow"),
    path("workflow/load/<str:name>/", views.load_workflow, name="load_workflow"),
    path("workflow/save/", views.save_workflow, name="save_workflow"),
    # Block operations
    path("workflow/block/add/", views.add_block, name="add_block"),
    path("workflow/block/remove/", views.remove_block, name="remove_block"),
    path("workflow/block/update/", views.update_block, name="update_block"),
    # Connection operations
    path("workflow/connection/add/", views.add_connection, name="add_connection"),
    path("workflow/connection/remove/", views.remove_connection, name="remove_connection"),
    # Export & run
    path("workflow/export/", views.export_workflow, name="export_workflow"),
    path("workflow/run/", views.run_workflow, name="run_workflow"),
]
