# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-05-11 15:58
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0017_auto_20160511_1849'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='participant',
            name='form',
        ),
        migrations.RemoveField(
            model_name='participationactivity',
            name='form_revision',
        ),
        migrations.RemoveField(
            model_name='participationactivitychoice',
            name='form_revision',
        ),
        migrations.RemoveField(
            model_name='questionanswer',
            name='form_revision',
        ),
    ]
