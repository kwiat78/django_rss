from datetime import datetime
from io import StringIO
from unittest.mock import patch, Mock

from binascii import b2a_base64
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase
from freezegun import freeze_time
import pytz
from rest_framework.test import APIClient
from rest_framework import status
from urllib.error import URLError


from feeds.models import Feed, FeedLink, Link, Post
from feeds.views import get_posts
from feed_reader.feed_reader import FeedDownloader
from feeds.fixtures import test_sites


def feed_creator(name, link, items):
    head = """
    <?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
        <channel>
          <title>{}</title>
          <link>{}</link>
          <description>Feed</description>
          {}
        </channel>
    </rss>""".format(name, link, "{}")
    feed_items = ""
    for t, l, p in items:
        item = """<item>
                <title>{}</title>
                <link>{}</link>
                <description>{}</description>
                <published>{}</published>
              </item>
        """.format(t, l, t, p)
        feed_items += item
    return head.format(feed_items)


def add_feed(user, name, url, position, reg_exp="", post_limit=20):
    feed = Feed.objects.create(name=name, user=user, position=position, postLimit=post_limit)
    link, _ = Link.objects.get_or_create(url=url)
    FeedLink.objects.create(link=link, feed=feed, reg_exp=reg_exp)


class FeedTests(TestCase):
    fixtures = ['feeds']

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.get(username='user1')
        self.client.force_authenticate(self.user)
        self.URL_FEEDS = reverse("feeds-list")

    def test_get_feeds(self):
        result = self.client.get(self.URL_FEEDS, format='json')
        assert result.status_code == status.HTTP_200_OK
        assert len(result.data) == 2

    def test_get_feed(self):
        result = self.client.get(reverse("feeds-detail", args=(1,)), format='json')
        assert result.status_code == status.HTTP_200_OK
        assert result.data['name'] == 'Feed1'
        assert result.data['position'] == 0

    def test_post_feed(self):
        test_url = "http://test.url/rss.xml"
        result = self.client.post(reverse("feeds-list"), data={"name": "Feed3", "url": test_url}, format='json')
        assert result.status_code == status.HTTP_201_CREATED
        assert len(Feed.objects.filter(user=self.user)) == 3
        assert FeedLink.objects.filter(link__url="http://test.url/rss.xml", feed__user=self.user).exists()
        assert result.data['name'] == 'Feed3'
        assert result.data['position'] == 2

    def test_put_feed(self):
        result = self.client.put(
            reverse("feeds-detail", args=(1,)),
            data={"name": "Feed1", "postLimit": 5},
            format='json'
        )
        assert result.status_code == status.HTTP_200_OK
        assert Feed.objects.get(pk=1, name="Feed1", user=self.user).postLimit == 5
        assert result.data['postLimit'] == 5

    def test_delete_feed(self):
        result = self.client.delete(reverse("feeds-detail", args=(1,)), format='json')
        assert result.status_code == status.HTTP_204_NO_CONTENT
        queryset = Feed.objects.filter(user=self.user)
        assert len(queryset) == 1
        assert queryset[0].position == 0
        # assert FeedLink.objects.filter(link__url="http://test.url/rss.xml", feed__user=self.user).exists()

    def test_reorder_feeds(self):
        result = self.client.put(reverse("feeds-reorder"), data={"oldPosition": 0, "newPosition": 1}, format='json')
        assert result.status_code == status.HTTP_204_NO_CONTENT
        assert Feed.objects.get(user=self.user, position=0).name == "Feed2"
        assert Feed.objects.get(user=self.user, position=1).name == "Feed1"

    def test_reorder_feeds_fix_order(self):
        result = self.client.put(reverse("feeds-reorder"), data={"oldPosition": 1, "newPosition": 0}, format='json')
        assert result.status_code == status.HTTP_204_NO_CONTENT
        assert Feed.objects.get(user=self.user, position=0).name == "Feed2"
        assert Feed.objects.get(user=self.user, position=1).name == "Feed1"

    def test_reorder_feeds_wrongly_specified_positions(self):
        result = self.client.put(reverse("feeds-reorder"), data={"newPosition": 1}, format='json')
        assert result.status_code == status.HTTP_400_BAD_REQUEST

    def test_loop(self):
        link = Link.objects.create(url="http://test.com/rss/feed.xml")
        FeedLink.objects.create(link=link, feed=Feed.objects.get(pk=1), reg_exp="")
        with freeze_time("2018-01-31T13:00:01Z"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1", "2018-01-31T11:00:00"),
                        ("Post2", "https://test.com/feed/Post2", "2018-01-31T12:00:00")
                    ])
            ))):
                result = self.client.get(reverse("feeds-loop"), format='json')
        assert result.data['added'] == 2


class FeedLinkTests(TestCase):
    fixtures = ['feeds', "feed_links"]

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.get(username='user1')
        self.client.force_authenticate(self.user)

    def test_get_feed_links(self):
        result = self.client.get(reverse("links-list", kwargs={"feed": "Feed1"}), format='json')
        assert result.status_code == status.HTTP_200_OK
        assert len(result.data) == 3

    def test_get_feed_link(self):
        result = self.client.get(reverse("links-detail", kwargs={"feed": "Feed1", "position": 0}), format='json')
        assert result.status_code == status.HTTP_200_OK
        assert result.data['link'] == "http://test.xml"
        assert result.data['feed'] == 1
        assert result.data['reg_exp'] is None

    def test_post_feed_link(self):
        result = self.client.post(
            reverse("links-list", kwargs={"feed": "Feed2", }),
            data={"link": "http://test21.xml", "reg_exp": "T1: .*"},
            format='json'
        )
        assert result.status_code == status.HTTP_201_CREATED
        assert result.data['link'] == "http://test21.xml"
        assert result.data['feed'] == 2
        assert result.data['reg_exp'] == "T1: .*"
        assert result.data['position'] == 0
        assert FeedLink.objects.filter(link__url="http://test21.xml", feed__user=self.user, reg_exp="T1: .*").exists()
        assert Link.objects.filter(url="http://test21.xml").exists()

    def test_put_feed_link(self):
        result = self.client.put(
            reverse("links-detail", kwargs={"feed": "Feed1", "position": 0}),
            data={"link": "http://test1.xml", "feed": 1, "reg_exp": "TX1: .*"},
            format='json'
        )
        assert result.status_code == status.HTTP_200_OK
        assert result.data['reg_exp'] == "TX1: .*"
        assert FeedLink.objects.get(link__url="http://test1.xml", feed__user=self.user).reg_exp == "TX1: .*"

    def test_delete_feed_link(self):
        result = self.client.delete(reverse("links-detail", kwargs={"feed": "Feed1", "position": 1}), format='json')
        assert result.status_code == status.HTTP_204_NO_CONTENT
        assert FeedLink.objects.filter(feed__name="Feed1").count() == 2
        assert FeedLink.objects.get(feed__name="Feed1", link__url="http://test3.xml").position == 1
        assert FeedLink.objects.get(feed__name="Feed1", link__url="http://test.xml").position == 0


class PostTests(TestCase):
    fixtures = ['feeds', "feed_links", "posts"]

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.get(username='user1')
        self.client.force_authenticate(self.user)

    def test_get_all_feed_posts(self):
        result = self.client.get(reverse("posts-list"), data={"feed": 1}, format='json')
        assert result.status_code == status.HTTP_200_OK
        assert result.data['count'] == 3

    def test_get_new_feed_posts(self):
        result = self.client.get(reverse("posts-list"), data={"feed": 1, "new": True}, format='json')
        assert result.status_code == status.HTTP_200_OK
        assert result.data['count'] == 2

    def test_get_current_feed_posts(self):
        current = datetime(2018, 1, 25, 20, 5, 1)
        result = self.client.get(
            reverse("posts-list"),
            data={"feed": 1, "current": int(current.timestamp())},
            format='json'
        )
        assert result.status_code == status.HTTP_200_OK

        assert result.data['count'] == 1

    def test_read_post(self):
        result = self.client.patch(reverse("posts-detail", args=(1,)), data={"view": True}, format='json')
        assert result.status_code == status.HTTP_200_OK
        assert result.data['title'] == "Post1"
        assert result.data['view'] == True
        assert Post.objects.filter(view=False).count() == 1


class DiscoverTests(TestCase):
    fixtures = ['feeds']

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.get(username='user1')
        self.client.force_authenticate(self.user)
        self.url = b2a_base64("http://test.com".encode())
        self.wrong_url = b2a_base64("htt://test.com".encode())
        self.feed_url = b2a_base64("http://test.com/feed/".encode())
        self.wrong_feed_url = b2a_base64("htt://test.com/feed/".encode())

    @patch("urllib.request.urlopen", Mock(return_value=StringIO(test_sites.SITE)))
    def test_scan(self):
        result = self.client.get(reverse("discover-scan"), data={"url": self.url}, format='json')
        assert result.status_code == status.HTTP_200_OK
        assert len(result.data) == 2
        assert "http://test.com/feed/" in result.data
        assert "http://test.com/feed2/" in result.data

    @patch("urllib.request.urlopen", Mock(return_value=StringIO(test_sites.EMPTY_SITE)))
    def test_no_links(self):
        result = self.client.get(reverse("discover-scan"), data={"url": self.url}, format='json')
        assert result.status_code == status.HTTP_200_OK
        assert len(result.data) == 0

    def test_scan_wrong_url(self):
        result = self.client.get(reverse("discover-scan"), data={"url": self.wrong_url}, format='json')
        assert result.status_code == status.HTTP_404_NOT_FOUND

    @patch("urllib.request.urlopen", Mock(return_value=StringIO(test_sites.FEED)))
    def test_extract(self):
        result = self.client.get(reverse("discover-extract"), data={"url": self.feed_url}, format='json')
        assert result.data['name'] == "Feed1"
        assert result.data['url'] == "http://test.com/feed/"

    @patch("urllib.request.urlopen", Mock(return_value=StringIO(test_sites.FEED_WITHOUT_TITLE)))
    def test_extract_feed_without_title(self):
        result = self.client.get(reverse("discover-extract"), data={"url": self.feed_url}, format='json')
        assert result.status_code == status.HTTP_200_OK
        assert result.data['name'] == "http://test.com/feed/"
        assert result.data['url'] == "http://test.com/feed/"

    @patch("urllib.request.urlopen", Mock(return_value=StringIO(test_sites.NO_FEEDS)))
    def test_extract_empty_feed(self):
        result = self.client.get(reverse("discover-extract"), data={"url": self.feed_url}, format='json')
        assert result.status_code == status.HTTP_404_NOT_FOUND

    def test_extract_wrong_feed_url(self):
        result = self.client.get(reverse("discover-extract"), data={"url": self.wrong_feed_url}, format='json')
        assert result.status_code == status.HTTP_404_NOT_FOUND


class TestFeedDownloader(TestCase):
    fixtures = ['feeds', "feed_links"]

    def setUp(self):
        self.url = "http://test.xml"

    @patch("urllib.request.urlopen", Mock(return_value=StringIO(test_sites.FEED)))
    def test_get_posts(self):
        downloader = FeedDownloader(self.url)
        posts = downloader.get_posts()
        assert len(posts) == 2
        assert posts[0].title == 'Post1'
        assert posts[0].url == 'https://test.com/feed/Post1'
        assert posts[0].post_date == datetime(2018, 1, 31, 10, tzinfo=pytz.UTC)
        assert posts[1].title == 'Post2'
        assert posts[1].url == 'https://test.com/feed/Post2'
        assert posts[1].post_date == datetime(2018, 1, 30, 10, 0, 1, tzinfo=pytz.UTC)

    @patch("urllib.request.urlopen", Mock(return_value=StringIO(test_sites.FEED)))
    def test_get_posts_respect_limit(self):
        Feed.objects.all().update(postLimit=1)
        downloader = FeedDownloader(self.url)
        posts = downloader.get_posts()
        assert len(posts) == 1
        assert posts[0].title == 'Post1'
        assert posts[0].url == 'https://test.com/feed/Post1'
        assert posts[0].post_date == datetime(2018, 1, 31, 10, tzinfo=pytz.UTC)


class TestGetPosts(TestCase):
    fixtures = ['feeds', "get_posts"]

    def test_loop(self):
        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                    ("Post1", "https://test.com/feed/Post1", "2018-01-31T11:00:00"),
                    ("Post2", "https://test.com/feed/Post2", "2018-01-31T12:00:00")
                ])
            ))):
                result = get_posts()
        assert result['added'] == 4

    def test_loop_check_reg_exp(self):
        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1", "2018-01-31T11:00:00"),
                        ("News1", "https://test.com/feed/Post2", "2018-01-31T12:00:00")
                    ])
            ))):
                result = get_posts()
        assert result['added'] == 3

    def test_loop_update_url(self):
        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1", "2018-01-31T11:00:00"),
                        ("Post2", "https://test.com/feed/Post2", "2018-01-31T12:00:00")
                    ])
            ))):
                get_posts()

        with freeze_time("2018-01-31T15:00:00"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1_up", "2018-01-31T16:00:00"),
                    ])
            ))):
                result = get_posts()
        assert result["updated"] == 2

    def test_loop_update_title(self):
        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1", "2018-01-31T11:00:00"),
                        ("Post2", "https://test.com/feed/Post2", "2018-01-31T12:00:00")
                    ])
            ))):
                get_posts()

        with freeze_time("2018-01-31T15:00:00"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1.1", "https://test.com/feed/Post1", "2018-01-31T14:00:00"),
                    ])
            ))):
                result = get_posts()
        assert result["updated"] == 2

    def test_loop_update_title_of_old_watched_video(self):
        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1", "2018-01-31T11:00:00"),
                        ("Post2", "https://test.com/feed/Post2", "2018-01-31T12:00:00")
                    ])
            ))):
                get_posts()
                Post.objects.filter(title='Post1').update(view=True)

        with freeze_time("2018-01-31T15:00:00"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1.1", "https://test.com/feed/Post1", "2018-01-31T14:00:00"),
                    ])
            ))):
                result = get_posts()
        assert result["updated"] == 2

    def test_loop_update_older_then_last_add(self):
        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1", "2018-01-31T11:00:00"),
                        ("Post2", "https://test.com/feed/Post2", "2018-01-31T12:00:00")
                    ])
            ))):
                get_posts()

        with freeze_time("2018-01-31T15:00:00"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1_up", "2018-01-31T12:30:00"),
                    ])
            ))):
                result = get_posts()
        assert result["updated"] == 0
        assert result["added"] == 0

    def test_loop_add_new(self):
        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1", "2018-01-31T11:00:00"),
                        ("Post2", "https://test.com/feed/Post2", "2018-01-31T12:00:00")
                    ])
            ))):
                get_posts()

        with freeze_time("2018-01-31T15:00:00"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post3", "https://test.com/feed/Post3", "2018-01-31T14:00:00"),
                    ])
            ))):
                result = get_posts()
        assert result["added"] == 2

    def test_loop_try_add_older(self):
        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post1", "https://test.com/feed/Post1", "2018-01-31T11:00:00"),
                        ("Post2", "https://test.com/feed/Post2", "2018-01-31T12:00:00")
                    ])
            ))):
                get_posts()

        with freeze_time("2018-01-31T15:00:00"):
            with patch("urllib.request.urlopen", Mock(return_value=StringIO(
                    feed_creator("Feed1", "http://test.com/rss/feed.xml", [
                        ("Post3", "https://test.com/feed/Post3", "2018-01-31T12:00:00"),
                    ])
            ))):
                result = get_posts()

        assert result["updated"] == 0
        assert result["added"] == 0

    def test_loop_add_to_full_feed(self):
        def mock_feeds(link):
            return StringIO({
                "http://test.com/rss/feed2.xml":
                    feed_creator("Feed2", "http://test.com/rss/feed2.xml", [
                        ("Post1", "https://test.com/feed2/Post1", "2018-01-31T11:00:00"),
                        ("Post2", "https://test.com/feed2/Post2", "2018-01-31T12:00:00")
                    ])
            }.get(link.full_url, test_sites.EMPTY_FEED))

        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", Mock(side_effect=mock_feeds)):
                result = get_posts()
        assert result["added"] == 2
        assert result["deleted"] == 1

    def test_broken_links(self):

        with freeze_time("2018-01-31T13:00:01"):
            with patch("urllib.request.urlopen", side_effect=URLError('Broken link')):
                result = get_posts()

        assert result["updated"] == 0
        assert result["added"] == 0
        assert result["deleted"] == 0
