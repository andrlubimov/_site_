/* Страница курса: «Программа курса» свёрнута до нескольких строк, кнопка «Развернуть» раскрывает её.
   Без JS программа показывается целиком. */
(function () {
    'use strict';

    var body = document.getElementById('course-program');
    var toggle = document.querySelector('.course-program-toggle');
    if (!body || !toggle) return;

    var COLLAPSED_HEIGHT = 240; // px — должно совпадать с max-height в .course-program-body.is-collapsed

    // Короткую программу не сворачиваем
    if (body.scrollHeight <= COLLAPSED_HEIGHT + 80) return;

    var label = toggle.querySelector('span');
    var icons = toggle.querySelectorAll('.bi');

    function setExpanded(expanded) {
        body.classList.toggle('is-collapsed', !expanded);
        toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        label.textContent = expanded ? 'Свернуть' : 'Развернуть';
        icons.forEach(function (icon) {
            icon.className = 'bi ' + (expanded ? 'bi-arrow-up' : 'bi-arrow-down');
        });
    }

    toggle.hidden = false;
    setExpanded(false);
    toggle.addEventListener('click', function () {
        var expanded = toggle.getAttribute('aria-expanded') === 'true';
        setExpanded(!expanded);
        if (expanded) {
            // при сворачивании возвращаемся к началу программы
            body.parentElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
})();
