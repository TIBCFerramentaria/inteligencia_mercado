from django.urls import path
from . import views


app_name = "mercado"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("ranking/", views.ranking_mercado, name="ranking_mercado"),
    path("ranking/exportar/", views.exportar_ranking_excel, name="exportar_ranking_excel"),
    path("marcas/", views.forca_marcas, name="forca_marcas"),
    path("precos/", views.precos_referencias, name="precos_referencias"),
    path("precos/exportar/", views.exportar_precos_excel, name="exportar_precos_excel"),
    path("produtos/", views.lista_produtos, name="lista_produtos"),
    path("referencias/", views.lista_referencias, name="lista_referencias"),
]