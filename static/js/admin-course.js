/* Админка курса: поле цены диплома / удостоверения видно только при отмеченном варианте */
document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    [['has_diploma', 'diploma_price'],
     ['has_qualification_certificate', 'qualification_certificate_price']].forEach(function (pair) {
        var checkbox = document.getElementById('id_' + pair[0]);
        var row = document.querySelector('.form-row.field-' + pair[1]);
        if (!checkbox || !row) return;

        function apply() {
            row.style.display = checkbox.checked ? '' : 'none';
        }
        checkbox.addEventListener('change', apply);
        apply();
    });
});
