from rest_framework.routers import DefaultRouter
from .views import MembershipViewSet, ShopViewSet

router = DefaultRouter()
router.register("shops", ShopViewSet, basename="shop")
router.register("members", MembershipViewSet, basename="member")
urlpatterns = router.urls