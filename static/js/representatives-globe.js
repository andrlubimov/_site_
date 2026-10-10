/* Глобус с отметками представителей (globe.gl). Точки приходят из Django
   через json_script#rep-globe-points, пути к текстурам — через window.REP_GLOBE.
   Если браузер не поддерживает WebGL2 (three.js без него не работает),
   показывается плоская карта с теми же метками. */
(function () {
    'use strict';

    var el = document.getElementById('rep-globe');
    var dataEl = document.getElementById('rep-globe-points');
    var cfg = window.REP_GLOBE || {};
    if (!el || !dataEl) {
        return;
    }

    var points = JSON.parse(dataEl.textContent);
    var COLORS = { hq: '#ff931e', regional: '#1e98ff', foreign: '#20c997' };

    // Метка: кружок с логотипом (или точка) и подпись с названием
    function buildMarker(d) {
        var marker = document.createElement('div');
        marker.className = 'globe-marker globe-marker--' + d.kind;
        marker.style.setProperty('--marker-color', COLORS[d.kind] || COLORS.regional);

        var pin = document.createElement('div');
        pin.className = 'globe-marker-pin';
        var logo = d.kind === 'hq' ? cfg.hqLogo : d.logo;
        if (logo) {
            var img = document.createElement('img');
            img.src = logo;
            img.alt = '';
            pin.appendChild(img);
        }
        marker.appendChild(pin);

        var label = document.createElement('div');
        label.className = 'globe-marker-label';
        var name = document.createElement('strong');
        name.textContent = d.name;
        var place = document.createElement('span');
        place.textContent = d.city + ' • ' + d.country;
        label.appendChild(name);
        label.appendChild(place);
        marker.appendChild(label);

        if (d.id) {
            marker.setAttribute('role', 'link');
            marker.setAttribute('tabindex', '0');
            marker.setAttribute('aria-label', d.name + ', ' + d.city);
            var go = function () { focusCard(d.id); };
            marker.addEventListener('click', go);
            marker.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); }
            });
        }
        return marker;
    }

    // Прокрутка к карточке представителя с подсветкой
    function focusCard(id) {
        var card = document.getElementById(id);
        if (!card) return;
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.remove('rep-card--highlight');
        void card.offsetWidth; // перезапуск анимации
        card.classList.add('rep-card--highlight');
    }

    function size() {
        var width = el.clientWidth;
        return { width: width, height: Math.min(600, Math.max(380, width * 0.6)) };
    }

    function hexToRgba(hex, alpha) {
        var n = parseInt(hex.slice(1), 16);
        return 'rgba(' + (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + alpha + ')';
    }

    function supportsWebGL2() {
        try {
            var canvas = document.createElement('canvas');
            return !!(window.WebGL2RenderingContext && canvas.getContext('webgl2'));
        } catch (e) {
            return false;
        }
    }

    function initGlobe() {
        var s = size();
        var globe = new Globe(el)
            .width(s.width)
            .height(s.height)
            .backgroundColor('rgba(0,0,0,0)')
            .globeImageUrl(cfg.globeImage)
            .bumpImageUrl(cfg.bumpImage)
            .showAtmosphere(true)
            .atmosphereColor('#9be6ff')
            .atmosphereAltitude(0.18)
            .htmlElementsData(points)
            .htmlElement(buildMarker)
            .htmlTransitionDuration(0)
            .htmlElementVisibilityModifier(function (elem, isVisible) {
                elem.style.opacity = isVisible ? 1 : 0;
                elem.style.pointerEvents = isVisible ? 'auto' : 'none';
            })
            .ringsData(points)
            .ringColor(function (d) {
                var c = COLORS[d.kind] || COLORS.regional;
                return function (t) { return hexToRgba(c, 1 - t); };
            })
            .ringMaxRadius(3)
            .ringPropagationSpeed(1.5)
            .ringRepeatPeriod(1600);

        // Стартовый вид — Евразия, где находится большинство представителей
        globe.pointOfView({ lat: 47, lng: 55, altitude: 1.35 });

        var controls = globe.controls();
        controls.enableZoom = false; // не перехватываем прокрутку страницы
        controls.autoRotate = true;
        controls.autoRotateSpeed = 0.35;

        // Останавливаем вращение, пока пользователь крутит глобус, и возобновляем через 6 секунд
        var resumeTimer = null;
        controls.addEventListener('start', function () {
            controls.autoRotate = false;
            clearTimeout(resumeTimer);
        });
        controls.addEventListener('end', function () {
            resumeTimer = setTimeout(function () { controls.autoRotate = true; }, 6000);
        });

        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            controls.autoRotate = false;
        }

        window.addEventListener('resize', function () {
            var sz = size();
            globe.width(sz.width).height(sz.height);
        });
    }

    /* ---------- Запасной вариант: плоская карта (равнопромежуточная проекция) ---------- */
    function initFlatMap() {
        el.innerHTML = '';
        el.classList.add('rep-globe--flat');

        var img = document.createElement('img');
        img.className = 'rep-flat-image';
        img.src = cfg.globeImage;
        img.alt = '';
        el.appendChild(img);

        var markers = points.map(function (d) {
            var m = buildMarker(d);
            m.classList.add('globe-marker--flat');
            el.appendChild(m);
            return m;
        });

        var lats = points.map(function (d) { return d.lat; });
        var lngs = points.map(function (d) { return d.lng; });
        var PAD = 12; // градусов вокруг крайних точек

        function layout() {
            var w = el.clientWidth;
            var h = Math.min(520, Math.max(320, w * 0.5));
            el.style.height = h + 'px';

            // Область карты по крайним точкам, растянутая под пропорции контейнера
            var lngMin = Math.min.apply(null, lngs) - PAD, lngMax = Math.max.apply(null, lngs) + PAD;
            var latMin = Math.min.apply(null, lats) - PAD, latMax = Math.max.apply(null, lats) + PAD;
            var lngSpan = lngMax - lngMin, latSpan = latMax - latMin;
            var ratio = w / h;
            if (lngSpan / latSpan < ratio) {
                var addLng = (latSpan * ratio - lngSpan) / 2;
                lngMin -= addLng; lngSpan = latSpan * ratio;
            } else {
                var addLat = (lngSpan / ratio - latSpan) / 2;
                latMax += addLat; latSpan = lngSpan / ratio;
            }
            // Не выходим за края карты мира
            lngSpan = Math.min(lngSpan, 360); latSpan = Math.min(latSpan, 180);
            lngMin = Math.max(-180, Math.min(lngMin, 180 - lngSpan));
            latMax = Math.min(90, Math.max(latMax, -90 + latSpan));

            var pxPerDeg = w / lngSpan;
            img.style.width = (360 * pxPerDeg) + 'px';
            img.style.height = (180 * pxPerDeg) + 'px';
            img.style.left = (-(lngMin + 180) * pxPerDeg) + 'px';
            img.style.top = (-(90 - latMax) * pxPerDeg) + 'px';

            markers.forEach(function (m, i) {
                m.style.left = ((points[i].lng - lngMin) * pxPerDeg) + 'px';
                m.style.top = ((latMax - points[i].lat) * pxPerDeg) + 'px';
            });
        }

        layout();
        window.addEventListener('resize', layout);

        var hint = document.querySelector('.rep-globe-hint');
        if (hint) {
            hint.textContent = 'Ваш браузер не поддерживает 3D-графику (WebGL 2), поэтому показана плоская карта. ' +
                'Нажмите на отметку, чтобы перейти к карточке представителя.';
        }
    }

    if (typeof Globe !== 'undefined' && supportsWebGL2()) {
        try {
            initGlobe();
        } catch (e) {
            initFlatMap();
        }
    } else {
        initFlatMap();
    }
})();
