# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-09-25 09:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0099_serviceform_verification_email_to_participant'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='email_verified',
            field=models.BooleanField(default=False, verbose_name='Email verified'),
        ),
    ]
