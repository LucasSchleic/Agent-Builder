from django.urls import path
from django.shortcuts import render

def index(request):
    """Serve the main canvas UI."""
    return render(request, "index.html")

urlpatterns = [
    path("", index),
]