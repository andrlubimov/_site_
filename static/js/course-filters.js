/* Фильтры курсов: применяются сразу при изменении; на телефоне блок по умолчанию свёрнут. */
(function () {
    'use strict';

    var wrap = document.querySelector('.course-filters-wrap');
    var form = document.querySelector('.course-filters[data-autosubmit]');
    if (!wrap || !form) return;

    // На узком экране фильтры занимают много места — сворачиваем, если ничего не выбрано
    var filtered = wrap.querySelector('.course-filters-badge');
    if (window.matchMedia('(max-width: 991.98px)').matches && !filtered) {
        wrap.open = false;
    }

    function submit() {
        // пустые параметры в адрес не пишем — ссылка короче
        Array.prototype.forEach.call(form.elements, function (el) {
            if (el.name && (el.tagName === 'SELECT' || el.type === 'search') && !el.value.trim()) el.disabled = true;
        });
        form.submit();
    }

    // поиск отправляется по Enter или при уходе из поля (событие change), остальное — сразу
    form.addEventListener('change', submit);
    // сортировка стоит в строке над списком, вне формы, но относится к ней (атрибут form)
    document.querySelectorAll('[form="' + form.id + '"]').forEach(function (el) {
        el.addEventListener('change', submit);
    });
})();
