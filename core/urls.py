from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='inicio'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
]