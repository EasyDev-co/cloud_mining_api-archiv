# Generated by Django 4.2 on 2023-06-21 01:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_alter_user_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, error_messages={'max_length': 'A telephone number cannot have more than 15 digits', 'unique': 'A user with that phone number already exists.'}, max_length=15, verbose_name='phone number'),
        ),
    ]
