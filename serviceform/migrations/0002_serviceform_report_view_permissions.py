# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-05-06 16:42
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('serviceform', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='serviceform',
            name='report_view_permissions',
            field=models.ManyToManyField(related_name='report_viewers', to=settings.AUTH_USER_MODEL),
        ),
    ]
