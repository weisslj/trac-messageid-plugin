#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Johannes Weißl
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

# Use this script if you have an existing Trac database and are about
# to change e.g. the sender address domain. It populates the messageid
# table with computed values.

from optparse import OptionParser

from trac.env import open_environment
from trac.notification.mail import create_message_id

def fill_messageid(env, db, opts):
    smtp_from = env.config['notification'].get('smtp_from')
    cursor = db.cursor()
    if not opts.dry_run and opts.rebuild:
        cursor.execute("DELETE FROM messageid")
    cursor.execute("""
        SELECT id FROM ticket WHERE id NOT IN (SELECT ticket FROM messageid)
        """)
    for ticket_id, in cursor.fetchall():
        msgid = create_message_id(env, ticket_id, smtp_from, None, 'ticket')
        if opts.verbose:
            print '%s -> %s' % (ticket_id, msgid)
        if not opts.dry_run:
            cursor.execute("""
                INSERT OR IGNORE INTO messageid (ticket,messageid)
                VALUES (%s, %s)
                """, (ticket_id, msgid))
    db.commit()

def main(args=None):
    parser = OptionParser('%prog [options] <project1> <project2> ...')
    parser.add_option('-v', '--verbose', action='store_true', default=False,
                      help='print ')
    parser.add_option('--rebuild', action='store_true', default=False,
                      help='clear messageid table before (use with care)')
    parser.add_option('-n', '--dry-run', action='store_true', default=False,
                      help='do not modify the database')
    opts, args = parser.parse_args(args)
    if ops.rebuild and opts.dry_run:
        parser.error('options --rebuild and --dry-run are mutually exclusive')
    if not args:
        parser.error('no project specified')
    for arg in args:
        env = open_environment(arg)
        with env.db_transaction as db:
            fill_messageid(env, db, opts)

if __name__ == '__main__':
    main()
