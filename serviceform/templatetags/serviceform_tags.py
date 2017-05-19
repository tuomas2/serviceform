from typing import NamedTuple, Dict, List

from django import template
from django.core.urlresolvers import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from serviceform.models import Participant
from serviceform.utils import safe_join
from .. import utils
from ..urls import participant_flow_urls, menu_urls, Requires
from ..utils import lighter_color as lighter_color_util, darker_color

register = template.Library()


class FlowItem(NamedTuple):
    name: str
    title: str
    target: str
    attrs: Dict[str, str]


@register.simple_tag(takes_context=True)
def responsible_link(context, item):
    """
    Used in category captions in report views, for example
    """
    responsible = context.get('responsible')
    item_responsibles = item.responsibles.all()
    links = []
    for item_responsible in item_responsibles:
        if responsible != item_responsible:
            links.append(format_html('<a class="responsible-link" href="{}">{}</a>',
                                     reverse('view_responsible', args=(item_responsible.pk,)),
                                     item_responsible))
        else:
            links.append(mark_safe(responsible))

    rv = format_html('({})', safe_join(', ', links)) if links else ''
    return rv


@register.assignment_tag
def has_responsible(item, responsible):
    return item.has_responsible(responsible)


@register.assignment_tag(takes_context=True)
def participation_items(context, item):
    revision_name = utils.get_report_settings(context['request'], 'revision')
    service_form = context.get('service_form')
    if revision_name == utils.RevisionOptions.ALL:
        for rev in service_form.formrevision_set.all():
            return item.participation_items(rev)
    elif revision_name == utils.RevisionOptions.CURRENT:
        return item.participation_items(service_form.current_revision.name)
    else:
        return item.participation_items(revision_name)


@register.assignment_tag(takes_context=True)
def all_revisions(context):
    revision_name = utils.get_report_settings(context['request'], 'revision')
    return revision_name == utils.RevisionOptions.ALL


@register.assignment_tag(takes_context=True)
def participants(context):
    revision_name = utils.get_report_settings(context['request'], 'revision')
    service_form = context.get('service_form')

    qs = Participant.objects.filter(form_revision__form=service_form,
                                    status__in=Participant.READY_STATUSES).order_by('surname')
    if revision_name == utils.RevisionOptions.CURRENT:
        qs = qs.filter(form_revision__id=service_form.current_revision_id)
    elif revision_name == utils.RevisionOptions.ALL:
        pass
    else:
        qs = qs.filter(form_revision__name=revision_name)
    return [utils.get_participant(i) for i, in qs.values_list('pk')]


@register.assignment_tag(takes_context=True)
def participant_flow_menu_items(context) -> List[FlowItem]:
    current_view = context['request'].resolver_match.view_name
    participant = context['request'].participant
    cat_num = context.get('cat_num', 0)
    lst = []

    for idx, f_item in enumerate(participant_flow_urls):
        if f_item.name not in participant.flow:
            continue
        if current_view == f_item.name:
            attrs = {'current': True, 'disabled': True}
        elif not participant.can_access_view(f_item.name):
            attrs = {'greyed': True, 'disabled': True}
        else:
            attrs = {}
        if f_item.name == 'participation':
            url = reverse(f_item.name, args=(cat_num,))
        else:
            url = reverse(f_item.name)
        flv = FlowItem(f_item.name, f_item.default_args.get('title', ''), url, attrs)
        lst.append(flv)
    return lst


@register.assignment_tag(takes_context=True)
def participant_flow_categories(context):
    current_view = 'participation'
    service_form = context['service_form']
    cat_num = context.get('cat_num', 0)
    max_cat = context.get('max_cat', 0)
    lst = []
    for idx, category in enumerate(service_form.sub_items):
        if idx == cat_num:
            attrs = {'current': True, 'disabled': True}
        elif idx > max_cat:
            attrs = {'greyed': True, 'disabled': True}
        else:
            attrs = {}
        attrs['category'] = category
        url = reverse(current_view, args=(idx,))
        flv = FlowItem(idx, category.name, url, attrs)
        lst.append(flv)
    return lst


@register.assignment_tag(takes_context=True)
def menu_items(context, menu_name):
    """
    This is used for:
     - Reports menu
     - Participation password_login page menu
    """
    current_view = context['request'].resolver_match.view_name
    service_form = context['service_form']
    responsible = utils.get_responsible(context['request'])

    def _check_requires(requires):
        for r in requires:
            if r == Requires.ACCESS_FULL_REPORT:
                if not (responsible and responsible.show_full_report):
                    return False
            if r == Requires.RESPONSIBLE_LOGGED_IN:
                if not responsible:
                    return False
        return True

    left = []
    right = []
    for idx, f_item in enumerate(menu_urls[menu_name]):
        name = f_item.name
        is_active = current_view == name
        arglist = f_item.default_args.get('arglist', ('slug',))
        requires = f_item.default_args.get('require', [])
        if not _check_requires(requires):
            continue

        args = tuple(getattr(service_form, i) for i in arglist)
        url = reverse(name, args=args)
        is_right = f_item.default_args.get('right')
        title = f_item.default_args.get('title', '')
        icon = f_item.default_args.get('icon')
        if icon:
            title = format_html('<span class="fa fa-{}"></span> {}', icon, title)
        itm = {'name': name, 'title': title, 'url': url, 'is_active': is_active}
        if is_right:
            right.append(itm)
        else:
            left.append(itm)
    return {'left': left, 'right': right}


@register.filter()
def shorten(text):
    return format_html('<span class="tooltip-only" title="{}" >{}...</span>', text,
                       text[:5].strip())


@register.filter()
def lighter_color(cat_color):
    return lighter_color_util(cat_color)


@register.filter(is_safe=True)
def url_target_blank(text):
    return text.replace('<a ', '<a target="_blank" ')


@register.filter()
def count_color(count):
    color_for_count = utils.color_for_count(count)
    return format_html('<span class="color-count" style="background: {};">{}</span>',
                       color_for_count, count)


@register.simple_tag()
def color_style(item, lighter=0, attr='background'):
    color = item.background_color_display
    if color:
        if lighter < 0:
            for i in range(-lighter):
                color = darker_color(color)
        else:
            for i in range(lighter):
                color = lighter_color_util(color)
        return format_html('style="{}: {};"', attr, color)
    else:
        return ''


@register.filter()
def translate_bool(value):
    _('True')
    _('False')
    return _(str(value))
