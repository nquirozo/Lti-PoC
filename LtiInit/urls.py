from typing import ValuesView
from django.urls import path
from . import views

urlpatterns = [
    path('launch', views.launch),
    path('login', views.login),
    path('dpl', views.deeplink),
    path('createLI', views.creaNota),
    path('notas', views.ObtenerNotas)

]
