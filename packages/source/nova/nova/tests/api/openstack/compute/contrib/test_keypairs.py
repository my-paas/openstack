# Copyright 2011 Eldar Nugaev
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from lxml import etree
import webob

from nova.api.openstack.compute.contrib import keypairs
from nova.api.openstack import wsgi
from nova import db
from nova import exception
from nova.openstack.common import jsonutils
from nova import quota
from nova import test
from nova.tests.api.openstack import fakes


QUOTAS = quota.QUOTAS


def fake_keypair(name):
    return {'public_key': 'FAKE_KEY',
            'fingerprint': 'FAKE_FINGERPRINT',
            'name': name}


def db_key_pair_get_all_by_user(self, user_id):
    return [fake_keypair('FAKE')]


def db_key_pair_create(self, keypair):
    pass


def db_key_pair_destroy(context, user_id, name):
    if not (user_id and name):
        raise Exception()


def db_key_pair_get(context, user_id, name):
    pass


class KeypairsTest(test.TestCase):

    def setUp(self):
        super(KeypairsTest, self).setUp()
        self.Controller = keypairs.Controller()
        fakes.stub_out_networking(self.stubs)
        fakes.stub_out_rate_limiting(self.stubs)

        self.stubs.Set(db, "key_pair_get_all_by_user",
                       db_key_pair_get_all_by_user)
        self.stubs.Set(db, "key_pair_create",
                       db_key_pair_create)
        self.stubs.Set(db, "key_pair_destroy",
                       db_key_pair_destroy)
        self.flags(
            osapi_compute_extension=[
                'nova.api.openstack.compute.contrib.select_extensions'],
            osapi_compute_ext_list=['Keypairs'])
        self.app = fakes.wsgi_app(init_only=('os-keypairs',))

    def test_keypair_list(self):
        req = webob.Request.blank('/v2/fake/os-keypairs')
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 200)
        res_dict = jsonutils.loads(res.body)
        response = {'keypairs': [{'keypair': fake_keypair('FAKE')}]}
        self.assertEqual(res_dict, response)

    def test_keypair_create(self):
        body = {'keypair': {'name': 'create_test'}}
        req = webob.Request.blank('/v2/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 200)
        res_dict = jsonutils.loads(res.body)
        self.assertTrue(len(res_dict['keypair']['fingerprint']) > 0)
        self.assertTrue(len(res_dict['keypair']['private_key']) > 0)

    def test_keypair_create_with_empty_name(self):
        body = {'keypair': {'name': ''}}
        req = webob.Request.blank('/v2/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 400)

    def test_keypair_create_with_invalid_name(self):
        body = {
            'keypair': {
                'name': 'a' * 256
            }
        }
        req = webob.Request.blank('/v2/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 400)

    def test_keypair_create_with_non_alphanumeric_name(self):
        body = {
            'keypair': {
                'name': 'test/keypair'
            }
        }
        req = webob.Request.blank('/v2/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        res_dict = jsonutils.loads(res.body)
        self.assertEqual(res.status_int, 400)

    def test_keypair_import(self):
        body = {
            'keypair': {
                'name': 'create_test',
                'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDBYIznA'
                              'x9D7118Q1VKGpXy2HDiKyUTM8XcUuhQpo0srqb9rboUp4'
                              'a9NmCwpWpeElDLuva707GOUnfaBAvHBwsRXyxHJjRaI6Y'
                              'Qj2oLJwqvaSaWUbyT1vtryRqy6J3TecN0WINY71f4uymi'
                              'MZP0wby4bKBcYnac8KiCIlvkEl0ETjkOGUq8OyWRmn7lj'
                              'j5SESEUdBP0JnuTFKddWTU/wD6wydeJaUhBTqOlHn0kX1'
                              'GyqoNTE1UEhcM5ZRWgfUZfTjVyDF2kGj3vJLCJtJ8LoGc'
                              'j7YaN4uPg1rBle+izwE/tLonRrds+cev8p6krSSrxWOwB'
                              'bHkXa6OciiJDvkRzJXzf',
            },
        }

        req = webob.Request.blank('/v2/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 200)
        # FIXME(ja): sholud we check that public_key was sent to create?
        res_dict = jsonutils.loads(res.body)
        self.assertTrue(len(res_dict['keypair']['fingerprint']) > 0)
        self.assertFalse('private_key' in res_dict['keypair'])

    def test_keypair_import_quota_limit(self):

        def fake_quotas_count(self, context, resource, *args, **kwargs):
            return 100

        self.stubs.Set(QUOTAS, "count", fake_quotas_count)

        body = {
            'keypair': {
                'name': 'create_test',
                'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDBYIznA'
                              'x9D7118Q1VKGpXy2HDiKyUTM8XcUuhQpo0srqb9rboUp4'
                              'a9NmCwpWpeElDLuva707GOUnfaBAvHBwsRXyxHJjRaI6Y'
                              'Qj2oLJwqvaSaWUbyT1vtryRqy6J3TecN0WINY71f4uymi'
                              'MZP0wby4bKBcYnac8KiCIlvkEl0ETjkOGUq8OyWRmn7lj'
                              'j5SESEUdBP0JnuTFKddWTU/wD6wydeJaUhBTqOlHn0kX1'
                              'GyqoNTE1UEhcM5ZRWgfUZfTjVyDF2kGj3vJLCJtJ8LoGc'
                              'j7YaN4uPg1rBle+izwE/tLonRrds+cev8p6krSSrxWOwB'
                              'bHkXa6OciiJDvkRzJXzf',
            },
        }

        req = webob.Request.blank('/v2/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 413)

    def test_keypair_create_quota_limit(self):

        def fake_quotas_count(self, context, resource, *args, **kwargs):
            return 100

        self.stubs.Set(QUOTAS, "count", fake_quotas_count)

        body = {
            'keypair': {
                'name': 'create_test',
            },
        }

        req = webob.Request.blank('/v2/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 413)

    def test_keypair_create_duplicate(self):
        self.stubs.Set(db, "key_pair_get", db_key_pair_get)
        body = {'keypair': {'name': 'create_duplicate'}}
        req = webob.Request.blank('/v2/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 409)

    def test_keypair_import_bad_key(self):
        body = {
            'keypair': {
                'name': 'create_test',
                'public_key': 'ssh-what negative',
            },
        }

        req = webob.Request.blank('/v2/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 400)

    def test_keypair_delete(self):
        req = webob.Request.blank('/v2/fake/os-keypairs/FAKE')
        req.method = 'DELETE'
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 202)

    def test_keypair_get_keypair_not_found(self):
        req = webob.Request.blank('/v2/fake/os-keypairs/DOESNOTEXIST')
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 404)

    def test_keypair_delete_not_found(self):

        def db_key_pair_get_not_found(context, user_id, name):
            raise exception.KeypairNotFound(user_id=user_id, name=name)

        self.stubs.Set(db, "key_pair_get",
                       db_key_pair_get_not_found)
        req = webob.Request.blank('/v2/fake/os-keypairs/WHAT')
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 404)

    def test_keypair_show(self):

        def _db_key_pair_get(context, user_id, name):
            return {'name': 'foo', 'public_key': 'XXX', 'fingerprint': 'YYY'}

        self.stubs.Set(db, "key_pair_get", _db_key_pair_get)

        req = webob.Request.blank('/v2/fake/os-keypairs/FAKE')
        req.method = 'GET'
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        res_dict = jsonutils.loads(res.body)
        self.assertEqual(res.status_int, 200)
        self.assertEqual('foo', res_dict['keypair']['name'])
        self.assertEqual('XXX', res_dict['keypair']['public_key'])
        self.assertEqual('YYY', res_dict['keypair']['fingerprint'])

    def test_keypair_show_not_found(self):

        def _db_key_pair_get(context, user_id, name):
            raise exception.KeypairNotFound(user_id=user_id, name=name)

        self.stubs.Set(db, "key_pair_get", _db_key_pair_get)

        req = webob.Request.blank('/v2/fake/os-keypairs/FAKE')
        req.method = 'GET'
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        self.assertEqual(res.status_int, 404)

    def test_show_server(self):
        self.stubs.Set(db, 'instance_get',
                        fakes.fake_instance_get())
        req = webob.Request.blank('/v2/fake/servers/1')
        req.headers['Content-Type'] = 'application/json'
        response = req.get_response(fakes.wsgi_app(init_only=('servers',)))
        self.assertEquals(response.status_int, 200)
        res_dict = jsonutils.loads(response.body)
        self.assertTrue('key_name' in res_dict['server'])
        self.assertEquals(res_dict['server']['key_name'], '')

    def test_detail_servers(self):
        self.stubs.Set(db, 'instance_get_all_by_filters',
                        fakes.fake_instance_get_all_by_filters())
        req = fakes.HTTPRequest.blank('/v2/fake/servers/detail')
        res = req.get_response(fakes.wsgi_app(init_only=('servers',)))
        server_dicts = jsonutils.loads(res.body)['servers']
        self.assertEquals(len(server_dicts), 5)

        for server_dict in server_dicts:
            self.assertTrue('key_name' in server_dict)
            self.assertEquals(server_dict['key_name'], '')

    def test_keypair_create_with_invalid_keypairBody(self):
        body = {'alpha': {'name': 'create_test'}}
        req = webob.Request.blank('/v1.1/fake/os-keypairs')
        req.method = 'POST'
        req.body = jsonutils.dumps(body)
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(self.app)
        res_dict = jsonutils.loads(res.body)
        self.assertEqual(res.status_int, 400)
        self.assertEqual(res_dict['badRequest']['message'],
                         "Invalid request body")


class KeypairsXMLSerializerTest(test.TestCase):
    def setUp(self):
        super(KeypairsXMLSerializerTest, self).setUp()
        self.deserializer = wsgi.XMLDeserializer()

    def test_default_serializer(self):
        exemplar = dict(keypair=dict(
                public_key='fake_public_key',
                private_key='fake_private_key',
                fingerprint='fake_fingerprint',
                user_id='fake_user_id',
                name='fake_key_name'))
        serializer = keypairs.KeypairTemplate()
        text = serializer.serialize(exemplar)

        tree = etree.fromstring(text)

        self.assertEqual('keypair', tree.tag)
        for child in tree:
            self.assertTrue(child.tag in exemplar['keypair'])
            self.assertEqual(child.text, exemplar['keypair'][child.tag])

    def test_index_serializer(self):
        exemplar = dict(keypairs=[
                dict(keypair=dict(
                        name='key1_name',
                        public_key='key1_key',
                        fingerprint='key1_fingerprint')),
                dict(keypair=dict(
                        name='key2_name',
                        public_key='key2_key',
                        fingerprint='key2_fingerprint'))])
        serializer = keypairs.KeypairsTemplate()
        text = serializer.serialize(exemplar)

        tree = etree.fromstring(text)

        self.assertEqual('keypairs', tree.tag)
        self.assertEqual(len(exemplar['keypairs']), len(tree))
        for idx, keypair in enumerate(tree):
            self.assertEqual('keypair', keypair.tag)
            kp_data = exemplar['keypairs'][idx]['keypair']
            for child in keypair:
                self.assertTrue(child.tag in kp_data)
                self.assertEqual(child.text, kp_data[child.tag])

    def test_deserializer(self):
        exemplar = dict(keypair=dict(
                name='key_name',
                public_key='public_key'))
        intext = ("<?xml version='1.0' encoding='UTF-8'?>\n"
                  '<keypair><name>key_name</name>'
                  '<public_key>public_key</public_key></keypair>')

        result = self.deserializer.deserialize(intext)['body']
        self.assertEqual(result, exemplar)
