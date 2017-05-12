# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-08-17 15:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0078_auto_20160817_1218'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='last_finished',
            field=models.DateTimeField(null=True, verbose_name='Last finished'),
        ),
        migrations.AddField(
            model_name='participationactivity',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='participationactivitychoice',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name='participant',
            name='year_of_birth',
            field=models.SmallIntegerField(blank=True, help_text='Optional', null=True, verbose_name='Year of birth'),
        ),
        migrations.RunSQL("UPDATE serviceform_participationactivity SET created_at='2016-01-01 12:00:00+02';", ''),
        migrations.RunSQL("UPDATE serviceform_participationactivitychoice SET created_at='2016-01-01 12:00:00+02';", ''),
        migrations.RunSQL('UPDATE serviceform_participant SET last_finished=last_modified;', ''),
    ]
