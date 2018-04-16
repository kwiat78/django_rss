from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text
from rest_framework import serializers

from feeds.models import Feed, Post, Link, FeedLink


class CreatableSlugRelatedField(serializers.SlugRelatedField):
    def to_internal_value(self, data):
        try:
            return self.get_queryset().get_or_create(**{self.slug_field: data})[0]
        except ObjectDoesNotExist:
            self.fail('does_not_exist', slug_name=self.slug_field, value=smart_text(data))
        except (TypeError, ValueError):
            self.fail('invalid')


class FeedLinkSerializer(serializers.ModelSerializer):

    link = CreatableSlugRelatedField(queryset=Link.objects, slug_field="url")
    feed = serializers.PrimaryKeyRelatedField(queryset=Feed.objects)

    class Meta:
        model = FeedLink
        exclude = ("id", "feed",)


class LinkSerializer(serializers.ModelSerializer):

    class Meta:
        model = Link
        fields = '__all__'

    def create(self, validated_data):
        item, _ = Link.objects.get_or_create(**validated_data)
        return item


class FeedSerializer(serializers.ModelSerializer):
    links = FeedLinkSerializer(many=True, read_only=True)
    count = serializers.SerializerMethodField()
    position = serializers.IntegerField(read_only=True)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    favIcon = serializers.CharField(default='undefined', required=False)

    class Meta:
        model = Feed
        fields = '__all__'

    def create(self, validated_data):
        position = len(Feed.objects.filter(user=validated_data['user']))
        validated_data['position'] = position
        feed = super().create(validated_data)
        link_serializer = LinkSerializer(data=self.initial_data)
        link_serializer.is_valid()
        link = link_serializer.save()

        feedlink_serializer = FeedLinkSerializer(data={'feed': feed.pk,
                                                       'link': link,
                                                       'reg_exp': self.initial_data.get('regExp', '')})
        feedlink_serializer.is_valid()
        feedlink_serializer.save()
        return feed

    def get_count(self, obj):
        return len(Post.objects.filter(feed=obj, view=False))


class PostSerializer(serializers.ModelSerializer):

    class Meta:
        model = Post
        fields = '__all__'
