# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-21 07:58
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0105_auto_20161021_1056'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='auth_key_expire',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='responsibilityperson',
            name='auth_key_expire',
            field=models.DateTimeField(null=True),
        ),
    ]
