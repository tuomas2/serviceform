# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-22 10:40
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scheduled_time', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('target_id', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('requested', 'Requested'), ('done', 'Done'), ('error', 'Error'), ('canceled', 'Canceled')], default='requested', max_length=16)),
                ('method_name', models.CharField(max_length=64)),
                ('data', models.TextField()),
                ('result', models.TextField()),
                ('target_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
            ],
        ),
    ]
