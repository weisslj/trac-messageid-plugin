# trac-messageid-plugin

This plugin for Trac >= 1.1.3 stores the Message-ID of ticket notifications in
a new database table, so they can be used for the In-Reply-To header of
subsequent messages.

This is necessary when using Amazon's Simple Email Service (AWS SES),
because it rewrites the message id. It is also useful when changing the
project URL or sender domain (otherwise replies will end up in a new thread).

It is a drop-in replacement for the native SmtpEmailSender component.

## Installation

Deploy to a specific Trac environment:

    cd /path/to/pluginsource
    python setup.py bdist_egg
    cp dist/*.egg /path/to/projenv/plugins

Or install globally:

    cd /path/to/pluginsource
    python setup.py install

Enable plugin in trac.ini:

    [components]
    tracmessageid.* = enabled

    [notification]
    email_sender = MessageIdSmtpEmailSender

Upgrade the database:

    trac-admin /path/to/env upgrade
