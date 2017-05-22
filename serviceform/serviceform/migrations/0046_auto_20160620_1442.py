# -*- coding: utf-8 -*-
# Generated by Django 1.9.7.dev20160521075240 on 2016-06-20 11:42
from __future__ import unicode_literals

from django.db import migrations, models
import serviceform.models
import serviceform.utils


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0045_participant_secret_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='participant',
            name='secret_key',
            field=models.CharField(db_index=True, default=serviceform.utils.generate_uuid, max_length=36, unique=True, verbose_name='Secret key'),
        ),
    ]