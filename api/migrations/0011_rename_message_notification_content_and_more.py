# Generated by Django 5.0.2 on 2024-02-28 22:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_alter_review_rating'),
    ]

    operations = [
        migrations.RenameField(
            model_name='notification',
            old_name='message',
            new_name='content',
        ),
        migrations.RenameField(
            model_name='notification',
            old_name='user',
            new_name='recipient',
        ),
    ]
