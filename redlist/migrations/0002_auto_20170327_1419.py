# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-03-27 12:19
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('redlist', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assessment',
            name='redlist_criteria',
            field=models.CharField(max_length=200),
        ),
    ]
