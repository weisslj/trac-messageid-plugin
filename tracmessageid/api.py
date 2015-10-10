# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Johannes Weißl
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

import re
import email
import time
import smtplib

from genshi.builder import tag

from trac.core import implements, Component, TracError
from trac.config import Option, IntOption, BoolOption, ConfigurationError
from trac.env import IEnvironmentSetupParticipant
from trac.notification import IEmailSender
from trac.db import DatabaseManager
from trac.util.text import CRLF, fix_eol, to_unicode
from trac.util.translation import _, tag_

import db_default

# Based on smtplib.sendmail() of Python 2.7.10, but returning last response.
def sendmail(server, from_addr, to_addrs, msg):
    server.ehlo_or_helo_if_needed()
    esmtp_opts = []
    if server.does_esmtp and server.has_extn('size'):
        esmtp_opts.append("size=%d" % len(msg))
    (code, resp) = server.mail(from_addr, esmtp_opts)
    if code != 250:
        server.rset()
        raise smtplib.SMTPSenderRefused(code, resp, from_addr)
    senderrs = {}
    if isinstance(to_addrs, basestring):
        to_addrs = [to_addrs]
    for each in to_addrs:
        (code, resp) = server.rcpt(each)
        if (code != 250) and (code != 251):
            senderrs[each] = (code, resp)
    if len(senderrs) == len(to_addrs):
        server.rset()
        raise smtplib.SMTPRecipientsRefused(senderrs)
    (code, resp) = server.data(msg)
    if code != 250:
        server.rset()
        raise smtplib.SMTPDataError(code, resp)
    return resp

# Based on trac.notification.SmtpEmailSender() of Trac 1.0.10.
class MessageIdSmtpEmailSender(Component):

    implements(IEnvironmentSetupParticipant, IEmailSender)

    smtp_server = Option('notification', 'smtp_server', 'localhost',
        """SMTP server hostname to use for email notifications.""")

    smtp_port = IntOption('notification', 'smtp_port', 25,
        """SMTP server port to use for email notification.""")

    smtp_user = Option('notification', 'smtp_user', '',
        """Username for SMTP server. (''since 0.9'')""")

    smtp_password = Option('notification', 'smtp_password', '',
        """Password for SMTP server. (''since 0.9'')""")

    use_tls = BoolOption('notification', 'use_tls', 'false',
        """Use SSL/TLS to send notifications over SMTP. (''since 0.10'')""")

    # IEmailSender methods
    def send(self, from_addr, recipients, message):
        # Ensure the message complies with RFC2822: use CRLF line endings
        message = fix_eol(message, CRLF)

        self.log.info("Sending notification through SMTP at %s:%d to %s",
                      self.smtp_server, self.smtp_port, recipients)
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        except smtplib.socket.error, e:
            raise ConfigurationError(
                tag_("SMTP server connection error (%(error)s). Please "
                     "modify %(option1)s or %(option2)s in your "
                     "configuration.",
                     error=to_unicode(e),
                     option1=tag.tt("[notification] smtp_server"),
                     option2=tag.tt("[notification] smtp_port")))
        # server.set_debuglevel(True)
        if self.use_tls:
            server.ehlo()
            if 'starttls' not in server.esmtp_features:
                raise TracError(_("TLS enabled but server does not support "
                                  "TLS"))
            server.starttls()
            server.ehlo()
        if self.smtp_user:
            server.login(self.smtp_user.encode('utf-8'),
                         self.smtp_password.encode('utf-8'))
        start = time.time()
        resp = sendmail(server, from_addr, recipients, message)
        t = time.time() - start
        if t > 5:
            self.log.warning('Slow mail submission (%.2f s), '
                             'check your mail setup', t)
        if self.use_tls:
            # avoid false failure detection when the server closes
            # the SMTP connection with TLS enabled
            import socket
            try:
                server.quit()
            except socket.sslerror:
                pass
        else:
            server.quit()

        msg = email.message_from_string(message)
        ticket_id = int(msg['x-trac-ticket-id'])
        msgid = msg['message-id']
        aws_re = r'^email-smtp\.([a-z0-9-]+)\.amazonaws\.com$'
        m = re.match(aws_re, self.smtp_server)
        if m:
            parts = resp.split()
            if len(parts) == 2 and parts[0] == 'Ok':
                region = m.group(1)
                msgid = '<%s@%s.amazonses.com>' % (parts[1], region)
        with self.env.db_transaction as db:
            cursor = db.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO messageid (ticket,messageid)
                VALUES (%s, %s)
                """, (ticket_id, msgid))

    # IEnvironmentSetupParticipant method
    def environment_created(self):
        if self.environment_needs_upgrade():
            self.upgrade_environment()

    # IEnvironmentSetupParticipant method
    def environment_needs_upgrade(self, _unused_db=None):
        return self.database_needs_upgrade(db_default.version, db_default.name)

    # IEnvironmentSetupParticipant method
    def upgrade_environment(self, _unused_db=None):
        dbm = DatabaseManager(self.env)
        if self.get_database_version(db_default.name) == 0:
            dbm.create_tables(db_default.tables)
            self.set_database_version(db_default.version, db_default.name)

    # DatabaseManager.get_database_version() from Trac 1.1.
    def get_database_version(self, name):
        rows = self.env.db_query("""
                SELECT value FROM system WHERE name=%s
                """, (name,))
        return int(rows[0][0]) if rows else False

    # DatabaseManager.set_database_version() from Trac 1.1.
    def set_database_version(self, version, name):
        current_database_version = self.get_database_version(name)
        if current_database_version is False:
            self.env.db_transaction("""
                    INSERT INTO system (name, value) VALUES (%s, %s)
                    """, (name, version))
        else:
            self.env.db_transaction("""
                    UPDATE system SET value=%s WHERE name=%s
                    """, (version, name))
            self.log.info("Upgraded %s from %d to %d",
                          name, current_database_version, version)

    # DatabaseManager.needs_upgrade() from Trac 1.1.
    def database_needs_upgrade(self, version, name):
        dbver = self.get_database_version(name)
        if dbver == version:
            return False
        elif dbver > version:
            raise TracError(_("Need to downgrade %(name)s.", name=name))
        self.log.info("Need to upgrade %s from %d to %d",
                      name, dbver, version)
        return True
