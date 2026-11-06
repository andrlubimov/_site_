/* Сайт конвенции: мобильное меню на весь экран — кнопка «Меню» справа вверху, как на старом сайте. */
(function () {
    'use strict';

    var button = document.querySelector('.cd-nav-trigger');
    var nav = document.getElementById('cd-nav');
    if (!button || !nav) return;

    function toggle(open) {
        document.body.classList.toggle('nav-is-visible', open);
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    button.addEventListener('click', function () {
        toggle(button.getAttribute('aria-expanded') !== 'true');
    });
    nav.addEventListener('click', function (event) {
        if (event.target.closest('a')) toggle(false);
    });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
            toggle(false);
            button.focus();
        }
    });
})();
