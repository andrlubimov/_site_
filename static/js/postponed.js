/* Сердечко на карточке курса: отложить курс или убрать из отложенных — без перезагрузки страницы.
   - Закрашиваются все сердечки этой карточки на странице (в карусели на главной у карточек есть копии).
   - Число отложенных — на кнопке «Отложенные» в шапке и в меню кабинета; при нуле кнопка скрыта.
   Без JS (или если запрос не удался) форма отправляется обычным образом. */
(function () {
    'use strict';

    if (!window.fetch || !window.FormData) return;

    function mark(key, postponed) {
        document.querySelectorAll('[data-postpone-key="' + key + '"]').forEach(function (button) {
            button.classList.toggle('is-postponed', postponed);
            button.setAttribute('aria-pressed', postponed ? 'true' : 'false');
            button.title = postponed ? 'В отложенных — нажмите, чтобы убрать' : 'Отложить';
            var icon = button.querySelector('.bi');
            if (icon) icon.className = 'bi ' + (postponed ? 'bi-heart-fill' : 'bi-heart');
        });
    }

    function showCount(count) {
        document.querySelectorAll('[data-postponed-count]').forEach(function (el) { el.textContent = count; });
        document.querySelectorAll('[data-postponed-link]').forEach(function (el) { el.hidden = !count; });
    }

    document.addEventListener('submit', function (event) {
        var form = event.target.closest('form[data-postpone]');
        if (!form) return;
        event.preventDefault();
        if (form.dataset.busy) return; // двойной клик — один запрос
        form.dataset.busy = '1';
        var button = form.querySelector('button');
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'Accept': 'application/json' },
            credentials: 'same-origin'
        })
            .then(function (response) {
                if (!response.ok) throw new Error(response.status);
                return response.json();
            })
            .then(function (data) {
                mark(data.key, data.postponed);
                showCount(data.count);
                if (data.postponed && button) {
                    button.classList.remove('is-popping');
                    void button.offsetWidth; // перезапустить анимацию
                    button.classList.add('is-popping');
                }
            })
            .catch(function () { form.submit(); })
            .then(function () { delete form.dataset.busy; });
    });
})();
