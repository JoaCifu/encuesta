from django.urls import path

from . import views

app_name = "encuesta"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("paso/<int:orden>/", views.paso, name="paso"),
    path("gracias/", views.gracias, name="gracias"),
]
