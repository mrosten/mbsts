import os
import inspect
from setuptools import setup, find_packages

setup(name='sprout',
      version='0.2',
      description='Asynchronous Python Framework',
      author=['Moshe Rosten'],
      author_email='mosherosten@gmail.com',
      license='MIT',
      include_package_data=True,
      packages=find_packages(),
      zip_safe=False,
      install_requires=[
          "imaplib2",
          "mail-parser",
          "aiocron",
          "asyncssh",
          "transitions",
          "aiosqlite",
          "aiojobs",
          "jinja2",
          "aiodocker",
          "docker",
          "aiohttp",
          "python-box",
          "pyjwt",
          "pyyaml",
          "requests"
      ])
