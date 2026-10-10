/* Надувной бассейн на странице «Партнёры»: спасательные круги с логотипами
   дрейфуют по воде, покачиваются и отталкиваются друг от друга и от бортов.
   Наведение — описание партнёра, клик — переход на сайт. */
(function () {
    'use strict';

    var pool = document.getElementById('partner-pool');
    if (!pool) return;

    var tooltip = pool.querySelector('.pool-tooltip');
    var els = Array.prototype.slice.call(pool.querySelectorAll('.buoy'));
    if (!els.length) return;

    // Вода на фото — эллипс в долях размера бассейна (совпадает с clip-path в partners-pool.css)
    var WATER = { cx: 0.4997, cy: 0.309, rx: 0.4314, ry: 0.2429 };
    var POOL_RATIO = 787 / 1400;
    var RING_RATIO = 170 / 310;
    // При «уменьшении движения» в системе круги не замирают, а плывут медленнее и качаются слабее
    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var MOTION = reduceMotion ? 0.4 : 1;

    var W, H, bw, bh, area;
    var active = null;       // круг под курсором / в фокусе
    var lastPointer = 'mouse';

    var buoys = els.map(function (el, i) {
        el.style.setProperty('--ripple-delay', (-i * 0.7) + 's');
        return {
            el: el,
            x: 0, y: 0, vx: 0, vy: 0,
            heading: Math.random() * Math.PI * 2,
            phase: Math.random() * Math.PI * 2,
            speed: 0.6 + Math.random() * 0.5
        };
    });

    function measure() {
        W = pool.clientWidth;
        H = W * POOL_RATIO;
        bw = els[0].offsetWidth;
        bh = bw * RING_RATIO;
        // Допустимая область для центра круга: эллипс воды минус «полкруга»
        area = {
            cx: WATER.cx * W,
            cy: WATER.cy * H,
            rx: Math.max(10, WATER.rx * W - bw * 0.42),
            ry: Math.max(10, WATER.ry * H - bh * 0.25)
        };
    }

    // Начальная раскладка «подсолнухом», чтобы круги не стартовали друг в друге
    function layout() {
        var n = buoys.length;
        buoys.forEach(function (b, i) {
            var r = Math.sqrt((i + 0.5) / n);
            var a = i * 2.399963;
            b.x = area.cx + r * area.rx * Math.cos(a);
            b.y = area.cy + r * area.ry * Math.sin(a);
            b.vx = b.vy = 0;
        });
    }

    function step(dt, t) {
        var i, j, a, b;
        var minX = bw * 0.95, minY = bh * 0.95;

        for (i = 0; i < buoys.length; i++) {
            b = buoys[i];
            if (b === active) {               // под курсором круг замирает
                b.vx *= 0.8; b.vy *= 0.8;
                continue;
            }
            // Блуждающее «течение»: направление медленно меняется
            b.heading += (Math.sin(t * 0.3 + b.phase) * 0.6 + (Math.random() - 0.5) * 0.8) * dt;
            var f = 9 * b.speed * MOTION;
            b.vx += Math.cos(b.heading) * f * dt;
            b.vy += Math.sin(b.heading) * f * 0.6 * dt;

            // Борт: мягко выталкиваем внутрь эллипса
            var nx = (b.x - area.cx) / area.rx, ny = (b.y - area.cy) / area.ry;
            var e = nx * nx + ny * ny;
            if (e > 0.85) {
                var push = (e - 0.85) * 120;
                b.vx -= nx * push * dt * (area.rx / 100);
                b.vy -= ny * push * dt * (area.ry / 100);
                b.heading = Math.atan2(-ny, -nx) + (Math.random() - 0.5);
            }
        }

        // Круги расталкивают друг друга
        for (i = 0; i < buoys.length; i++) {
            for (j = i + 1; j < buoys.length; j++) {
                a = buoys[i]; b = buoys[j];
                var dx = (b.x - a.x) / minX, dy = (b.y - a.y) / minY;
                var d = Math.sqrt(dx * dx + dy * dy);
                if (d < 1 && d > 0.0001) {
                    var k = (1 - d) * 60 * dt;
                    var px = dx / d * k * minX / 10, py = dy / d * k * minY / 10;
                    if (a !== active) { a.vx -= px; a.vy -= py; }
                    if (b !== active) { b.vx += px; b.vy += py; }
                }
            }
        }

        for (i = 0; i < buoys.length; i++) {
            b = buoys[i];
            var damp = Math.pow(0.9, dt * 60 / 10);
            b.vx *= damp; b.vy *= damp;
            var sp = Math.sqrt(b.vx * b.vx + b.vy * b.vy), max = W * 0.025 * MOTION;
            if (sp > max) { b.vx *= max / sp; b.vy *= max / sp; }
            b.x += b.vx * dt;
            b.y += b.vy * dt;

            // Жёсткая граница на случай резкого изменения размера
            var ex = (b.x - area.cx) / area.rx, ey = (b.y - area.cy) / area.ry;
            var ee = Math.sqrt(ex * ex + ey * ey);
            if (ee > 1.02) {
                b.x = area.cx + ex / ee * area.rx;
                b.y = area.cy + ey / ee * area.ry;
            }
        }
    }

    function render(t) {
        buoys.forEach(function (b) {
            // Ближе к зрителю (ниже) — чуть крупнее
            var depth = (b.y - (area.cy - area.ry)) / (2 * area.ry);
            var scale = 0.86 + 0.24 * Math.max(0, Math.min(1, depth));
            var bob = Math.sin(t * 1.6 * MOTION + b.phase) * bh * 0.035 * MOTION;
            var tilt = Math.sin(t * 1.1 * MOTION + b.phase * 1.7) * 3.5 * MOTION;
            if (b === active) scale *= 1.08;
            b.el.style.transform =
                'translate(' + (b.x - bw / 2).toFixed(1) + 'px,' + (b.y - bh / 2 + bob).toFixed(1) + 'px)' +
                ' rotate(' + tilt.toFixed(2) + 'deg) scale(' + scale.toFixed(3) + ')';
            b.el.style.zIndex = b === active ? 1000 : Math.round(b.y);
        });
        if (active) placeTooltip(active);
    }

    function placeTooltip(b) {
        var x = Math.max(160, Math.min(W - 160, b.x));
        var below = b.y - bh * 0.6 < 150;
        tooltip.classList.toggle('is-below', below);
        tooltip.style.left = x + 'px';
        tooltip.style.top = (below ? b.y + bh * 0.55 : b.y - bh * 0.55) + 'px';
    }

    function activate(b) {
        if (active === b) return;
        if (active) active.el.classList.remove('is-active');
        active = b;
        if (!b) { tooltip.hidden = true; return; }
        b.el.classList.add('is-active');
        tooltip.innerHTML = b.el.querySelector('.buoy-info').innerHTML;
        tooltip.hidden = false;
        placeTooltip(b);
    }

    buoys.forEach(function (b) {
        b.el.addEventListener('pointerenter', function (e) {
            lastPointer = e.pointerType;
            if (e.pointerType === 'mouse') activate(b);
        });
        b.el.addEventListener('pointerleave', function (e) {
            if (e.pointerType === 'mouse' && active === b) activate(null);
        });
        b.el.addEventListener('pointerdown', function (e) { lastPointer = e.pointerType; });
        b.el.addEventListener('focus', function () { activate(b); });
        b.el.addEventListener('blur', function () { if (active === b) activate(null); });
        // Касание: первое показывает описание, второе открывает сайт
        b.el.addEventListener('click', function (e) {
            if (lastPointer !== 'mouse' && active !== b) {
                e.preventDefault();
                activate(b);
            }
        });
    });

    document.addEventListener('pointerdown', function (e) {
        if (active && !e.target.closest('.buoy')) activate(null);
    });

    measure();
    layout();

    // Анимация работает, только пока бассейн виден на экране; цикл всегда один
    var visible = true, running = false, last = performance.now(), start = last;

    function run() {
        if (running || !visible) return;
        running = true;
        last = performance.now();
        requestAnimationFrame(frame);
    }

    function frame(now) {
        if (!visible) { running = false; return; }
        var dt = Math.min(0.05, (now - last) / 1000);
        last = now;
        var t = (now - start) / 1000;
        step(dt, t);
        render(t);
        requestAnimationFrame(frame);
    }

    if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (entries) {
            visible = entries[0].isIntersecting;
            run();
        }).observe(pool);
    }
    run();

    window.addEventListener('resize', function () {
        var oldW = W, oldH = H;
        measure();
        buoys.forEach(function (b) {
            b.x *= W / oldW;
            b.y *= H / oldH;
        });
    });
})();
