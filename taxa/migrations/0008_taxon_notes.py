# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-01-27 14:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('taxa', '0007_auto_20170124_1557'),
    ]

    operations = [
        migrations.AddField(
            model_name='taxon',
            name='notes',
            field=models.TextField(null=True),
        ),
    ]