# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-24 11:51
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel('ResponsibilityPerson', 'Member')
    ]
