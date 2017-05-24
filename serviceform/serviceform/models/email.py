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
import json
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.template import Context, Template
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger(__name__)
from .mixins import CopyMixin

if TYPE_CHECKING:
    from .serviceform import ServiceForm

class EmailMessage(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    template = models.ForeignKey('serviceform.EmailTemplate', null=True, on_delete=models.SET_NULL)
    from_address = models.CharField(max_length=256)
    to_address = models.CharField(max_length=256)
    subject = models.CharField(max_length=256)
    content = models.TextField()
    sent_at = models.DateTimeField(null=True)
    context = models.TextField(default="{}")  # JSONified context variables

    def __str__(self):
        return '<EmailMessage %s to %s>' % (self.pk, self.to_address)

    @cached_property
    def context_dict(self) -> Context:
        return Context(json.loads(self.context))

    def content_display(self) -> str:
        return Template(self.content).render(self.context_dict)

    content_display.short_description = _('Content')

    def subject_display(self) -> str:
        return Template(self.subject).render(self.context_dict)

    subject_display.short_description = _('Subject')

    def _cleanup_context(self) -> None:
        context = json.loads(self.context)
        if 'url' in context:
            # Remove URL from email message, as it contains password
            context['url'] = 'http://***password*removed***'
            self.context = json.dumps(context)
            self.save(update_fields=['context'])

    def send(self) -> None:
        logger.info('Sending email to %s', self.to_address)
        body = self.content_display()
        html_body = render_to_string('serviceform/email.html', context={'body': body})
        headers = {'List-Unsubscribe': '<%s>' % self.context_dict['list_unsubscribe']}
        mail = EmailMultiAlternatives(subject=self.subject_display(),
                                      body=body,
                                      from_email=settings.SERVER_EMAIL,
                                      headers=headers,
                                      to=[self.to_address])
        mail.attach_alternative(html_body, 'text/html')
        emails = mail.send()
        if emails == 1:
            self.sent_at = timezone.now()
            self.save(update_fields=['sent_at'])
            self._cleanup_context()
        else:
            logger.error('Email message to %s could not be sent', self)

    @classmethod
    def make(cls, template: 'EmailTemplate', context_dict: dict, address: str,
             send: bool=False) -> 'EmailMessage':
        logger.info('Creating email to %s', address)
        msg = cls.objects.create(template=template, to_address=address,
                                 from_address=settings.SERVER_EMAIL,
                                 subject=template.subject, content=template.content,
                                 context=json.dumps(context_dict))
        if send:
            msg.send()
        return msg


class EmailTemplate(CopyMixin, models.Model):
    class Meta:
        verbose_name = _('Email template')
        verbose_name_plural = _('Email templates')

    def __str__(self):
        return self.name

    name = models.CharField(_('Template name'), max_length=256)
    subject = models.CharField(_('Subject'), max_length=256)
    content = models.TextField(_('Content'), help_text=_(
        'Following context may (depending on topic) be available for both subject and content: '
        '{{responsible}}, {{participant}}, {{last_modified}}, {{form}}, {{url}}, {{contact}}'))
    form = models.ForeignKey('serviceform.ServiceForm', on_delete=models.CASCADE)

    @classmethod
    def make(cls, name: str, form: 'ServiceForm', content: str, subject: str):
        return cls.objects.create(name=name, form=form, subject=subject, content=content)