"""Импорт партнёров со старого сайта grudnichkovoe-plavanie.ru/partners/.

    python manage.py import_old_partners            # импорт
    python manage.py import_old_partners --dry-run  # только показать, что будет импортировано

Переносит название, описание, логотип, город, страну и сайт. Повторный запуск обновляет
тех же партнёров (поиск по названию); логотип скачивается, только если его ещё нет.
"""
import re
from io import BytesIO
from urllib.parse import urljoin

from django.core.files.base import ContentFile
from django.core.management.base import CommandError

from core.management.commands.import_old_courses import (
    BASE_URL, Command as CourseImportCommand, html_to_text, inline_text,
)
from core.models import Partner


def parse_partners(page):
    content = page[page.find('<!-- CONTENT'):page.find('<!-- FOOTER')] or page
    content = re.sub(r'(?s)<!--.*?-->', '', content)
    partners = []
    for box in re.findall(r'(?s)<div class="partner-box">(.*?)<p class="website">.*?</div>', content):
        logo = re.search(r'<img src="([^"]+)"', box)
        site = re.search(r'<a href="([^"]+)"', box)
        name = re.search(r'(?s)<h3>(.*?)</h3>', box)
        description = re.search(r'(?s)</h3>\s*<p>(.*?)</p>', box)
        location = re.search(r'(?s)<p class="location">(.*?)</p>', box)
        city, _, country = inline_text(location.group(1)).partition('•') if location else ('', '', '')
        partners.append({
            'name': inline_text(name.group(1)) if name else '',
            'description': html_to_text(description.group(1)) if description else '',
            'logo': logo.group(1) if logo else '',
            'website': site.group(1) if site else '',
            'city': city.strip(),
            'country': country.strip(),
        })
    return [p for p in partners if p['name']]


class Command(CourseImportCommand):
    help = 'Импортирует партнёров со старого сайта grudnichkovoe-plavanie.ru'

    def add_arguments(self, parser):
        parser.add_argument('--base-url', default=BASE_URL)
        parser.add_argument('--dry-run', action='store_true', help='Ничего не сохранять, только показать')
        parser.add_argument('--delay', type=float, default=0.2, help='Пауза между запросами, секунд')

    def handle(self, *args, **opts):
        self.base = opts['base_url'].rstrip('/') + '/'
        self.delay = opts['delay']
        partners = parse_partners(self.fetch(urljoin(self.base, 'partners/')))
        if not partners:
            raise CommandError('На странице партнёров старого сайта никого не найдено')

        if opts['dry_run']:
            for p in partners:
                self.stdout.write(f'{p["name"]:40} {p["city"]} • {p["country"]} | {p["website"]} | {p["logo"]}')
            self.stdout.write(self.style.WARNING('--dry-run: изменения не сохранены'))
            return

        created_count = 0
        for order, data in enumerate(partners, 1):
            logo_url = data.pop('logo')
            partner, created = Partner.objects.update_or_create(
                name=data['name'], defaults={**data, 'order': order, 'is_active': True})
            created_count += created
            if logo_url and not partner.logo:
                raw = self.fetch(urljoin(self.base, logo_url), binary=True)
                from PIL import Image
                Image.open(BytesIO(raw)).verify()  # убедиться, что это изображение
                partner.logo.save(logo_url.rsplit('/', 1)[-1], ContentFile(raw), save=True)

        self.stdout.write(self.style.SUCCESS(
            f'Готово. Партнёров: новых {created_count}, обновлено {len(partners) - created_count}.'))
