from django.utils import timezone

from django_filters import rest_framework as filters
from feeds.models import Post


class PostFilterSet(filters.FilterSet):
    name = filters.CharFilter(name="feed__id")
    current = filters.NumberFilter(name="add_date", method="current_filter")
    new = filters.BooleanFilter(name="view", method="new_filter")

    @staticmethod
    def current_filter(queryset, name, value):
        current = timezone.make_aware(timezone.datetime.fromtimestamp(float(value)))
        return queryset.filter(add_date__gte=current, add_date__lte=timezone.now())

    @staticmethod
    def new_filter(queryset, name, value):
        return queryset.exclude(view=value)

    class Meta:
        model = Post
        fields = ["name", "new", "mentioned", "current"]
