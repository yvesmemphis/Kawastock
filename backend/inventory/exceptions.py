from rest_framework.exceptions import APIException


class InsufficientStock(APIException):
    # 409 = "Conflit" : ta demande est bien formée, mais elle entre en
    # conflit avec l'état actuel des choses (pas assez de stock).
    status_code = 409
    default_code = "insufficient_stock"

    def __init__(self, product, available, requested):
        super().__init__({
            "code": "insufficient_stock",
            "detail": (f"Stock insuffisant pour {product.sku} : "
                       f"disponible {available}, demandé {requested}."),
            "product_id": str(product.id),
        })