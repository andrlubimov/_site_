from unittest.mock import patch

from django.db import OperationalError
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase

from .models import PageContent
from .views import page_content


class PageContentViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('core.views.PageContent.objects.filter')
    def test_about_page_renders_with_fallback_when_record_missing(self, mock_filter):
        mock_filter.return_value.first.return_value = None

        response = page_content(self.factory.get('/page/about/'), 'about')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Об Ассоциации')

    @patch('core.views.PageContent.objects.filter')
    def test_unknown_slug_still_returns_404(self, mock_filter):
        mock_filter.return_value.first.return_value = None

        with self.assertRaises(Http404):
            page_content(self.factory.get('/page/unknown/'), 'unknown')

    @patch('core.views.PageContent.objects.filter')
    def test_existing_page_content_is_used(self, mock_filter):
        mock_filter.return_value.first.return_value = PageContent(
            slug='about',
            title='Тестовый заголовок',
            content='Тестовый текст',
        )

        response = page_content(self.factory.get('/page/about/'), 'about')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый заголовок')
        self.assertContains(response, 'Тестовый текст')

    @patch('core.views.PageContent.objects.filter')
    def test_about_page_renders_when_database_unavailable(self, mock_filter):
        mock_filter.side_effect = OperationalError('db unavailable')

        response = page_content(self.factory.get('/page/about/'), 'about')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Об Ассоциации')
