"""Страница «Об Ассоциации»: документы и ссылки к блокам. Тексты блоков — в админке
(«Страница «Об Ассоциации»», по умолчанию — about_defaults)."""
import re
from types import SimpleNamespace

from .info_page import LICENSES, doc

# якорь в оглавлении и на странице → ключ блока (AboutSection.key)
ANCHORS = [('about', 'intro'), ('goals', 'goals'), ('directions', 'directions'), ('education', 'education'),
           ('documents', 'documents')]

# «Образовательная и просветительская деятельность»: ссылки (название, имя адреса, slug страницы)
EDUCATION_LINKS = [
    ('Программы', 'core:courses_list', None),
    ('Расписание курсов и семинаров', 'core:page_content', 'timetable'),
    ('Выездные семинары', 'core:page_content', 'seminars'),
    ('Сведения об образовательной организации', 'core:page_content', 'info'),
]
EDUCATION_DOCS = [
    doc('Положение об оказании платных образовательных услуг в Международной ассоциации поддержки и развития '
        'раннего и грудничкового плавания',
        'polojzenie-ob-okazanii-platnih-obrazovatelnih-uslug-v-mejzdunarodnoy-assoziazii-podderjzki-i-'
        'razvitiya-rannego-i-grudnichkovogo-plavaniya.pdf'),
    doc('Договор об оказании платных образовательных услуг (физические лица)',
        'dogovor-ob-okazanii-platnih-obrazovatelnih-uslug.pdf'),
    doc('Договор об оказании платных образовательных услуг (юридические лица)',
        'dogovor-ob-okazanii-platnih-obrazovatelnih-uslug-urliza.pdf'),
    doc('Правила приема слушателей на обучение по программам дополнительного профессионального образования',
        'pravila-priema-slushateley-na-obuchenie-po-programmam-dopolnitelnogo-professionalnogo-obrazovaniya.pdf'),
]
# лицензия — миниатюры, как в «Сведениях об образовательной организации»
EDUCATION_THUMBS = LICENSES[:2]

# «Документы, регламентирующие деятельность Ассоциации»: свидетельства — миниатюрами, устав — строкой
REGISTRATION_THUMBS = [
    SimpleNamespace(title='Свидетельство о регистрации организации',
                    path='documents/svidetelstvo-o-registraziy-organyzaziy.pdf',
                    thumb='documents/svidetelstvo-1.thumb.jpg'),
    SimpleNamespace(title='Свидетельство о государственной регистрации юридического лица',
                    path='documents/svidetelstvo-o-gosregistraziy-yridicheskogo-litza.pdf',
                    thumb='documents/svidetelstvo-2.thumb.jpg'),
    SimpleNamespace(title='Свидетельство о постановке на учёт',
                    path='documents/svidetelstvo-o-postanovke-na-uchet-assoziaziya.pdf',
                    thumb='documents/svidetelstvo-3.thumb.jpg'),
]
CHARTER = doc('Устав Международной ассоциации поддержки и развития раннего и грудничкового плавания',
              'ustav-mejzdunarodnoy-assoziazii-podderjzki-i-razvitiya-rannego-i-grudnichkovogo-plavaniya.pdf')


def numbered_items(text):
    """Абзацы «1. …», «2. …» → пункты списка без номеров. Если хоть один абзац без номера — None:
    текст показывается абзацами, как его написали в админке."""
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text or '') if p.strip()]
    if paragraphs and all(re.match(r'\d+[.)]\s', p) for p in paragraphs):
        return [re.sub(r'^\d+[.)]\s*', '', p) for p in paragraphs]
    return None
