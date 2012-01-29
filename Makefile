test:
	PYTHONPATH=. DJANGO_SETTINGS_MODULE=django_resto.test_settings \
	django/bin/django-admin.py test django_resto

coverage:
	coverage erase
	PYTHONPATH=. DJANGO_SETTINGS_MODULE=django_resto.test_settings \
	coverage run --source=django_resto django/bin/django-admin.py test django_resto
	coverage html

clean:
	find . -name '*.pyc' -delete
	rm -r django_resto/tests/media .coverage dist htmlcov MANIFEST
