# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-07-29 13:57
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0071_auto_20160729_1548'),
    ]

    operations = [
        migrations.AddField(
            model_name='serviceform',
            name='hide_contact_details',
            field=models.BooleanField(default=False, verbose_name='Hide contact details (other than email) in form'),
        ),
        migrations.AlterField(
            model_name='emailtemplate',
            name='name',
            field=models.CharField(max_length=256, verbose_name='Template name'),
        ),
        migrations.AlterField(
            model_name='serviceform',
            name='bulk_email_to_responsibles',
            field=models.ForeignKey(blank=True, help_text='Email that is sent to responsibles when emailing starts', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='serviceform.EmailTemplate', verbose_name='Bulk email to responsibles'),
        ),
        migrations.AlterField(
            model_name='serviceform',
            name='email_to_former_participants',
            field=models.ForeignKey(blank=True, help_text='Email that is sent to former participants when form is published', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='serviceform.EmailTemplate', verbose_name='Bulk email to former participants'),
        ),
        migrations.AlterField(
            model_name='serviceform',
            name='email_to_participant',
            field=models.ForeignKey(blank=True, help_text='Email that is sent to participant after he has fulfilled his participation', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='serviceform.EmailTemplate', verbose_name='Email to participant'),
        ),
        migrations.AlterField(
            model_name='serviceform',
            name='email_to_responsibles',
            field=models.ForeignKey(blank=True, help_text='Email that is sent to responsibles when new participation is registered', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='serviceform.EmailTemplate', verbose_name='Email to responsibles'),
        ),
        migrations.AlterField(
            model_name='serviceform',
            name='resend_email_to_participant',
            field=models.ForeignKey(blank=True, help_text='Email that is sent to participant if he requests resending email', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='serviceform.EmailTemplate', verbose_name='Resend email to participant'),
        ),
    ]