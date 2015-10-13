from setuptools import setup, find_packages
import os

version = '0.0.1'

setup(
    name='frappe_subscription',
    version=version,
    description='Frappe Subscription',
    author='Indictrans',
    author_email='contact@indictranstech.com',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=("frappe",),
)
