#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Johannes Weißl
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

from setuptools import find_packages, setup

setup(
    name = 'TracMessageIdPlugin',
    version = '1.1.0',
    keywords = 'trac plugin messageid message id aws ses',
    author = 'Johannes Weißl',
    author_email = 'jargon@molb.org',
    url = 'https://github.com/weisslj/trac-messageid-plugin',
    description = 'Trac Message-ID Plugin',
    long_description = """
    This plugin for Trac >= 1.1.3 stores the Message-ID of new ticket
    notifications in a new database table, so that they can be
    used for the In-Reply-To header of subsequent emails.

    This is necessary when using Amazon's Simple Email Service (AWS SES),
    because it rewrites the message id. It is also useful when changing the
    project URL or sender domain (otherwise replies will end up in a new
    thread).
    """,
    license = 'BSD',
    install_requires = ['Trac >= 1.1.3'],
    packages = find_packages(exclude=['*.tests*']),
    entry_points = {
        'trac.plugins': [
            'tracmessageid.api = tracmessageid.api',
        ],
        'console_scripts': [
            'fill-trac-messageid = tracmessageid.fill:main',
        ],
    },
)
