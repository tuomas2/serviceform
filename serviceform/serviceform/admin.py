# -*- coding: utf-8 -*-
# (c) 2017 Tuomas Airaksinen
#
# This file is part of Serviceform.
#
# Serviceform is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Serviceform is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Serviceform.  If not, see <http://www.gnu.org/licenses/>.

import datetime
from typing import Iterable
import collections
from django.contrib import admin
from django.conf import settings
from django.contrib import messages
from django.db.models import Model, Field
from django.forms.utils import pretty_name
from django.http import HttpRequest
from django.utils.encoding import force_str
from django.utils.translation import ugettext_lazy as _, gettext as _g
from django.utils import timezone
from guardian.admin import GuardedModelAdmin, GuardedModelAdminMixin
from guardian.shortcuts import get_objects_for_user, assign_perm

from nested_admin.nested import NestedModelAdmin, NestedTabularInline, NestedStackedInline, \
    NestedModelAdminMixin
from . import models, utils

if 'grappelli' in settings.INSTALLED_APPS:
    from grappelli.forms import GrappelliSortableHiddenMixin
else:
    class GrappelliSortableHiddenMixin:
        pass


class OwnerSaveMixin:
    def save_model(self, request: HttpRequest, obj: Model, form, change: bool) -> Model:
        assign_new_perm = not obj.pk
        rv = super().save_model(request, obj, form, change)
        if assign_new_perm:
            assign_perm('serviceform.can_access_serviceform', request.user, obj)
        return rv


class ResponsibleMixin:
    def formfield_for_manytomany(self, db_field: Field, request: HttpRequest=None, **kwargs):
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name in ['responsibles']:
            formfield.queryset = request._responsibles
            # Let's do a little DB optimization trick because there will be
            # otherwise tons of queries to responsible choices
            choices = getattr(request, '_responsible_choices', None)
            formfield.choices = choices or formfield.choices
            if not choices:
                request._responsible_choices = formfield.choices
        return formfield


class ExtendedLogMixin:
    """
    Adds changed content into log message in Admin
    """

    def map_field_value(self, values, choices):
        def do_map(value, choices):
            if value is None:
                return '?'
            elif isinstance(value, Model):
                return str(value)
            else:
                return _g(str(choices.get(value, value)))

        if isinstance(values, collections.Iterable) and not isinstance(values, str):
            msg = ', '.join(do_map(val, choices) for val in values)
            return '[%s]' % msg
        else:
            return do_map(values, choices)

    def get_field_change(self, form, changed_fields):
        """Mentions old and new value for changed fields"""
        changes = []
        for field_name in changed_fields:
            field = form.fields[field_name]
            label = field.label or pretty_name(field_name)
            old_value = field.prepare_value(form.initial.get(field_name))
            new_value = form.cleaned_data[field_name]
            if hasattr(field, 'choices'):
                choices = dict(field.choices)
                old_value = self.map_field_value(old_value, choices)
                new_value = self.map_field_value(new_value, choices)
            if old_value != new_value:
                if isinstance(old_value, datetime.datetime):
                    old_value = old_value.astimezone(timezone.get_current_timezone())
                changes.append({'label': force_str(label).lower(),
                                'new_value': new_value,
                                'old_value': old_value})
        # Translators: This appears after "Changed" and is joined with "and"
        chg_msg = _(' {label} to {new_value} (was {old_value}) ')
        return _('and').join(chg_msg.format(**cc) for cc in changes)

    def construct_change_message(self, request, form, formsets, add=False):
        """Construct a change message from a changed object.
        Copy of contrib/admin/options.py class ModelAdmin with get_text_list
        replaced with self.get_field_change."""
        change_message = []
        if form.changed_data:
            change_message.append(_('Changed %s.')
                                  % self.get_field_change(form, form.changed_data))

        if formsets:
            for formset in formsets:
                form_by_instance = {form.instance: form for form in formset.forms if
                                    form.instance.pk}
                for added_object in formset.new_objects:
                    change_message.append(
                        _('Added %(name)s "%(object)s".')
                        % {'name': force_str(added_object._meta.verbose_name),
                           'object': force_str(added_object)})
                for changed_object, changed_fields in formset.changed_objects:
                    form = form_by_instance[changed_object]
                    change_message.append(
                        _('Changed %(list)s for %(name)s "%(object)s".')
                        % {'list': self.get_field_change(form, changed_fields),
                           'name': force_str(changed_object._meta.verbose_name),
                           'object': force_str(changed_object)})
                for deleted_object in formset.deleted_objects:
                    change_message.append(
                        _('Deleted %(name)s "%(object)s".')
                        % {'name': force_str(deleted_object._meta.verbose_name),
                           'object': force_str(deleted_object)})
        change_message = ' '.join(change_message)
        return change_message or _('No fields changed.')


class ServiceFormItemInline(GrappelliSortableHiddenMixin, ResponsibleMixin, NestedTabularInline):
    extra = 0
    sortable_field_name = 'order'


class ActivityChoiceInline(ServiceFormItemInline):
    fields = ('name', 'description', 'responsibles', 'skip_numbering', 'people_needed', 'order')
    model = models.ActivityChoice


class ActivityInline(ServiceFormItemInline):
    fields = ('name', 'description', 'responsibles', 'multiple_choices_allowed', 'skip_numbering',
              'people_needed', 'order')
    model = models.Activity
    inlines = [ActivityChoiceInline]


class Level2CategoryInline(ServiceFormItemInline):
    fields = ('name', 'description', 'responsibles', 'background_color', 'order')
    model = models.Level2Category
    inlines = [ActivityInline]


class Level1CategoryInline(ServiceFormItemInline):
    fields = ('name', 'description', 'responsibles', 'background_color', 'order')
    model = models.Level1Category
    inlines = [Level2CategoryInline]


class QuestionInline(ResponsibleMixin, GrappelliSortableHiddenMixin, NestedTabularInline):
    sortable_field_name = 'order'
    model = models.Question
    extra = 0
    fields = ('question', 'responsibles', 'answer_type', 'required', 'order')


class EmailTemplateInline(NestedStackedInline):
    fields = ('name', 'subject', 'content')
    model = models.EmailTemplate
    extra = 0


class RevisionInline(NestedStackedInline):
    fields = ('name', ('valid_from', 'valid_to'), 'send_emails_after',
              'send_bulk_email_to_participants')
    model = models.FormRevision
    extra = 0


#class ResponsibilityPersonInline(NestedStackedInline):
#    model = models.Member
#    extra = 0
#    fields = (('forenames', 'surname'), ('email', 'phone_number'), 'street_address',
#              ('postal_code', 'city'), 'send_email_notifications', 'hide_contact_details',
#              'show_full_report', 'personal_link')
#    readonly_fields = ('personal_link',)


@admin.register(models.ServiceForm)
class ServiceFormAdmin(OwnerSaveMixin, ExtendedLogMixin, NestedModelAdminMixin,
                       GuardedModelAdminMixin, admin.ModelAdmin):
    class Media:
        css = {'all': ('serviceform/serviceform_admin.css',)}

    inlines = [RevisionInline, EmailTemplateInline, Level1CategoryInline, QuestionInline]

    superuser_actions = ['bulk_email_former_participants', 'bulk_email_responsibles']
    if settings.DEBUG:
        superuser_actions.append('shuffle_data')

    actions = superuser_actions

    prepopulated_fields = {'slug': ('name',)}
    list_display = (
        'name', 'id', 'can_access', 'last_editor', 'responsible', 'created_at', 'last_updated',
        'current_revision', 'is_published_display', 'participation_count', 'links')
    list_select_related = ('responsible', 'current_revision', 'last_editor')

    basic = ('name',
             'slug',
             )
    ownership = ('responsible', 'can_access')

    email_settings = (
        'require_email_verification',
        'verification_email_to_participant',
        'email_to_responsibles',
        'email_to_invited_users',

        'email_to_participant',
        'resend_email_to_participant',

        'email_to_participant_on_update',
        'email_to_former_participants',

        'bulk_email_to_responsibles',
        'email_to_responsible_auth_link',
    )

    customization = (
        'current_revision',
        'password',
        'hide_contact_details',
        ('flow_by_categories', 'allow_skipping_categories'),
        'level1_color',
        'level2_color',
        'activity_color',
        'login_text',
        'description',
        'instructions',
    )
    visible_contact_details = (
    ('visible_year_of_birth', 'visible_street_address', 'visible_phone_number'),)
    required_contact_details = (
    ('required_year_of_birth', 'required_street_address', 'required_phone_number'),)

    fieldsets = ((_('Basic information'), {'fields': basic}),
                 (_('Ownership'), {'fields': ownership}),
                 (_('Email settings'), {'fields': email_settings}),
                 (_('Customization'), {'fields': customization}),
                 (_('Ask details from participants'), {'fields': visible_contact_details}),
                 (_('Require details from participants'), {'fields': required_contact_details}),
                 )

    new_fieldsets = ((_('Basic information'), {'fields': basic}),)
    readonly_fields = ('can_access',)

    def get_fieldsets(self, request: HttpRequest, obj: models.ServiceForm=None):
        return self.new_fieldsets if obj is None else super().get_fieldsets(request, obj)

    def get_inline_instances(self, request: HttpRequest, obj: models.ServiceForm=None):
        return super().get_inline_instances(request, obj) if obj else []

    def get_actions(self, request: HttpRequest):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            for a in self.superuser_actions:
                actions.pop(a, None)
        return actions

    def bulk_email_former_participants(self, request: HttpRequest,
                                       queryset: Iterable[models.ServiceForm]) -> None:
        for serviceform in queryset:
            serviceform.bulk_email_former_participants()

    bulk_email_former_participants.short_description = _('Bulk email former participants now!')

    def bulk_email_responsibles(self, request: HttpRequest,
                                queryset: Iterable[models.ServiceForm]) -> None:
        for serviceform in queryset:
            serviceform.bulk_email_responsibles()

    bulk_email_responsibles.short_description = _('Bulk email responsibility persons now!')

    def shuffle_data(self, request: HttpRequest,
                     queryset: Iterable[models.ServiceForm]) -> None:
        for serviceform in queryset:
            utils.shuffle_person_data(serviceform)

    shuffle_data.short_description = _('Shuffle participant data')

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return get_objects_for_user(request.user, 'serviceform.can_access_serviceform', klass=qs,
                                    use_groups=True)

    def get_form(self, request: HttpRequest, obj: models.ServiceForm=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj:
            request._responsibles = responsibles = models.Member.objects.filter(
                form=obj)
            form.base_fields['responsible'].queryset = responsibles
            form.base_fields['current_revision'].queryset = models.FormRevision.objects.filter(
                form=obj)

            emailtemplates = models.EmailTemplate.objects.filter(form=obj)

            for name, field in form.base_fields.items():
                if 'email_to' in name:
                    field.queryset = emailtemplates
                    if obj and field.queryset:
                        field.required = True

        return form

    def save_model(self, request: HttpRequest, obj: models.ServiceForm, form, change: bool):
        obj.last_editor = request.user
        rv = super().save_model(request, obj, form, change)
        if not change:
            obj.create_initial_data()
        if obj.pk:
            count = obj.level1category_set.count()
            if obj.flow_by_categories and count > 7:
                messages.warning(request, _(
                    'You have {} level 1 categories. We recommend that no more than '
                    '7 level 1 categories are used, if form flow is split to categories, '
                    'so that form is rendered correctly.').format(count))
        return rv

    def save_related(self, request: HttpRequest, form, formsets, change: bool):
        rv = super().save_related(request, form, formsets, change)
        form.instance.reschedule_bulk_email()
        return rv



@admin.register(models.EmailMessage)
class EmailMessageAdmin(ExtendedLogMixin, admin.ModelAdmin):
    list_display = ('to_address', 'created_at', 'sent_at', 'subject_display', 'template',
                    'content_display',)


@admin.register(models.Organization)
class EmailMessageAdmin(ExtendedLogMixin, admin.ModelAdmin):
    list_display = ('name',)


@admin.register(models.Participation)
class ParticipantAdmin(ExtendedLogMixin, admin.ModelAdmin):
    list_display = (
        'id', '__str__', 'form_display', 'form_revision', 'status', 'activities_display',
        'created_at', 'last_modified')
    fields = ('forenames', 'surname')

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('form_revision__form')
        if request.user.is_superuser or settings.OTHER_CAN_SEE_DATA:
            return qs
        allowed_forms = get_objects_for_user(request.user, 'serviceform.can_access_serviceform',
                                             models.ServiceForm)
        return qs.filter(form_revision__form__in=allowed_forms).distinct()
