/* Админка расписания: показываем только те поля дат, которые нужны для типа выбранного курса.
   Тип курса приходит в data-course-type у вариантов списка «Курс» (CourseTypeSelect). */
document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    var select = document.getElementById('id_course');
    if (!select) return;

    function row(field) {
        return document.querySelector('.form-row.field-' + field);
    }

    var parts = {
        dates: row('start_date'),
        time: row('time_from'),
        materials: row('materials_from'),
        access: row('access_days'),
        inPerson: document.getElementById('in_person_days-group')
    };
    var hint = document.querySelector('.schedule-type-hint');

    var HINTS = {
        in_person: 'Очный курс: укажите даты начала и окончания и примерное время занятий.',
        online: 'Онлайн-курс: укажите даты начала и окончания и примерное время занятий.',
        blended: 'Очно-заочный курс: даты начала и окончания, время занятий, период доступа к материалам ' +
                 'и даты очных занятий (список ниже).',
        distance: 'Дистанционный курс: дат нет — укажите срок доступа к материалам в днях.'
    };

    function show(el, visible) {
        if (el) el.style.display = visible ? '' : 'none';
    }

    function apply() {
        var option = select.options[select.selectedIndex];
        var type = option ? option.getAttribute('data-course-type') || '' : '';
        var dated = type === 'in_person' || type === 'online' || type === 'blended';

        show(parts.dates, dated);
        show(parts.time, dated);
        show(parts.materials, type === 'blended');
        show(parts.access, type === 'distance');
        show(parts.inPerson, type === 'blended');

        if (hint) {
            if (!select.value) {
                hint.textContent = 'Выберите курс — появятся поля дат для его типа.';
            } else {
                hint.textContent = HINTS[type] || 'У курса не указан тип — сначала укажите его в карточке курса.';
            }
        }
    }

    select.addEventListener('change', apply);
    apply();
});
