# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-07-29 10:36
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0066_auto_20160729_1335'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailmessage',
            name='template',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='serviceform.EmailTemplate'),
        ),
    ]