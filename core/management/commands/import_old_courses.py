"""Импорт курсов и расписания со старого сайта grudnichkovoe-plavanie.ru.

    python manage.py import_old_courses            # импорт
    python manage.py import_old_courses --dry-run  # только показать, что будет импортировано

Берёт все записи со страницы /education/timetable, для каждой даты открывает страницу
курса и переносит: название, часы, описание (краткое + развёрнутое), «для кого», программу,
преподавателей (с фотографиями), тип курса, базовую стоимость и расписание.

Тип курса — по формату дат на старом сайте: «Онлайн…» — онлайн, «Дистанционное обучение…» —
дистанционный, адрес — очный. У очных и онлайн-курсов каждая дата становится записью расписания
(адрес — в комментарии), у дистанционных — одна запись со сроком доступа в днях.

Повторный запуск обновляет те же записи: курс ищется по адресу (slug) старого сайта, запись
расписания — по курсу и дате начала. Формат и комментарий, изменённые в админке, не затираются.
Направление, место, навыки, возраст и особенности здоровья на старом сайте не указаны —
их нужно заполнить в админке.
"""
import html
import re
import time
from collections import Counter
from datetime import datetime
from io import BytesIO
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.legacy_cards import assign_course_cards
from core.legacy_directions import LEGACY_DIRECTIONS
from core.models import Course, CourseCard, CourseSchedule, CourseTeacher, Teacher

BASE_URL = 'https://www.grudnichkovoe-plavanie.ru/'
USER_AGENT = 'Mozilla/5.0 (course import)'


def html_to_text(fragment):
    """HTML старого сайта → текст: абзацы через пустую строку, <br> — перенос строки."""
    s = re.sub(r'(?s)<!--.*?-->', '', fragment)
    s = re.sub(r'\s+', ' ', s)  # переводы строк в исходном HTML — это просто пробелы
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'(?i)</(p|div|h[1-6]|ul|ol)>', '\n\n', s)
    s = re.sub(r'(?i)<li[^>]*>', '\n• ', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).replace('\xa0', ' ')
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in s.split('\n')]
    s = '\n'.join(lines)
    return re.sub(r'\n{3,}', '\n\n', s).strip()


def inline_text(fragment):
    return re.sub(r'\s+', ' ', html_to_text(fragment)).strip()


def nice_case(text):
    """«ОНЛАЙН» → «Онлайн», «ДИСТАНЦИОННОЕ ОБУЧЕНИЕ» → «Дистанционное обучение»."""
    return text.capitalize() if text.isupper() else text


SHORT_DESCRIPTION_LIMIT = 320


def split_description(text, limit=SHORT_DESCRIPTION_LIMIT):
    """Краткое описание — первые предложения в пределах limit символов, развёрнутое — продолжение."""
    text = (text or '').strip()
    if len(text) <= limit:
        return text, ''
    ends = [m.end() for m in re.finditer(r'[.!?…](?=\s)', text)]
    fitting = [e for e in ends if e <= limit]
    if fitting:
        cut = fitting[-1]
    elif ends and ends[0] <= 2 * limit:
        cut = ends[0]  # первое предложение длинное, но берём его целиком
    else:
        words = text[:limit].rsplit(' ', 1)[0]
        return words.rstrip(' ,;:—-') + '…', text  # не режем предложение: полный текст — в развёрнутом
    return text[:cut].strip(), text[cut:].strip()


def location_kind(location):
    """Тип курса по месту проведения со старого сайта: online / distance / in_person"""
    loc = (location or '').strip().lower()
    if not loc:
        return ''
    if loc.startswith('онлайн'):
        return Course.TYPE_ONLINE
    if loc.startswith('дистанц'):
        return Course.TYPE_DISTANCE
    return Course.TYPE_IN_PERSON


def parse_full_price(price):
    """«22 800 руб, для членов Ассоциации — 18 240 руб» → 22800 (полная цена)"""
    m = re.match(r'\s*([\d\s\u00a0]+)', price or '')
    digits = re.sub(r'\D', '', m.group(1)) if m else ''
    return int(digits) if digits else None


def parse_date(value):
    return datetime.strptime(value.strip(), '%d.%m.%Y').date()


def parse_timetable(page):
    """Записи расписания: ссылка на курс/дату, даты, часы, цена «от …» из списка."""
    rows = []
    for box in re.findall(r'(?s)<div class="edu-schedule-box">(.*?)</h2>\s*</div>', page):
        box = re.sub(r'(?s)<!--.*?-->', '', box)
        dates = re.search(r'<span class="date">\s*([\d.]+)\s*—\s*([\d.]+)\s*</span>', box)
        link = re.search(r'(?s)<h2[^>]*>\s*<a href="([^"]+)">', box)
        hours = re.search(r'<span class="time">\s*(\d+)', box)
        if not (dates and link):
            continue
        href = link.group(1)
        match = re.match(r'/?education/courses/([^/]+)/(\d+)', href)
        if not match:
            continue
        rows.append({
            'slug': match.group(1),
            'href': href,
            'start': parse_date(dates.group(1)),
            'end': parse_date(dates.group(2)),
            'hours': int(hours.group(1)) if hours else 0,
        })
    return rows


def parse_course_page(page):
    content = page[page.find('<!-- CONTENT'):page.find('<!-- FOOTER')] or page
    content = re.sub(r'(?s)<!--.*?-->', '', content)

    def find(pattern, group=1):
        m = re.search(pattern, content, re.S)
        return m.group(group) if m else ''

    title = inline_text(find(r'<h2 class="large">(.*?)</h2>'))
    kind = inline_text(find(r'<p class="middle-outline"[^>]*>(.*?)</p>\s*<h2 class="large">'))
    kind = kind[:1].upper() + kind[1:]  # на старом сайте встречается и «семинар», и «Семинар»
    hours = find(r'hours-marker[^>]*>\s*(\d+)')

    teachers = []
    for img, first, last in re.findall(
            r'(?s)<p class="fio-title">\s*<img src="([^"]+)"[^>]*>\s*(.*?)<br>\s*<b>(.*?)</b>', content):
        teachers.append({'photo': img, 'first_name': inline_text(first), 'last_name': inline_text(last)})

    description = html_to_text(find(r'<p class="large-text"[^>]*>(.*?)</p>'))
    audience = html_to_text(find(r'<p class="?accent"?[^>]*>(.*?)</p>'))

    program = ''
    start = content.find('<h3>Рассматриваемые темы</h3>')
    if start != -1:
        end = content.find('<div class="block-container', start)
        program = html_to_text(content[start + len('<h3>Рассматриваемые темы</h3>'):end if end != -1 else None])

    # «Где проходят занятия?» — место и уточнение (клуб, ZOOM и т.п.)
    location = ''
    where = re.search(r'(?s)Где проходят занятия\?</h2>\s*<p>(.*?)</p>\s*(?:<p class="small-text">(.*?)</p>)?', content)
    if where:
        place = nice_case(inline_text(where.group(1)).rstrip(', '))
        detail = inline_text(where.group(2) or '')
        location = f'{place} — {detail}' if place and detail else place or detail

    # «Стоимость» — полная цена и цена для членов Ассоциации
    price = ''
    cost = re.search(r'(?s)<h2 class="small"[^>]*>Стоимость</h2>(.*?)</div>', content)
    if cost:
        amounts = [inline_text(a) for a in re.findall(r'<p class="outline"[^>]*>(.*?)</p>', cost.group(1))]
        amounts = [re.sub(r'\s*руб$', ' руб', a) for a in amounts if a]
        if len(amounts) >= 2:
            price = f'{amounts[0]}, для членов Ассоциации — {amounts[1]}'
        elif amounts:
            price = amounts[0]

    return {
        'title': title, 'kind': kind, 'hours': int(hours) if hours else 0, 'teachers': teachers,
        'description': description, 'audience': audience, 'program': program,
        'location': location[:255], 'price': price[:100],
    }


class Command(BaseCommand):
    help = 'Импортирует курсы и расписание со старого сайта grudnichkovoe-plavanie.ru'

    def add_arguments(self, parser):
        parser.add_argument('--base-url', default=BASE_URL)
        parser.add_argument('--dry-run', action='store_true', help='Ничего не сохранять, только показать')
        parser.add_argument('--no-photos', action='store_true', help='Не скачивать фотографии преподавателей')
        parser.add_argument('--delay', type=float, default=0.2, help='Пауза между запросами, секунд')

    def fetch(self, url, binary=False):
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers={'User-Agent': USER_AGENT}), timeout=30) as resp:
                    data = resp.read()
                time.sleep(self.delay)
                return data if binary else data.decode('utf-8', errors='replace')
            except (URLError, TimeoutError) as exc:
                if attempt == 2:
                    raise CommandError(f'Не удалось загрузить {url}: {exc}')
                time.sleep(2)

    def handle(self, *args, **opts):
        self.base = opts['base_url'].rstrip('/') + '/'
        self.delay = opts['delay']
        dry = opts['dry_run']

        rows = parse_timetable(self.fetch(urljoin(self.base, 'education/timetable')))
        if not rows:
            raise CommandError('В расписании старого сайта не найдено ни одной записи')

        # Одна ссылка (курс + дата) может встречаться в расписании несколько раз — берём один раз
        unique = {}
        for row in rows:
            unique.setdefault((row['slug'], row['start']), row)
        self.stdout.write(f'Записей в расписании: {len(rows)}, уникальных дат: {len(unique)}, '
                          f'курсов: {len({r["slug"] for r in unique.values()})}')

        pages = {}
        for i, row in enumerate(unique.values(), 1):
            pages[(row['slug'], row['start'])] = parse_course_page(self.fetch(urljoin(self.base, row['href'])))
            if i % 20 == 0:
                self.stdout.write(f'  загружено страниц: {i}/{len(unique)}')

        if dry:
            for (slug, start), data in pages.items():
                self.stdout.write(f'{start:%d.%m.%Y}  {slug:28} {data["title"][:60]} | {data["location"][:40]} | {data["price"]}')
            self.stdout.write(self.style.WARNING('--dry-run: изменения не сохранены'))
            return

        photo_cache = {}
        stats = {'courses_new': 0, 'courses_upd': 0, 'schedules_new': 0, 'schedules_upd': 0, 'teachers_new': 0}
        # Группируем даты по курсам, сохраняя порядок первого появления в расписании
        by_course = {}
        for (slug, start), data in pages.items():
            by_course.setdefault(slug, []).append((start, data))

        with transaction.atomic():
            for order, (slug, sessions) in enumerate(by_course.items(), 1):
                data = sessions[0][1]  # описание курса одинаково на страницах всех его дат
                kinds = Counter(location_kind(d['location']) for _, d in sessions if location_kind(d['location']))
                prices = Counter(parse_full_price(d['price']) for _, d in sessions if parse_full_price(d['price']))
                course_type = kinds.most_common(1)[0][0] if kinds else ''
                base_price = prices.most_common(1)[0][0] if prices else None
                short, full = split_description(data['description'])
                course, created = Course.objects.update_or_create(slug=slug, defaults={
                    'title': data['title'] or slug,
                    'short_description': short,
                    'full_description': full,
                    'hours': data['hours'] or unique[(slug, sessions[0][0])]['hours'],
                    'audience': data['audience'],
                    'program': data['program'],
                    'course_type': course_type,
                    'base_price': base_price,
                    'order': order,
                    'is_active': True,
                })
                stats['courses_new' if created else 'courses_upd'] += 1
                if not course.direction and slug in LEGACY_DIRECTIONS:
                    course.direction = LEGACY_DIRECTIONS[slug]  # направления на старом сайте нет
                    course.save(update_fields=['direction'])

                for position, t in enumerate(data['teachers']):
                    teacher, t_created = Teacher.objects.get_or_create(
                        first_name=t['first_name'], last_name=t['last_name'])
                    stats['teachers_new'] += t_created
                    if not teacher.photo and not opts['no_photos'] and t['photo']:
                        self.save_photo(teacher, urljoin(self.base, t['photo']), photo_cache)
                    CourseTeacher.objects.update_or_create(
                        course=course, teacher=teacher, defaults={'order': position})

                def override(price):
                    return price if price and price != base_price else None

                dated = sessions
                if course_type == Course.TYPE_DISTANCE:
                    # у дистанционных курсов дат нет — одна запись со сроком доступа
                    distance = [(st, d) for st, d in sessions if location_kind(d['location']) == Course.TYPE_DISTANCE]
                    dated = [(st, d) for st, d in sessions if location_kind(d['location']) != Course.TYPE_DISTANCE]
                    days = Counter((unique[(slug, st)]['end'] - st).days + 1 for st, _ in distance)
                    access = next((n for n, _ in days.most_common() if n > 0), None)
                    price = Counter(parse_full_price(d['price']) for _, d in distance).most_common(1)[0][0]
                    self.upsert_schedule(stats, course, None, {
                        'access_days': access, 'price_override': override(price),
                    }, on_create={'format': 'group'})

                for start, session_data in dated:
                    location = session_data['location']
                    in_moscow = location.strip().lower().startswith('москва')
                    away = location_kind(location) == Course.TYPE_IN_PERSON and not in_moscow
                    self.upsert_schedule(stats, course, start, {
                        'end_date': unique[(slug, start)]['end'],
                        'price_override': override(parse_full_price(session_data['price'])),
                    }, on_create={
                        'format': 'away' if away else 'group',
                        'comment': location if location_kind(location) != Course.TYPE_DISTANCE else '',
                    })

        # новые курсы — по карточкам страницы «Программы» (варианты одного курса — вместе)
        stats['cards_new'] = assign_course_cards(Course, CourseCard)

        self.stdout.write(self.style.SUCCESS(
            f'Готово. Курсы: новых {stats["courses_new"]}, обновлено {stats["courses_upd"]}. '
            f'Записи расписания: новых {stats["schedules_new"]}, обновлено {stats["schedules_upd"]}. '
            f'Новых преподавателей: {stats["teachers_new"]}. Новых карточек курсов: {stats["cards_new"]}.'))

    def upsert_schedule(self, stats, course, start_date, values, on_create):
        """Запись расписания по курсу и дате начала (у дистанционных — без даты).
        Формат и комментарий задаются только при создании, чтобы не затирать правки из админки."""
        schedule = (CourseSchedule.objects.filter(course=course, start_date=start_date)
                    .order_by('pk').first())
        if schedule is None:
            CourseSchedule.objects.create(course=course, start_date=start_date, **values, **on_create)
            stats['schedules_new'] += 1
        else:
            for field, value in values.items():
                setattr(schedule, field, value)
            schedule.save()
            stats['schedules_upd'] += 1

    def save_photo(self, teacher, url, cache):
        if url not in cache:
            try:
                raw = self.fetch(url, binary=True)
                from PIL import Image
                Image.open(BytesIO(raw)).verify()  # убедиться, что это изображение
                cache[url] = raw
            except Exception as exc:  # фото не критично для импорта
                self.stderr.write(f'  фото не загружено ({url}): {exc}')
                cache[url] = None
        if cache[url]:
            name = f'{teacher.last_name}-{teacher.first_name}-{url.rsplit("/", 1)[-1]}'
            teacher.photo.save(name, ContentFile(cache[url]), save=True)
