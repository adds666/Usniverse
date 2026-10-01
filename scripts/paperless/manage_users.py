"""Run in manage.py shell; read initial member credentials from stdin, never log them."""
import json
import sys
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
payload = json.load(sys.stdin)
group, _ = Group.objects.get_or_create(name='Usniverse Members')
models = ['document', 'tag', 'correspondent', 'documenttype', 'note', 'savedview', 'uisettings']
permissions = Permission.objects.filter(content_type__app_label='documents', content_type__model__in=models,
                                         codename__regex=r'^(add|view|change|delete)_')
permissions = permissions | Permission.objects.filter(content_type__app_label='documents', codename='view_paperlesstask')
group.permissions.set(permissions)
user, created = get_user_model().objects.get_or_create(username=payload['member_username'])
if created:
    user.set_password(payload['member_password'])
    user.is_staff = False
    user.is_superuser = False
    user.save()
user.groups.add(group)
print(json.dumps({'memberCreated': created, 'group': group.name, 'permissionCount': group.permissions.count()}))
