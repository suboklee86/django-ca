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
import os

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.serialization import PrivateFormat

from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.utils import six

from ... import ca_settings
from ...models import CertificateAuthority
from ...utils import ca_storage
from ...utils import wrap_file_exceptions
from ..base import BaseCommand
from ..base import CertificateAuthorityDetailMixin
from ..base import PasswordAction

if six.PY2:  # pragma: no branch, pragma: only py2
    from ...utils import PermissionError


class Command(BaseCommand, CertificateAuthorityDetailMixin):
    help = """Import an existing certificate authority.

Note that the private key will be copied to the directory configured by the CA_DIR setting."""

    def add_arguments(self, parser):
        self.add_ca(parser, '--parent',
                    help='''Make the CA an intermediate CA of the named CA. By default, this is a
                    new root CA.''', no_default=True)
        self.add_password(
            parser, help='Password used to encrypt the private key. Pass no argument to be prompted.')
        parser.add_argument('--import-password', nargs='?', action=PasswordAction, metavar='PASSWORD',
                            prompt='Password to import CA: ',
                            help='Password for the private key.')

        self.add_ca_args(parser)

        parser.add_argument('name', help='Human-readable name of the CA')
        parser.add_argument('key', help='Path to the private key (PEM or DER format).',
                            type=argparse.FileType('rb'))
        parser.add_argument('pem', help='Path to the public key (PEM or DER format).',
                            type=argparse.FileType('rb'))

    def handle(self, name, key, pem, **options):
        if not os.path.exists(ca_settings.CA_DIR):
            try:
                with wrap_file_exceptions():
                    os.makedirs(ca_settings.CA_DIR)
            except PermissionError:
                pem.close()
                key.close()
                raise CommandError('%s: Could not create CA_DIR: Permission denied.' % ca_settings.CA_DIR)
            # FileNotFoundError shouldn't happen, whole point of this block is to create it

        password = options['password']
        import_password = options['import_password']
        parent = options['parent']
        pem_data = pem.read()
        key_data = key.read()
        crl_url = '\n'.join(options['crl_url'])

        # close reader objects (otherwise we get a ResourceWarning)
        key.close()
        pem.close()

        ca = CertificateAuthority(name=name, parent=parent, issuer_url=options['issuer_url'],
                                  issuer_alt_name=options['issuer_alt_name'], crl_url=crl_url)

        # load public key
        try:
            pem_loaded = x509.load_pem_x509_certificate(pem_data, default_backend())
        except Exception:
            try:
                pem_loaded = x509.load_der_x509_certificate(pem_data, default_backend())
            except Exception:
                raise CommandError('Unable to load public key.')
        ca.x509 = pem_loaded
        ca.private_key_path = ca_storage.generate_filename('%s.key' % ca.serial.replace(':', ''))

        # load private key
        try:
            key_loaded = serialization.load_pem_private_key(key_data, import_password, default_backend())
        except Exception:
            try:
                key_loaded = serialization.load_der_private_key(key_data, import_password, default_backend())
            except Exception:
                raise CommandError('Unable to load private key.')

        if password is None:
            encryption = serialization.NoEncryption()
        else:
            encryption = serialization.BestAvailableEncryption(password)

        # write private key to file
        pem = key_loaded.private_bytes(encoding=Encoding.PEM,
                                       format=PrivateFormat.TraditionalOpenSSL,
                                       encryption_algorithm=encryption)

        perm_denied = '%s: Permission denied: Could not open file for writing' % ca.private_key_path

        try:
            with wrap_file_exceptions():
                ca_storage.save(ca.private_key_path, ContentFile(pem))
        except PermissionError:
            raise CommandError(perm_denied)

        # Only save CA to database if we loaded all data and copied private key
        ca.save()
