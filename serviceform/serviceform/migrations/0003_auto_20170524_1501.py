# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-24 12:01
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0002_rename_responsibilityperson_to_member'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='member',
            options={},
        ),
        migrations.AddField(
            model_name='member',
            name='membership_type',
            field=models.CharField(choices=[('external', 'external'), ('normal', 'normal'), ('staff', 'staff')], default='external', max_length=8, verbose_name='Is this person a member of this organization?'),
        ),
        migrations.AlterField(
            model_name='member',
            name='city',
            field=models.CharField(max_length=32, verbose_name='City'),
        ),
        migrations.AlterField(
            model_name='member',
            name='phone_number',
            field=models.CharField(max_length=32, validators=[django.core.validators.RegexValidator(message="Phone number must be entered in the format: '050123123' or '+35850123123'. Up to 15 digits allowed.", regex='^\\+?1?\\d{9,15}$')], verbose_name='Phone number'),
        ),
        migrations.AlterField(
            model_name='member',
            name='postal_code',
            field=models.CharField(max_length=32, validators=[django.core.validators.RegexValidator(code='invalid', message='Enter a valid postal code.', regex='^\\d{5}$')], verbose_name='Zip/Postal code'),
        ),
        migrations.AlterField(
            model_name='member',
            name='street_address',
            field=models.CharField(max_length=128, verbose_name='Street address'),
        ),
    ]