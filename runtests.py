import os
import sys

import django
from django.conf import settings
from django.test.runner import DiscoverRunner

DIRNAME = os.path.dirname(__file__)

settings.configure(
    DEBUG=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
        }
    },
    INSTALLED_APPS=(
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.admin',
        'feeds'
    ),
    REST_FRAMEWORK={
        'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',)
    },
    USE_TZ=True,
    TIME_ZONE='UTC',
    ROOT_URLCONF='feeds.urls',
)

django.setup()
failures = DiscoverRunner(
    verbosity=1, interactive=True, failfast=False).run_tests(["feeds"])
sys.exit(failures)
