/* Админка партнёров: предпросмотр логотипа на круге сразу после выбора файла */
document.addEventListener('DOMContentLoaded', function () {
    'use strict';
    var input = document.getElementById('id_logo');
    var logo = document.querySelector('.partner-admin-logo');
    if (!input || !logo) return;

    input.addEventListener('change', function () {
        var file = input.files && input.files[0];
        if (!file || !/^image\//.test(file.type)) return;
        var reader = new FileReader();
        reader.onload = function () {
            logo.src = reader.result;
            logo.hidden = false;
        };
        reader.readAsDataURL(file);
    });
});
