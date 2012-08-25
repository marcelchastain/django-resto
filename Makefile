test:
	DJANGO_SETTINGS_MODULE=django_resto.tests.test_settings \
	django-admin.py test django_resto

coverage:
	coverage erase
	DJANGO_SETTINGS_MODULE=django_resto.tests.test_settings \
	coverage run --source=django_resto `which django-admin.py` test django_resto
	coverage html

clean:
	find . -name '*.pyc' -delete
	find . -name __pycache__ -delete
	rm -rf django_resto/tests/media .coverage dist htmlcov MANIFEST
