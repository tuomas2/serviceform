# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-08-17 09:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0004_auto_20160817_1218'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.CharField(choices=[('requested', 'Requested'), ('done', 'Done'), ('error', 'Error'), ('canceled', 'Canceled')], default='requested', max_length=16),
        ),
    ]