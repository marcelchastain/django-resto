test:
	PYTHONPATH=. DJANGO_SETTINGS_MODULE=django_dust.test_settings \
	django-admin.py test django_dust

coverage:
	coverage erase
	PYTHONPATH=. DJANGO_SETTINGS_MODULE=django_dust.test_settings \
	coverage run --source=django_dust `which django-admin.py` test django_dust
	coverage html
