"""Характеристики курсов для фильтров на странице «Программы» (по адресу курса).

На старом сайте их не было — они определены по названию, описанию, программе и «Для кого».
Используется миграцией 0021 и командой import_old_courses: заполняет поле, только если оно
ещё пустое (правки из админки не затираются).

Возраст детей: infant — грудной (0–1), early — ранний (1–3), preschool — дошкольный (4–7).
Особенности здоровья: normotypical — нормотипичные, special_care — особой заботы, pregnant — беременные.
Место: pool — бассейн, gym — спортзал, home — на дому.
Уровень учащегося: beginner — новичок, basic — есть практика и базовый курс, advanced — продвинутый.

У курсов для взрослых (Акваджет при варикозе, целлюлите и т. п.) и у курсов для руководителей
и администраторов акваклубов возраст детей и особенности здоровья не указываются — к детям
они прямого отношения не имеют.
"""
ALL_AGES = ('infant', 'early', 'preschool')


def _attrs(ages=(), health=(), venue='', skill=''):
    return {'ages': tuple(ages), 'health': tuple(health), 'venue': venue, 'skill': skill}


def _pair(slugs, **attrs):
    """Варианты одного курса (семинар и повышение квалификации, пакеты) — с одинаковыми характеристиками"""
    return {slug: _attrs(**attrs) for slug in slugs}


LEGACY_ATTRIBUTES = {
    # --- Гидрореабилитация ---
    **_pair(['hydrorehabilitation', 'hydrorehabilitationprofessional'],
            ages=ALL_AGES, health=['special_care'], venue='pool', skill='beginner'),
    'speech': _attrs(ages=['early', 'preschool'], health=['special_care'], venue='pool', skill='basic'),
    'speechadvanced': _attrs(ages=['early', 'preschool'], health=['special_care'], venue='pool', skill='advanced'),
    # для практикующих специалистов со стажем от года
    **_pair(['korrektsionnayarabota2', 'korrektsionnayarabota'],
            ages=['infant', 'early'], health=['normotypical', 'special_care'], venue='pool', skill='advanced'),
    # нарушения осанки и сколиоз — тренерам детей дошкольного и школьного возраста
    **_pair(['recreationalswimmingPK', 'recreationalswimmingPK2'],
            ages=['preschool'], health=['special_care'], venue='pool', skill='basic'),
    **_pair(['prematurebabies', 'prematurebabiesspecialist'],
            ages=['infant'], health=['special_care'], venue='pool', skill='beginner'),
    **_pair(['sindromDauna', 'sindromDauna2'],
            ages=ALL_AGES, health=['special_care'], venue='pool', skill='basic'),
    **_pair(['medlikbezall3', 'medlikbezspecialist'],
            ages=ALL_AGES, health=['normotypical', 'special_care'], venue='pool', skill='beginner'),
    **_pair(['specialparents-online', 'specialparents-online2'],
            ages=ALL_AGES, health=['special_care'], venue='pool', skill='basic'),
    'psychosomaticsofraces': _attrs(ages=['early', 'preschool'], health=['special_care'], venue='pool',
                                    skill='beginner'),
    # СДВГ, дети от 3 лет
    'hyperactivechildrenONL': _attrs(ages=['preschool'], health=['special_care'], venue='pool', skill='beginner'),

    # --- Акваджет тиксотренинг Душем Алексеева: на дому, для специалистов и родителей ---
    'aquajet': _attrs(ages=['infant'], health=['normotypical', 'special_care'], venue='home', skill='beginner'),
    **_pair(['thixotrainingpregnant', 'thixotrainingpregnant2'],
            health=['pregnant'], venue='home', skill='beginner'),
    **_pair(['thixotrainingflatfeet', 'thixotrainingflatfeet2'],
            ages=['preschool'], health=['normotypical'], venue='home', skill='beginner'),
    **_pair(['logoaquadget', 'logoaquadget2'],
            ages=['early', 'preschool'], health=['special_care'], venue='home', skill='beginner'),
    **_pair(['thixotraininginfection', 'thixotraininginfection2'],
            ages=ALL_AGES, health=['normotypical'], venue='home', skill='beginner'),
    # работа со взрослыми
    **_pair(['thixotrainingosteochondrosis', 'thixotrainingosteochondrosis2',
             'thixotrainingofvaricoseveins', 'thixotrainingofvaricoseveins2',
             'thixotrainingcellulite', 'cellulitespecialist',
             'thixotrainingabdominalaponeurosis', 'thixotrainingabdominalaponeurosis2',
             'thixotrainingagingface', 'thixotrainingagingface2'],
            venue='home', skill='beginner'),

    # --- Плавание ---
    **_pair(['gp-base-pool3', 'gp-base-pool1onl'],
            ages=['infant', 'early'], health=['normotypical'], venue='pool', skill='beginner'),
    'gp-base-bath3onl': _attrs(ages=['infant'], health=['normotypical'], venue='home', skill='beginner'),
    'water-aerobics-pregnant-3': _attrs(health=['pregnant'], venue='pool', skill='basic'),
    'dinamichkavvode': _attrs(ages=['infant'], health=['normotypical'], venue='pool', skill='basic'),
    'gaming-technology-water': _attrs(ages=['early'], health=['normotypical'], venue='pool', skill='beginner'),
    **_pair(['earlyswimming', 'ranneyplavaniyePK'],
            ages=['early', 'preschool'], health=['normotypical'], venue='pool', skill='beginner'),
    **_pair(['distantstyles2', 'distantstyles'],
            ages=['preschool'], health=['normotypical'], venue='pool', skill='basic'),
    'professionalstyles': _attrs(ages=['preschool'], health=['normotypical', 'special_care'], venue='pool',
                                 skill='basic'),
    **_pair(['doshkolniki-plavanie', 'doshkolnikitraining'],
            ages=['preschool'], health=['normotypical'], venue='pool', skill='beginner'),
    **_pair(['motornyiontogenez2', 'motornyiontogenez'],
            ages=ALL_AGES, health=['normotypical', 'special_care'], venue='pool', skill='advanced'),

    # --- Сухопутные: патронаж на дому ---
    **_pair(['nursing-art-basic2', 'patronageart2'],
            ages=['infant'], health=['normotypical'], venue='home', skill='beginner'),
    **_pair(['advanced', 'advanced2'],
            ages=['infant'], health=['normotypical'], venue='home', skill='basic'),
    **_pair(['grudnoyevskarmlivaniye', 'grudnoyevskarmlivaniye2'],
            ages=['infant'], health=['normotypical', 'pregnant'], venue='home', skill='beginner'),

    # --- Администрирование акваклуба ---
    **_pair(['sales', 'juristik2', 'administrator2'], venue='pool', skill='beginner'),
}

# Курс, который нужно пройти перед этим: вторая часть «Патронажного искусства» — после первой
LEGACY_REQUIRED = {
    'advanced': 'nursing-art-basic2',
    'advanced2': 'patronageart2',
}

# Тексты, которых не было на старом сайте
LEGACY_TEXTS = {
    'speech': {
        'short_description': 'Семинар-практикум о работе в воде с детьми с нарушениями речи, слуха, зрения, '
                             'психики и поведения: ЗРР, алалия, дизартрия, заикание, ДЦП, ТМНР. '
                             'Речевое дыхание, голос и коммуникация с ребёнком на занятии.',
        'audience': 'Для тренеров и инструкторов по плаванию, реабилитологов и специалистов, '
                    'работающих в воде с детьми с нарушениями развития.',
    },
}


def fill_course_attributes(Course, ChildAge, HealthFeature):
    """Заполняет пустые характеристики курсов по LEGACY_*. Возвращает число изменённых курсов."""
    ages = {a.code: a for a in ChildAge.objects.all()}
    health = {h.code: h for h in HealthFeature.objects.all()}
    changed = set()
    for course in Course.objects.filter(slug__in=LEGACY_ATTRIBUTES):
        attrs = LEGACY_ATTRIBUTES[course.slug]
        update = {}
        if not course.venue and attrs['venue']:
            update['venue'] = attrs['venue']
        if not course.skill_level and attrs['skill']:
            update['skill_level'] = attrs['skill']
        if update:
            Course.objects.filter(pk=course.pk).update(**update)
            changed.add(course.pk)
        if attrs['ages'] and not course.child_ages.exists():
            course.child_ages.set([ages[code] for code in attrs['ages'] if code in ages])
            changed.add(course.pk)
        if attrs['health'] and not course.health_features.exists():
            course.health_features.set([health[code] for code in attrs['health'] if code in health])
            changed.add(course.pk)
    for slug, required_slug in LEGACY_REQUIRED.items():
        required = Course.objects.filter(slug=required_slug).first()
        if required and Course.objects.filter(slug=slug, required_course=None).update(required_course=required):
            changed.add(Course.objects.get(slug=slug).pk)
    for slug, texts in LEGACY_TEXTS.items():
        for field, text in texts.items():
            if Course.objects.filter(slug=slug, **{field: ''}).update(**{field: text}):
                changed.add(Course.objects.get(slug=slug).pk)
    return len(changed)
