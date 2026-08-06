from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "daily"

    def items(self):
        return [
            "inicio",
            "inscripcion",
            "login",
            "desarrollo_web_compra",
            "inteligencia_artificial_compra",
            "terminos_y_condiciones",
            "password_reset",
            "formulario_inscripcion",
            "inscripcion_ia_promo",
        ]

    def location(self, item):
        return reverse(item)