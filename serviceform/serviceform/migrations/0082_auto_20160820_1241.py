# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-08-20 09:41
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0081_questionanswer_created_at'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='participationactivity',
            name='hint_name',
        ),
        migrations.RemoveField(
            model_name='participationactivitychoice',
            name='hint_name',
        ),
    ]