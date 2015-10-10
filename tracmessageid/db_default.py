# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Johannes Weißl
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

from trac.db import Table, Column

name = 'messageid'
version = 1
tables = [
    Table(name, key='ticket')[
        Column('ticket', type='int'),
        Column('messageid'),
    ],
]
