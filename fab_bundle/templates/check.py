#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import smtplib
import subprocess

TO = '{{ admin }}'
FROM = '{{ email.from }}'
SMTP_HOST = '{{ email.host }}'
SMTP_PORT = {{ email.port }}
SMTP_USERNAME = '{{ email.user }}'
SMTP_PASSWORD = '{{ email.password }}'
SERVER_NAME = '{{ host_string }}'


def run(command):
    """
    Runs a command.
    Returns stdout if sucess, stderr if failure.
    """
    result = subprocess.Popen(command, shell=True,
                              stdout=subprocess.PIPE)
    out, err = result.communicate()
    if err is not None:
        return err
    return out


def status_check():
    """
    Runs a series of checks and send some stats to the admins.
    """
    run('apt-get update')

    disks = run('df -h|grep -E "^(/dev|File)"').replace("\n", "\n    ")
    disks = "    " + disks

    context = {
        'packages': run('apt-get upgrade -sV | grep -E "^ "'),
        'disks': disks,
        'uptime': run('uptime'),
    }
    message = EMAIL_TEMPLATE % context

    date = datetime.date.today() - datetime.timedelta(days=1)
    subject = '%s daily run output - %s' % (SERVER_NAME,
                                            date.strftime("%Y-%m-%d"))
    head = (FROM, TO, subject)
    headers = "From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n" % head

    message = headers + message
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    server.sendmail(FROM, TO, message)
    server.quit()


EMAIL_TEMPLATE = """System status
-------------

    %(uptime)s
Disk space
----------

Mount points:
%(disks)s
Out-of-date packages
--------------------

%(packages)s"""


if __name__ == '__main__':
    status_check()
