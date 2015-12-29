# -*- coding: utf-8 -*-
#
# This file is part of django-ca (https://github.com/mathiasertl/django-ca).
#
# django-ca is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# django-ca is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with django-ca.  If not,
# see <http://www.gnu.org/licenses/>.

import argparse

from OpenSSL import crypto


from django.core.management.base import BaseCommand as _BaseCommand
from django.core.management.base import CommandError

from django_ca.models import Certificate


class FormatAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        value = value.strip().upper()
        if value == 'DER':
            value = 'ASN1'
        try:
            value = getattr(crypto, 'FILETYPE_%s' % value)
        except AttributeError:
            parser.error('Unknown format "%s".' % value)
        setattr(namespace, self.dest, value)


format_parser = argparse.ArgumentParser(add_help=False)
format_parser.add_argument(
    '-f', '--format', metavar='{PEM,ASN1,DER,TEXT}',
    default=crypto.FILETYPE_PEM, action=FormatAction,
    help='The format to use, default is PEM.')


class BaseCommand(_BaseCommand):
    certificate_queryset = Certificate.objects.filter(revoked=False)
    parents = []

    def add_parents(self, parser):
        for parent in self.parents:
            parser._add_container_actions(parent)
            try:
                defaults = parent._defaults
            except AttributeError:
                pass
            else:
                parser._defaults.update(defaults)

    def add_arguments(self, parser):
        self.add_parents(parser)
        super(BaseCommand, self).add_arguments(parser)

    def get_certificate(self, id):
        try:
            return self.certificate_queryset.get_by_serial_or_cn(id)
        except Certificate.DoesNotExist:
            raise CommandError('No valid certificate with CommonName/serial "%s" exists.' % id)
        except Certificate.MultipleObjectsReturned:
            raise CommandError('Multiple valid certificates with CommonName "%s" found.' % id)


class CertCommand(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'cert',
            help='''Certificate by CommonName or serial. If you give a CommonName (which is not by
                definition unique) there must be only one valid certificate with the given
                CommonName.''')
        super(CertCommand, self).add_arguments(parser)
