from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet

# Le "router" est un fabricant de panneaux : on lui dit "ce guichetier est
# à cette adresse" et il fabrique tout seul les adresses de liste, de détail, etc.
router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("products", ProductViewSet)

urlpatterns = router.urls