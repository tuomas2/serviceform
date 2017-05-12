$(document).ready(function () {
    var activity_inputs = $(".activity-input");
    activity_inputs.change(function (ev) {
        $(".group-" + this.name + '.choice-radio-input').prop('disabled', !this.checked);
        if(!this.checked) {
            $(".group-" + this.name + '.choice-radio-input').attr('checked', false);
            var activity_textareas = $('.extra-CHOICE-textarea.group-' + this.name);
            activity_textareas.prop('disabled', true);
        }
        $(".group-" + this.name + '.extra-ACTIVITY-textarea').prop('disabled', !this.checked);
    });
    activity_inputs.each(function (ev) {
        $(".group-" + this.name + '.choice-radio-input').prop('disabled', !this.checked);
        $(".group-" + this.name + '.extra-ACTIVITY-textarea').prop('disabled', !this.checked);
    });

    var radio_inputs = $(".choice-radio-input");
    radio_inputs.change(function (ev) {
        var enabled_radiobutton = $(this);
        var choice_name = enabled_radiobutton.data('choice');
        var activity_id = enabled_radiobutton.data('activity_id');
        var activity_textareas = $('.extra-CHOICE-textarea.group-SRV_ACTIVITY_' + activity_id);
        activity_textareas.prop('disabled', true);
        var selected_activity_textarea = $('.extra-' + choice_name);
        selected_activity_textarea.prop('disabled', false);
    });

    $('.extra-CHOICE-textarea').prop('disabled', true);
    radio_inputs.filter(':checked').each(function (ev) {
        var choice_name = $(this).data('choice');
        var selected_activity_textarea = $('.extra-' + choice_name);
        selected_activity_textarea.prop('disabled', false);
    });

    var choice_inputs = $(".choice-input");
    choice_inputs.change(function (ev) {
        $(".extra-" + this.name).prop('disabled', !this.checked);
    });
    choice_inputs.each(function (ev) {
        $(".extra-" + this.name).prop('disabled', !this.checked);
    });

    // report

    $("#show-old").change(function () {
        if(this.checked)
            $('.old').show();
        else
            $('.old').hide();
    });
    $("#expand-all-info").change(function () {
        if(this.checked)
            $('.collapse').collapse('show');
        else
            $('.collapse').collapse('hide');
    });
});


