# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-02-19 08:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('biblio', '0006_auto_20170214_0944'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reference',
            name='title',
            field=models.CharField(default='No title', max_length=500),
            preserve_default=False,
        ),
    ]
