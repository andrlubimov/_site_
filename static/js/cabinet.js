/* Личный кабинет:
   - подсказка в поле номера телефона меняется вместе со страной (пример номера этой страны);
   - выбранная в «Стране» страна подставляется в код телефона, пока номер не введён;
   - выбранное фото сразу видно в кружке-аватарке (регистрация, «Мой профиль»);
   - переключатель «Показывать меня на сайте» сохраняется сразу. */
(function () {
    'use strict';

    document.querySelectorAll('[data-phone-country]').forEach(function (select) {
        var input = select.parentElement.querySelector('[data-phone-number]');
        if (!input) return;
        function showExample() {
            var option = select.options[select.selectedIndex];
            if (option && option.dataset.example) input.placeholder = option.dataset.example;
        }
        select.addEventListener('change', showExample);
        showExample();
    });

    document.querySelectorAll('[data-country-select]').forEach(function (country) {
        var phoneCountry = country.form && country.form.querySelector('[data-phone-country]');
        var phoneNumber = country.form && country.form.querySelector('[data-phone-number]');
        if (!phoneCountry || !phoneNumber) return;
        country.addEventListener('change', function () {
            var code = country.options[country.selectedIndex].dataset.code;
            if (code && !phoneNumber.value.trim()) {
                phoneCountry.value = code;
                phoneCountry.dispatchEvent(new Event('change')); // и пример номера — этой страны
            }
        });
    });

    document.querySelectorAll('[data-avatar-preview]').forEach(function (preview) {
        var file = preview.parentElement.querySelector('input[type="file"]');
        if (!file) return;
        var saved = preview.style.backgroundImage; // фото, которое уже есть в профиле
        var url = '';
        file.addEventListener('change', function () {
            if (url) URL.revokeObjectURL(url);
            var picked = file.files && file.files[0];
            url = picked && picked.type.indexOf('image/') === 0 ? URL.createObjectURL(picked) : '';
            preview.style.backgroundImage = url ? 'url("' + url + '")' : saved;
            preview.classList.toggle('has-photo', !!(url || saved));
        });
    });

    document.querySelectorAll('input[data-autosubmit]').forEach(function (input) {
        input.addEventListener('change', function () { input.form.submit(); });
    });
})();
