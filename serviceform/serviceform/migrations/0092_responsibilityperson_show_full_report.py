# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-09-16 12:11
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0091_auto_20160916_1053'),
    ]

    operations = [
        migrations.AddField(
            model_name='responsibilityperson',
            name='show_full_report',
            field=models.BooleanField(default=False, verbose_name='Grant access to full reports'),
        ),
    ]