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
from trac.db import DatabaseManager
from trac.util.text import CRLF, fix_eol, to_unicode
from trac.util.translation import _, tag_
from trac.notification.api import IEmailSender, IEmailDecorator
from trac.notification.mail import set_header

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

# Based on trac.notification.mail.SmtpEmailSender() of Trac 1.1.3.
class MessageIdSmtpEmailSender(Component):

    implements(IEnvironmentSetupParticipant, IEmailSender, IEmailDecorator)

    smtp_server = Option('notification', 'smtp_server', 'localhost',
        """SMTP server hostname to use for email notifications.""")

    smtp_port = IntOption('notification', 'smtp_port', 25,
        """SMTP server port to use for email notification.""")

    smtp_user = Option('notification', 'smtp_user', '',
        """Username for authenticating with SMTP server.""")

    smtp_password = Option('notification', 'smtp_password', '',
        """Password for authenticating with SMTP server.""")

    use_tls = BoolOption('notification', 'use_tls', 'false',
        """Use SSL/TLS to send notifications over SMTP.""")

    # IEmailSender methods
    def send(self, from_addr, recipients, message):
        # Ensure the message complies with RFC2822: use CRLF line endings
        message = fix_eol(message, CRLF)

        self.log.info("Sending notification through SMTP at %s:%d to %s",
                      self.smtp_server, self.smtp_port, recipients)
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        except smtplib.socket.error as e:
            raise ConfigurationError(
                tag_("SMTP server connection error (%(error)s). Please "
                     "modify %(option1)s or %(option2)s in your "
                     "configuration.",
                     error=to_unicode(e),
                     option1=tag.code("[notification] smtp_server"),
                     option2=tag.code("[notification] smtp_port")))
        # server.set_debuglevel(True)
        if self.use_tls:
            server.ehlo()
            if 'starttls' not in server.esmtp_features:
                raise TracError(_("TLS enabled but server does not support"
                                  " TLS"))
            server.starttls()
            server.ehlo()
        if self.smtp_user:
            server.login(self.smtp_user.encode('utf-8'),
                         self.smtp_password.encode('utf-8'))
        start = time.time()
        resp = sendmail(server, from_addr, recipients, message)
        t = time.time() - start
        if t > 5:
            self.log.warning("Slow mail submission (%.2f s), "
                             "check your mail setup", t)
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

    # IEmailDecorator method
    def decorate_message(self, event, message, charset):
        if event.realm == 'ticket' and event.category != 'created':
            rows = self.env.db_query("""
                    SELECT messageid FROM messageid WHERE ticket=%s
                    """, (event.target.id,))
            if rows:
                msgid = rows[0][0]
                set_header(message, 'In-Reply-To', msgid, charset)
                set_header(message, 'References', msgid, charset)

    # IEnvironmentSetupParticipant method
    def environment_created(self):
        self.create_initial_database()

    # IEnvironmentSetupParticipant method
    def environment_needs_upgrade(self):
        dbm = DatabaseManager(self.env)
        return dbm.needs_upgrade(db_default.version, db_default.name)

    # IEnvironmentSetupParticipant method
    def upgrade_environment(self):
        dbm = DatabaseManager(self.env)
        if dbm.get_database_version(db_default.name) == 0:
            self.create_initial_database()

    def create_initial_database(self):
        dbm = DatabaseManager(self.env)
        dbm.create_tables(db_default.tables)
        dbm.set_database_version(db_default.version, db_default.name)
