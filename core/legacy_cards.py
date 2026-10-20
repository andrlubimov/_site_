"""Карточки курсов для страницы «Программы»: какие курсы со старого сайта показываются одной карточкой.

В карточку объединены варианты одного курса — пакеты «Студент»/«Специалист», семинар и повышение
квалификации. Порядок курсов внутри карточки — порядок строк в ней; краткое описание карточки
берётся из первого курса. Используется миграцией 0019 и командой import_old_courses: раскладывает
только курсы, у которых карточки ещё нет (правки из админки не затираются).

Формат: (название карточки, [(адрес курса, подпись варианта), …]).
"""
STUDENT = 'Пакет «Студент»'
SPECIALIST = 'Пакет «Специалист»'
SEMINAR = 'Семинар'
PRACTICUM = 'Семинар-практикум'
QUALIFICATION = 'Повышение квалификации'

LEGACY_CARDS = [
    # --- Гидрореабилитация ---
    ('Гидрореабилитация детей с нарушениями здоровья и развития. Введение',
     [('hydrorehabilitation', SEMINAR), ('hydrorehabilitationprofessional', QUALIFICATION)]),
    ('Гидрореабилитация детей с нарушениями речи, психики, поведения',
     [('speech', PRACTICUM), ('speechadvanced', QUALIFICATION)]),
    ('Грудничковое плавание. Коррекционно-диагностическая работа',
     [('korrektsionnayarabota2', SEMINAR), ('korrektsionnayarabota', QUALIFICATION)]),
    ('Коррекционное плавание при нарушениях осанки и сколиозе',
     [('recreationalswimmingPK', SEMINAR), ('recreationalswimmingPK2', QUALIFICATION)]),
    ('Недоношенные дети. Основные проблемы ранней и поздней реабилитации. '
     'Роль грудничкового плавания в физической реабилитации недоношенных детей',
     [('prematurebabies', STUDENT), ('prematurebabiesspecialist', SPECIALIST)]),
    ('Гидрокинезотерапия детей с трисомией 21 хромосомы (синдром Дауна)',
     [('sindromDauna', STUDENT), ('sindromDauna2', SPECIALIST)]),
    ('Медицинский ликбез для специалистов по грудничковому и раннему плаванию',
     [('medlikbezall3', STUDENT), ('medlikbezspecialist', SPECIALIST)]),
    ('Принципы эффективного общения с родителями особенных детей. '
     'Базовые коммуникационные компетенции реабилитолога',
     [('specialparents-online', STUDENT), ('specialparents-online2', SPECIALIST)]),
    ('Психосоматика расстройств аутистического спектра (РАС)',
     [('psychosomaticsofraces', SEMINAR)]),
    ('Работа в воде с гиперактивными детьми. Педагогические аспекты',
     [('hyperactivechildrenONL', SEMINAR)]),
    ('Оздоровление и тренировка детей от 1 месяца струйным тренажёром «Душ Алексеева» '
     'по авторской методике «Акваджет тиксотренинг»',
     [('aquajet', PRACTICUM)]),
    ('Акваджет тиксотренинг Душем Алексеева для беременных женщин и женщин послеродового периода',
     [('thixotrainingpregnant', STUDENT), ('thixotrainingpregnant2', SPECIALIST)]),
    ('Акваджет тиксотренинг Душем Алексеева в работе с плоскостопием',
     [('thixotrainingflatfeet', STUDENT), ('thixotrainingflatfeet2', SPECIALIST)]),
    ('Акваджет тиксотренинг Душем Алексеева в работе с остеохондрозом и болями в суставах',
     [('thixotrainingosteochondrosis', STUDENT), ('thixotrainingosteochondrosis2', SPECIALIST)]),
    ('Акваджет тиксотренинг Душем Алексеева в работе с логопедическими проблемами '
     'и нарушениями сенсорной интеграции',
     [('logoaquadget', STUDENT), ('logoaquadget2', SPECIALIST)]),
    ('Акваджет тиксотренинг Душем Алексеева в работе с сезонными инфекционными заболеваниями '
     'у детей и взрослых',
     [('thixotraininginfection', STUDENT), ('thixotraininginfection2', SPECIALIST)]),
    ('Акваджет тиксотренинг Душем Алексеева в работе с варикозом',
     [('thixotrainingofvaricoseveins2', STUDENT), ('thixotrainingofvaricoseveins', SPECIALIST)]),
    ('Акваджет тиксотренинг Душем Алексеева в работе с целлюлитом',
     [('thixotrainingcellulite', STUDENT), ('cellulitespecialist', SPECIALIST)]),
    ('Акваджет тиксотренинг Душем Алексеева в работе с брюшным апоневрозом — обвисанием «фартука» живота',
     [('thixotrainingabdominalaponeurosis', STUDENT), ('thixotrainingabdominalaponeurosis2', SPECIALIST)]),
    ('Акваджет тиксотренинг Душем Алексеева в работе с признаками старения лица и шеи',
     [('thixotrainingagingface', STUDENT), ('thixotrainingagingface2', SPECIALIST)]),

    # --- Плавание ---
    ('Грудничковое плавание. Базовый модуль. Работа в бассейне',
     [('gp-base-pool3', SEMINAR), ('gp-base-pool1onl', QUALIFICATION)]),
    ('Грудничковое плавание. Базовый модуль. Работа на ваннах',
     [('gp-base-bath3onl', SEMINAR)]),
    ('Аквапренатальная подготовка для беременных',
     [('water-aerobics-pregnant-3', SEMINAR)]),
    ('Динамическая гимнастика на занятиях в воде',
     [('dinamichkavvode', SEMINAR)]),
    ('Игры при обучении плаванию детей от 1 года до 3 лет. Авторская программа Марины Мониной',
     [('gaming-technology-water', SEMINAR)]),
    ('Плавание для детей раннего возраста от 1 года до 4 лет',
     [('earlyswimming', SEMINAR), ('ranneyplavaniyePK', QUALIFICATION)]),
    ('Обучение плаванию детей дошкольного и школьного возраста',
     [('distantstyles2', SEMINAR), ('distantstyles', QUALIFICATION)]),
    ('Методика обучения стилям плавания детей дошкольного и школьного возраста. '
     'Коррекционное плавание при нарушениях осанки и сколиозе',
     [('professionalstyles', QUALIFICATION)]),
    ('Работа с детьми дошкольного и младшего школьного возраста. Освоение спортивных способов плавания',
     [('doshkolniki-plavanie', SEMINAR), ('doshkolnikitraining', QUALIFICATION)]),
    ('Моторный онтогенез как инструмент работы в воде',
     [('motornyiontogenez2', SEMINAR), ('motornyiontogenez', QUALIFICATION)]),

    # --- Сухопутные ---
    ('Патронажное искусство. Специфика и особенности работы с новорождёнными',
     [('nursing-art-basic2', STUDENT), ('patronageart2', SPECIALIST)]),
    ('Патронажное искусство. Часть 2. Работа с детьми от 2 до 6 месяцев',
     [('advanced', STUDENT), ('advanced2', SPECIALIST)]),
    ('Патронажное искусство. Грудное вскармливание',
     [('grudnoyevskarmlivaniye', STUDENT), ('grudnoyevskarmlivaniye2', SPECIALIST)]),

    # --- Администрирование ---
    ('Практический тренинг по продажам в акваклубе',
     [('sales', 'Тренинг')]),
    ('Эффективное управление акваклубом. Юридические, кадровые и психологические аспекты деятельности',
     [('juristik2', SEMINAR)]),
    ('Администратор акваклуба. Профессиональные стандарты, работа с клиентами, '
     'прививка от эмоционального выгорания',
     [('administrator2', SEMINAR)]),
]


def assign_course_cards(Course, CourseCard):
    """Раскладывает по карточкам курсы, у которых карточки ещё нет.

    Сначала — по LEGACY_CARDS (если карточка с таким названием уже есть, курс добавляется в неё),
    затем каждый оставшийся курс получает собственную карточку. Принимает классы моделей,
    поэтому работает и в миграции (исторические модели), и в команде импорта.
    Возвращает число созданных карточек.
    """
    created = 0
    for order, (title, members) in enumerate(LEGACY_CARDS, 1):
        courses = {c.slug: c for c in Course.objects.filter(slug__in=[slug for slug, _ in members], card=None)}
        if not courses:
            continue
        card = CourseCard.objects.filter(title=title).first()
        if card is None:
            card = CourseCard.objects.create(title=title, order=order * 10)
            created += 1
        taken = Course.objects.filter(card=card).count()
        for position, (slug, label) in enumerate(members, taken):
            course = courses.get(slug)
            if course is None:
                continue
            course.card = card
            course.card_position = position
            if not course.variant_label:
                course.variant_label = label
            course.save(update_fields=['card', 'card_position', 'variant_label'])
        if card.description_course_id is None:
            # описание — из первого курса карточки, у которого оно заполнено
            in_card = list(Course.objects.filter(card=card).order_by('card_position', 'pk'))
            card.description_course = next((c for c in in_card if c.short_description.strip()), in_card[0])
            card.save(update_fields=['description_course'])

    start = (len(LEGACY_CARDS) + 1) * 10
    for offset, course in enumerate(Course.objects.filter(card=None).order_by('order', 'pk')):
        card = CourseCard.objects.create(title=course.title, order=start + offset * 10, description_course=course)
        course.card = card
        course.card_position = 0
        course.save(update_fields=['card', 'card_position'])
        created += 1
    return created
