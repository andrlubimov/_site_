"""Начальное наполнение сайта конвенции — со старого сайта convent.grudnichkovoe-plavanie.ru (по web.archive.org):
конвенции 6–14, программа 13-й по дням, партнёры, спикеры, оргкомитет, фотоконкурс, документы.
data.json и файлы (files/) собраны из архива; загружает миграция 0002 — только в пустую базу конвенции."""
import json
from datetime import date, time
from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage

SEED_DIR = Path(__file__).resolve().parent


def stored(name, folder):
    """Файл из seed/files — в хранилище (media), под постоянным именем: повторная загрузка не плодит копии"""
    if not name:
        return ''
    target = folder + Path(name).name
    if not default_storage.exists(target):
        with open(SEED_DIR / 'files' / name, 'rb') as f:
            target = default_storage.save(target, File(f))
    return target


def load(apps):
    Convention = apps.get_model('convention', 'Convention')
    if Convention.objects.exists():  # уже заполнено или заведено вручную
        return
    Venue = apps.get_model('convention', 'Venue')
    EventType = apps.get_model('convention', 'EventType')
    Speaker = apps.get_model('convention', 'Speaker')
    Partner = apps.get_model('convention', 'Partner')
    Organizer = apps.get_model('convention', 'Organizer')

    data = json.loads((SEED_DIR / 'data.json').read_text(encoding='utf-8'))
    venues = {key: Venue.objects.create(**fields) for key, fields in data['venues'].items()}
    types = {t['name']: EventType.objects.create(**t) for t in data['event_types']}
    speakers = {
        s['name']: Speaker.objects.create(name=s['name'], details=s['details'],
                                          photo=stored(s['photo'], 'convention/speakers/'))
        for s in data['speakers']
    }
    partners = {
        p['name']: Partner.objects.create(name=p['name'], website=p['website'], headline=p['headline'],
                                          description=p['description'],
                                          logo=stored(p['logo'], 'convention/partners/'))
        for p in data['partners']
    }
    for order, o in enumerate(data['organizers'], 1):
        Organizer.objects.create(group=o['group'], name=o['name'], role=o['role'], phone=o['phone'],
                                 email=o['email'], photo=stored(o['photo'], 'convention/organizers/'), order=order)

    for c in data['conventions']:
        c = dict(c)
        days = c.pop('days', [])
        prices = c.pop('prices', [])
        partner_names = c.pop('partners', [])
        featured = c.pop('featured', [])
        winners = c.pop('photo_winners', [])
        venue = venues.get(c.pop('venue', None))
        for field, folder in [('schedule_file', 'convention/archive/'), ('regulations', 'convention/docs/'),
                              ('offer', 'convention/docs/'), ('price_list', 'convention/docs/')]:
            c[field] = stored(c.get(field, ''), folder)
        c['start_date'] = date.fromisoformat(c['start_date'])
        c['end_date'] = date.fromisoformat(c['end_date'])
        convention = Convention.objects.create(venue=venue, **c)

        for d in days:
            day = convention.days.create(date=date.fromisoformat(d['date']))
            for order, a in enumerate(d['activities'], 1):
                day.activities.create(title=a['title'], hall=a['hall'], venue=venues.get(a.get('venue')), order=order)
            for e in d['events']:
                event = day.events.create(section=e['section'], time=time.fromisoformat(e['time']),
                                          location=e['location'], event_type=types[e['type']],
                                          title=e['title'], topic=e['topic'])
                event.speakers.set([speakers[name] for name in e['speakers']])
        for order, p in enumerate(prices, 1):
            convention.prices.create(order=order, **p)
        for order, name in enumerate(partner_names, 1):
            convention.partnerships.create(partner=partners[name], is_general_sponsor=order == 1, order=order)
        for order, f in enumerate(featured, 1):
            convention.featured_speakers.create(speaker=speakers[f['speaker']], caption=f['caption'], order=order)
        for w in winners:
            convention.photo_winners.create(place=w['place'], author=w['author'],
                                            photo=stored(w['photo'], 'convention/photo-contest/'))
