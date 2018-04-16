EMPTY_SITE = """
    <html>
        <head>
        </head>
    </html>"""

SITE = """
    <html>
        <head>
            <link rel="alternate" type="application/rss+xml" title="Example" href="http://test.com/feed/" />
            <link rel="alternate" type="application/rss+xml" title="Example" href="http://test.com/feed2/" />
        </head>
    </html>"""

NO_FEEDS = """
    <?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
    </rss>"""

EMPTY_FEED = """
    <?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
        <channel>
          <title>Feed1</title>
          <link>https://test.com/Feed1</link>
          <description>Feed</description>
        </channel>
    </rss>"""

FEED_WITHOUT_TITLE = """
    <?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
        <channel>
          <link>https://test.com/Feed1</link>
          <title></title>
          <description>Feed</description>
          <item>
            <title>Post1</title>
            <link>https://test.com/feed/Post1</link>
            <description>Post1</description>
          </item>
          <item>
            <title>Post2</title>
            <link>https://test.com/feed/Post2</link>
            <description>Post1</description>
          </item>
        </channel>
    </rss>"""

FEED = """
    <?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
        <channel>
          <title>Feed1</title>
          <link>https://test.com/Feed1</link>
          <description>Feed</description>
          <item>
            <title>Post1</title>
            <link>https://test.com/feed/Post1</link>
            <description>Post1</description>
            <published>2018-01-31T10:00:00</published>
          </item>
          <item>
            <title>Post2</title>
            <link>https://test.com/feed/Post2</link>
            <description>Post2</description>
            <published>2018-01-30T10:00:01</published>
          </item>
        </channel>
    </rss>"""

FEED2 = """
    <?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
        <channel>
          <title>Feed1</title>
          <link>https://test.com/Feed1</link>
          <description>Feed</description>
          <item>
            <title>Post3</title>
            <link>https://test.com/feed/Post3</link>
            <description>Post1</description>
            <published>2018-01-31T12:00:00</published>
          </item>
          <item>
            <title>Post4</title>
            <link>https://test.com/feed/Post4</link>
            <description>Post4</description>
            <published>2018-01-30T12:00:01</published>
          </item>
        </channel>
    </rss>"""
