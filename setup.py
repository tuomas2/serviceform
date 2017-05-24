#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

setup(
    name="serviceform",
    version="0.9.5",
    description="Django web application to collect volunteering willingness "
                "data and report to responsible people",
    long_description=readme,
    author="Tuomas Airaksinen",
    author_email="tuomas.airaksinen@gmail.com",
    url="https://github.com/tuomas2/serviceform",
    packages=['serviceform.'+i for i in find_packages('serviceform')],
    include_package_data=True,
    install_requires=[
        "Django",
        "django-libsass",
        "psycopg2",
        "django-nested-admin",
        "django-crispy-forms",
        "django-colorful",
        "colour",
        "django-redis-cache",
        "django-compressor",
        "django-guardian",
        "django-select2-forms",
    ],
    extras_require={
        'cachalot': ['django-cachalot'],
        'grappelli': ['django-grappelli'],
        'celery': ['django-celery', 'celery'],
    },
    license="GPL",
    zip_safe=False,
    classifiers=[
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
)