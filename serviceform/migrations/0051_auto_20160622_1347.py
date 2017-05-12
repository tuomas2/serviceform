# -*- coding: utf-8 -*-
# Generated by Django 1.9.7.dev20160521075240 on 2016-06-22 10:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serviceform', '0050_participant_send_email_allowed'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='last_finished_form',
            field=models.CharField(default='', max_length=32),
        ),
        migrations.AlterField(
            model_name='participant',
            name='send_email_allowed',
            field=models.BooleanField(default=True, help_text='You will receive email that allows later modification of the form. Also when new version of form is published, you will be notified. It is highly recommended that you keep this enabled unless you move away and do not want to participate at all any more. You can also change this setting later if you wish.', verbose_name='Sending email allowed'),
        ),
    ]
