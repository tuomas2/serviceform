# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-09-25 09:15
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0098_auto_20160925_1207'),
    ]

    operations = [
        migrations.AddField(
            model_name='serviceform',
            name='verification_email_to_participant',
            field=models.ForeignKey(blank=True, help_text='Email verification message that is sent to participant when filling form, if email verification is enabled', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='serviceform.EmailTemplate', verbose_name='Verification email to participant'),
        ),
    ]
