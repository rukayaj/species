# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-02-19 08:44
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('taxa', '0015_generaldistribution_descripton'),
    ]

    operations = [
        migrations.RenameField(
            model_name='generaldistribution',
            old_name='descripton',
            new_name='description',
        ),
    ]