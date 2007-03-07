#! /usr/bin/env python

from setuptools import setup, Extension

setup(name="pydmc",
      version="0.1",
      description="My useful routines",
      author="David M. Cooke",
      author_email="david.m.cooke@gmail.com",
      license="GPL",

      packages = ['pydmc'],
      ext_modules = [
          Extension('pydmc._count', ['src/_count.pyx']),
          ],
      zip_safe=True,
      )
