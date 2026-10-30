/* Сердечко на карточке курса: отложить курс или убрать из отложенных — без перезагрузки страницы.
   - Закрашиваются все сердечки этой карточки на странице (в карусели на главной у карточек есть копии).
   - Число отложенных — на кнопке «Отложенные» в шапке и в меню кабинета; при нуле кнопка скрыта.
   - Отложенный курс «улетает» сердечком туда, где его потом искать, и цель на миг подсвечивается розовым.
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

    // Куда летит сердечко — первое видимое: у вошедшего «Мои курсы» в нижней панели (телефон), «Отложенные»
    // в меню кабинета или кнопка «Личный кабинет» (компьютер); у гостя кнопка «Отложенные» (компьютер)
    // или кнопка меню, где «Отложенные» на телефоне.
    var TARGETS = [
        '.cabinet-tabbar [data-tab="my_courses"]',
        '.cabinet-side [data-cabinet-key="postponed"]',
        '.top-nav-postponed',
        '.top-nav-cabinet',
        '.mobile-menu-btn'
    ];
    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function flightTarget() {
        for (var i = 0; i < TARGETS.length; i++) {
            var el = document.querySelector(TARGETS[i]);
            if (el && el.getClientRects().length) return el;
        }
        return null;
    }

    function center(el) {
        var r = el.getBoundingClientRect();
        return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }

    function highlight(target) {
        target.classList.remove('is-postpone-hit');
        void target.offsetWidth; // перезапустить подсветку, если сердечки летят одно за другим
        target.classList.add('is-postpone-hit');
        clearTimeout(target.postponeHitTimer);
        target.postponeHitTimer = setTimeout(function () { target.classList.remove('is-postpone-hit'); }, 1400);
    }

    function flyHeart(button) {
        var target = flightTarget();
        if (!target) return;
        if (reduceMotion || !Element.prototype.animate) {
            highlight(target);
            return;
        }
        var icon = button.querySelector('.bi') || button;
        var landing = target.querySelector('.bi, img');  // садится на значок вкладки или кнопки
        if (!landing || !landing.getClientRects().length) landing = target;
        var from = center(icon);
        var to = center(landing);
        // цель уехала с экрана (шапка не прилипает) — сердечко долетает до края экрана в её сторону и тает
        var EDGE = 14;
        var clampedX = Math.min(Math.max(to.x, EDGE), window.innerWidth - EDGE);
        var clampedY = Math.min(Math.max(to.y, EDGE), window.innerHeight - EDGE);
        var offscreen = clampedX !== to.x || clampedY !== to.y;
        to = { x: clampedX, y: clampedY };
        var dx = to.x - from.x;
        var dy = to.y - from.y;
        var duration = Math.min(900, Math.max(550, Math.sqrt(dx * dx + dy * dy) * 0.9));

        var flyer = document.createElement('span');
        flyer.className = 'postpone-flyer';
        flyer.setAttribute('aria-hidden', 'true');
        flyer.style.left = from.x + 'px';
        flyer.style.top = from.y + 'px';
        flyer.style.fontSize = getComputedStyle(icon).fontSize;
        flyer.innerHTML = '<i class="bi bi-heart-fill"></i>';
        document.body.appendChild(flyer);

        // по горизонтали — ровно, по вертикали — подскок и разгон: сердечко летит дугой и уменьшается
        flyer.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(' + dx + 'px)' }],
                      { duration: duration, easing: 'cubic-bezier(0.4, 0, 0.6, 1)', fill: 'forwards' });
        var flight = flyer.firstChild.animate([
            { transform: 'translateY(0) scale(1)' },
            { transform: 'translateY(-36px) scale(1.6)', offset: 0.22, easing: 'cubic-bezier(0.5, 0, 1, 1)' },
            { transform: 'translateY(' + dy + 'px) scale(0.6)', opacity: offscreen ? 0 : 0.9 }
        ], { duration: duration, fill: 'forwards' });
        flight.onfinish = function () {
            flyer.remove();
            highlight(target);
        };
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
                    flyHeart(button);
                }
            })
            .catch(function () { form.submit(); })
            .then(function () { delete form.dataset.busy; });
    });
})();
