# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-08-16 18:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.CharField(choices=[('error', 'Error'), ('requested', 'Requested'), ('canceled', 'Canceled'), ('done', 'Done')], default='requested', max_length=16),
        ),
    ]