/* Карусели на главной (представители, партнёры): бесконечная лента с автопрокруткой.
   - Карточки продублированы один раз (копии скрыты от чтения с экрана и Tab). Когда лента уходит в копии,
     она незаметно перескакивает на те же карточки в начале — листать можно бесконечно в обе стороны.
   - Каждые AUTOPLAY_MS лента сдвигается на одну карточку. Пауза — пока над каруселью курсор, в ней фокус,
     её касаются, она не видна на экране или вкладка скрыта. При «уменьшении движения» автопрокрутки нет.
   - Если все карточки помещаются — листать нечего: кнопки скрыты, без копий и автопрокрутки.
   Без JS лента просто прокручивается (CSS scroll-snap). */
(function () {
    'use strict';

    var AUTOPLAY_MS = 2000;
    var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    document.querySelectorAll('[data-carousel]').forEach(function (carousel) {
        var track = carousel.querySelector('[data-carousel-track]');
        var prev = carousel.querySelector('[data-carousel-prev]');
        var next = carousel.querySelector('[data-carousel-next]');
        if (!track || !prev || !next) return;

        var originals = Array.prototype.slice.call(track.children);
        if (track.scrollWidth - track.clientWidth <= 8) {
            carousel.classList.add('is-static');
            return;
        }

        // копии карточек — продолжение ленты
        originals.forEach(function (item) {
            var clone = item.cloneNode(true);
            clone.setAttribute('aria-hidden', 'true');
            clone.querySelectorAll('a, button').forEach(function (el) { el.tabIndex = -1; });
            track.appendChild(clone);
        });

        function step() {   // шаг — расстояние между соседними карточками (с учётом промежутка)
            return originals[1] ? originals[1].offsetLeft - originals[0].offsetLeft : track.clientWidth;
        }

        function loopWidth() {   // ширина исходного набора: на столько лента сдвигается при «перескоке»
            return track.children[originals.length].offsetLeft - originals[0].offsetLeft;
        }

        function jump(left) {   // мгновенно, без плавной прокрутки и привязки
            track.style.scrollBehavior = 'auto';
            track.style.scrollSnapType = 'none';
            track.scrollLeft = left;
            track.offsetHeight; // применить сразу
            track.style.scrollBehavior = '';
            track.style.scrollSnapType = '';
        }

        function wrap() {   // ушли в копии — вернуться на то же место в исходном наборе
            var width = loopWidth();
            if (track.scrollLeft >= width) jump(track.scrollLeft - width);
        }

        function go(direction) {
            if (direction < 0 && track.scrollLeft < step() / 2) {
                jump(track.scrollLeft + loopWidth()); // назад от начала — из копий, тоже бесшовно
            }
            track.scrollBy({ left: direction * step(), behavior: reducedMotion ? 'auto' : 'smooth' });
        }

        var scrollTimer;
        track.addEventListener('scroll', function () {
            clearTimeout(scrollTimer);
            scrollTimer = setTimeout(wrap, 120); // после окончания прокрутки
        }, { passive: true });

        prev.addEventListener('click', function () { go(-1); restart(); });
        next.addEventListener('click', function () { go(1); restart(); });

        // --- автопрокрутка
        var timer = null;
        var paused = { hover: false, focus: false, touch: false, hidden: false };

        function canPlay() {
            return !reducedMotion && !document.hidden &&
                !paused.hover && !paused.focus && !paused.touch && !paused.hidden;
        }

        function restart() {
            clearInterval(timer);
            timer = canPlay() ? setInterval(function () { go(1); }, AUTOPLAY_MS) : null;
        }

        function pause(reason, value) {
            paused[reason] = value;
            restart();
        }

        carousel.addEventListener('mouseenter', function () { pause('hover', true); });
        carousel.addEventListener('mouseleave', function () { pause('hover', false); });
        carousel.addEventListener('focusin', function () { pause('focus', true); });
        carousel.addEventListener('focusout', function (e) {
            if (!carousel.contains(e.relatedTarget)) pause('focus', false);
        });
        // касание: пауза на время свайпа и ещё немного после
        var touchTimer;
        track.addEventListener('touchstart', function () {
            clearTimeout(touchTimer);
            pause('touch', true);
        }, { passive: true });
        track.addEventListener('touchend', function () {
            touchTimer = setTimeout(function () { pause('touch', false); }, 4000);
        }, { passive: true });
        document.addEventListener('visibilitychange', restart);
        if ('IntersectionObserver' in window) {
            new IntersectionObserver(function (entries) {
                pause('hidden', !entries[0].isIntersecting);
            }).observe(carousel);
        }
        restart();
    });
})();
