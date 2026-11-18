from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from catalog.models import Product
from inventory.models import StockMovement


class Command(BaseCommand):
    # Ce texte s'affiche avec : python manage.py help check_stock_integrity
    help = "Compare le stock de chaque produit avec la somme de ses mouvements."

    def add_arguments(self, parser):
        # Une option facultative : python manage.py check_stock_integrity --fix
        parser.add_argument(
            "--fix", action="store_true",
            help="Écrit une ligne de régularisation pour chaque écart trouvé.",
        )

    def handle(self, *args, **options):
        # annotate = "ajoute une colonne calculée à chaque produit".
        # Ici : journal_total = la somme de toutes ses lignes dans le cahier.
        # Coalesce(..., 0) = "si un produit n'a AUCUNE ligne, compte 0 au lieu de rien".
        products = Product.objects.annotate(
            journal_total=Coalesce(
                Sum("movements__quantity_delta"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=12, decimal_places=3),
            )
        )

        # On garde seulement les produits où le tableau et le cahier se contredisent.
        problems = [p for p in products if p.journal_total != p.stock_quantity]

        if not problems:
            self.stdout.write(self.style.SUCCESS("OK : le stock correspond au cahier partout."))
            return

        for p in problems:
            self.stdout.write(
                f"ECART {p.sku} : tableau = {p.stock_quantity}, cahier = {p.journal_total}"
            )
        self.stdout.write(self.style.WARNING(f"{len(problems)} produit(s) avec un écart."))

        if options["fix"]:
            self.fix(problems)

    @transaction.atomic
    def fix(self, problems):
        # Pour chaque écart, on ajoute au cahier UNE ligne qui comble la différence.
        # On ne touche PAS au stock du produit : on met seulement le cahier à niveau.
        for p in problems:
            StockMovement.objects.create(
                shop_id=p.shop_id, product=p, movement_type="adjustment",
                quantity_delta=p.stock_quantity - p.journal_total,
                quantity_before=p.journal_total, quantity_after=p.stock_quantity,
                reason="Régularisation : stock initial saisi sans mouvement",
                created_by=None,
            )
        self.stdout.write(self.style.SUCCESS(f"{len(problems)} régularisation(s) écrite(s)."))