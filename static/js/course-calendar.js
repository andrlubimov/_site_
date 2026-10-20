/* Календарь курсов на странице «Расписание» (FullCalendar v7 + тема Bootstrap 5).
   События приходят из Django через json_script#course-calendar-events. */
(function () {
    'use strict';

    var calendarEl = document.getElementById('course-calendar');
    var dataEl = document.getElementById('course-calendar-events');
    if (!calendarEl || !dataEl || typeof FullCalendar === 'undefined') {
        return;
    }

    var events = JSON.parse(dataEl.textContent);

    // Открываем месяц ближайшего курса, если в текущем месяце курсов нет
    function pickInitialDate() {
        var today = new Date().toISOString().slice(0, 10);
        var upcoming = events
            .filter(function (e) { return e.end > today; })
            .sort(function (a, b) { return a.start < b.start ? -1 : 1; })[0];
        return upcoming && upcoming.start > today ? upcoming.start : today;
    }

    function line(parent, iconClass, text) {
        if (!text) return;
        var row = document.createElement('div');
        row.className = 'course-pop-row';
        var icon = document.createElement('i');
        icon.className = 'bi ' + iconClass;
        var span = document.createElement('span');
        span.textContent = text;
        row.appendChild(icon);
        row.appendChild(span);
        parent.appendChild(row);
    }

    // Содержимое всплывающей подсказки — через textContent, без HTML из БД
    function buildPopoverContent(event) {
        var p = event.extendedProps;
        var box = document.createElement('div');
        box.className = 'course-pop';
        line(box, 'bi-calendar-event', p.dates);
        line(box, 'bi-people', p.inPersonDays ? 'Очные занятия: ' + p.inPersonDays : '');
        line(box, 'bi-journal-text', p.materials ? 'Доступ к материалам: ' + p.materials : '');
        line(box, 'bi-clock', p.time ? 'Занятия: ' + p.time : '');
        line(box, 'bi-mortarboard', [p.type, p.format].filter(Boolean).join(' · '));
        line(box, 'bi-hourglass-split', p.hours);
        line(box, 'bi-person', p.teacher);
        line(box, 'bi-cash-coin', p.price);
        line(box, 'bi-info-circle', p.comment);
        if (p.description) {
            var desc = document.createElement('p');
            desc.className = 'course-pop-desc';
            desc.textContent = p.description;
            box.appendChild(desc);
        }
        var hint = document.createElement('div');
        hint.className = 'course-pop-hint';
        hint.textContent = 'Нажмите, чтобы открыть описание курса';
        box.appendChild(hint);
        return box;
    }

    var calendar = new FullCalendar.Calendar(calendarEl, {
        locale: 'ru',
        initialView: 'dayGridMonth',
        initialDate: pickInitialDate(),
        headerToolbar: {
            start: 'prev,next today',
            center: 'title',
            end: 'dayGridMonth,dayGridWeek'
        },
        buttonText: {
            today: 'Сегодня',
            month: 'Месяц',
            week: 'Неделя'
        },
        height: 'auto',
        dayMaxEvents: 4,
        events: events,

        eventDidMount: function (info) {
            if (typeof bootstrap === 'undefined') return;
            new bootstrap.Popover(info.el, {
                title: info.event.title,
                content: buildPopoverContent(info.event),
                html: true,
                trigger: 'hover focus',
                placement: 'auto',
                container: 'body',
                customClass: 'course-popover',
                // без анимации: FullCalendar может удалить элемент посреди перехода
                animation: false
            });
        },

        eventWillUnmount: function (info) {
            if (typeof bootstrap === 'undefined') return;
            var pop = bootstrap.Popover.getInstance(info.el);
            if (pop) {
                pop.hide();
                pop.dispose();
            }
        },

        // В v7 переход по event.url не выполняется автоматически
        eventClick: function (info) {
            if (!info.event.url) return;
            if (info.jsEvent) info.jsEvent.preventDefault();
            var pop = typeof bootstrap !== 'undefined' && bootstrap.Popover.getInstance(info.el);
            if (pop) pop.hide();
            if (info.jsEvent && (info.jsEvent.ctrlKey || info.jsEvent.metaKey)) {
                window.open(info.event.url, '_blank');
            } else {
                window.location.href = info.event.url;
            }
        }
    });

    calendar.render();
})();
