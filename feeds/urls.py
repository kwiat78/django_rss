from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter

from feeds.views import DiscoverView, FeedView, LinkView, PostView

router = DefaultRouter()

router.register(r"feeds", FeedView, base_name='feeds')
router.register(r"posts", PostView, base_name='posts')
router.register(r"discover", DiscoverView, base_name="discover")

posts_router = DefaultRouter()
posts_router.register(r"links", LinkView, base_name='links')


urlpatterns = [
    url(r'', include(router.urls)),
    url(r'^feeds/(?P<feed>[^/.]+)/', include(posts_router.urls)),
]
