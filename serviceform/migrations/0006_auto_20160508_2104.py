# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-05-08 18:04
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0005_auto_20160508_2052'),
    ]

    operations = [
        migrations.RenameField(
            model_name='serviceform',
            old_name='report_view_permissions',
            new_name='allowed_users',
        ),
    ]
