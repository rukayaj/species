# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-04-18 08:02
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('taxa', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='taxon',
            old_name='notes',
            new_name='taxonomic_notes',
        ),
    ]
