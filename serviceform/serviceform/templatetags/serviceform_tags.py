from typing import NamedTuple, Dict, List, TYPE_CHECKING, Union, Iterable, Sequence

from django import template
from django.core.urlresolvers import reverse
from django.template import Context
from django.utils.html import format_html
from django.utils.safestring import mark_safe, SafeString
from django.utils.translation import gettext_lazy as _

from ..models import Participation
from ..utils import safe_join, ColorStr
from .. import utils
from ..urls import participant_flow_urls, menu_urls, Requires
from ..utils import lighter_color as lighter_color_util, darker_color

register = template.Library()
if TYPE_CHECKING:
    from ..models import (Member, SubitemMixin, Activity,
                          ActivityChoice, ParticipationActivity, ParticipationActivityChoice,
                          Question, QuestionAnswer)
    from ..models.serviceform import AbstractServiceFormItem


class FlowItem(NamedTuple):
    name: str
    title: str
    target: str
    attrs: Dict[str, str]


class MenuItem(NamedTuple):
    name: str
    title: str
    url: str
    is_active: bool


class MenuItems(NamedTuple):
    left: List[MenuItem]
    right: List[MenuItem]


@register.simple_tag(takes_context=True)
def responsible_link(context: Context, item: 'AbstractServiceFormItem') -> SafeString:
    """
    Used in category captions in report views, for example
    """
    responsible = context.get('responsible')
    service_form = context.get('service_form')
    item_responsibles = item.responsibles.all()
    links = []
    for item_responsible in item_responsibles:
        if responsible != item_responsible:
            links.append(
                format_html('<a class="responsible-link" href="{}">{}</a>',
                            reverse('view_responsible',
                                    args=(item_responsible.pk, service_form.slug)),
                            item_responsible))
        else:
            links.append(mark_safe(responsible))

    rv = format_html('({})', safe_join(', ', links)) if links else ''
    return rv


@register.assignment_tag
def has_responsible(item: 'AbstractServiceFormItem', responsible: 'Member') -> bool:
    return item.has_responsible(responsible)


@register.assignment_tag(takes_context=True)
def participation_items(context: Context, item: 'Union[Activity, ActivityChoice]')\
        -> 'Sequence[ParticipationActivity, ParticipationActivityChoice]':
    revision_name = utils.get_report_settings(context['request'], 'revision')
    return item.participation_items(revision_name)


@register.assignment_tag(takes_context=True)
def questionanswers(context: Context, item: 'Question') -> 'Sequence[QuestionAnswer]':
    revision_name = utils.get_report_settings(context['request'], 'revision')
    return item.questionanswers(revision_name)


@register.assignment_tag(takes_context=True)
def all_revisions(context: Context) -> bool:
    revision_name = utils.get_report_settings(context['request'], 'revision')
    return revision_name == utils.RevisionOptions.ALL


@register.assignment_tag(takes_context=True)
def participants(context: Context) -> 'Sequence[Participation]':
    revision_name = utils.get_report_settings(context['request'], 'revision')
    service_form = context.get('service_form')

    qs = Participation.objects.filter(
        form_revision__form=service_form,
        status__in=Participation.READY_STATUSES).order_by('member__surname')
    if revision_name == utils.RevisionOptions.CURRENT:
        qs = qs.filter(form_revision__id=service_form.current_revision_id)
    elif revision_name == utils.RevisionOptions.ALL:
        pass
    else:
        qs = qs.filter(form_revision__name=revision_name)
    return [utils.get_participant(i) for i, in qs.values_list('pk')]


@register.assignment_tag(takes_context=True)
def participant_flow_menu_items(context: Context) -> List[FlowItem]:
    current_view = context['request'].resolver_match.view_name
    # TODO: rename participant -> participation everywhere
    # TODO: fix menu for contact_details_creation (+ possibly all others)

    request = context['request']
    participant = getattr(request, 'participant', None)
    service_form = context['service_form']
    cat_num = context.get('cat_num', 0)
    lst = []

    for idx, f_item in enumerate(participant_flow_urls):
        if participant and f_item.name not in participant.flow:
            continue
        if current_view == f_item.name:
            attrs = {'current': True, 'disabled': True}
        elif not participant or not participant.can_access_view(f_item.name):
            attrs = {'greyed': True, 'disabled': True}
        else:
            attrs = {}
        if f_item.name == 'participation':
            url = reverse(f_item.name, args=(service_form.slug, cat_num))
        else:
            url = reverse(f_item.name, args=(service_form.slug,))
        flv = FlowItem(f_item.name, f_item.default_args.get('title', ''), url, attrs)
        lst.append(flv)
    return lst


@register.assignment_tag(takes_context=True)
def participant_flow_categories(context: Context) -> List[FlowItem]:
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
        url = reverse(current_view, args=(service_form.slug, idx,))
        flv = FlowItem(idx, category.name, url, attrs)
        lst.append(flv)
    return lst


@register.assignment_tag(takes_context=True)
def menu_items(context: Context, menu_name: str) -> MenuItems:
    """
    This is used for:
     - Reports menu
     - Participation password_login page menu
    """
    current_view = context['request'].resolver_match.view_name
    service_form = context['service_form']
    responsible = utils.get_authenticated_member(context['request'])

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
        itm = MenuItem(name, title, url, is_active)
        if is_right:
            right.append(itm)
        else:
            left.append(itm)
    return MenuItems(left, right)


@register.filter()
def shorten(text: str) -> SafeString:
    return format_html('<span class="tooltip-only" title="{}" >{}...</span>', text,
                       text[:5].strip())


@register.filter()
def lighter_color(cat_color: ColorStr) -> ColorStr:
    return lighter_color_util(cat_color)


@register.filter(is_safe=True)
def url_target_blank(text: str) -> str:
    return text.replace('<a ', '<a target="_blank" ')


@register.filter()
def count_color(count: int) -> SafeString:
    color_for_count = utils.color_for_count(count)
    return format_html('<span class="color-count" style="background: {};">{}</span>',
                       color_for_count, count)


@register.simple_tag()
def color_style(item: 'AbstractServiceFormItem', lighter=0, attr='background') -> SafeString:
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
        return format_html('')


@register.filter()
def translate_bool(value: bool) -> str:
    _('True')
    _('False')
    return _(str(value))
