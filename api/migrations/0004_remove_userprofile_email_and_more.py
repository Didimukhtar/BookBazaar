# Generated by Django 5.0.2 on 2024-02-24 14:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_userprofile_email_userprofile_first_name_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='email',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='last_name',
        ),
    ]
