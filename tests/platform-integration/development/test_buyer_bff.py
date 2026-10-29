"""Closed source boundaries only; never native HTTP acceptance evidence."""
from contextlib import nullcontext
from copy import deepcopy
import importlib.util
import io
import base64
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

import adapter
import buyer_bff
import buyer_bff_contract as c
import dev


class BuyerBffTests(unittest.TestCase):
    def test_login_driver_reaches_http_with_a_real_cookie_jar(self):
        spec = importlib.util.spec_from_file_location('_buyer_bff_driver_test', Path(__file__).with_name('buyer_bff_probe.py'))
        module = importlib.util.module_from_spec(spec)
        with patch('ssl.create_default_context', return_value=SimpleNamespace()), \
             patch.dict(sys.modules, {'buyer_identity_probe': SimpleNamespace(client_auth=Mock())}):
            spec.loader.exec_module(module)
        # Stop at the transport boundary: this is a source regression, not
        # fabricated native login or qualification evidence.
        with patch.object(module, 'stage'), patch.object(module, 'http', side_effect=RuntimeError('transport boundary')) as request:
            with self.assertRaisesRegex(RuntimeError, 'transport boundary'):
                module.login()
        request.assert_called_once()
        self.assertEqual(request.call_args.args[:2], ('POST', '/api/iam/login'))
        self.assertIsNotNone(request.call_args.kwargs['opener'])

    def test_internal_build_stages_keep_external_base_digest_enforcement(self):
        base = 'node@sha256:' + 'a'*64
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Dockerfile'
            path.write_text('FROM ' + base + ' AS dependencies\nFROM dependencies AS build\n')
            dev.check_dockerfile(path)
            for source in ('FROM node:latest AS build\n',
                           'FROM future AS build\nFROM '+base+' AS future\n',
                           'FROM '+base+' AS dependencies\nFROM node:24 AS runtime\n'):
                path.write_text(source)
                with self.assertRaises(dev.Refused): dev.check_dockerfile(path)
    def authorization(self, **change):
        query = dict(client_id=c.BFF, response_type='code', redirect_uri=c.CALLBACK,
            scope='openid trade:buy', audience='baobab-trade', code_challenge_method='S256',
            state='a'*43, nonce='b'*43, code_challenge='c'*43)
        query.update(change)
        return 'https://hydra.int03.test/oauth2/auth?' + urlencode(query)

    def test_actual_bff_request_is_preserved_and_not_replaced_by_a_driver_verifier(self):
        self.assertEqual(c.authorization(self.authorization()), 'a'*43)
        for change in ({'client_id': 'foreign'}, {'redirect_uri': 'https://attacker.test/callback'},
                       {'scope': 'openid trade:buy admin'}, {'audience': 'baobab-control-plane'},
                       {'state': 'short'}, {'nonce': ''}, {'code_challenge': 'short'},
                       {'code_challenge_method': 'plain'}, {'extra': 'unregistered'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                c.authorization(self.authorization(**change))
        for value in (self.authorization() + '&state=second', self.authorization() + '#fragment',
                      self.authorization().replace('hydra.int03.test', 'evil.test'), None):
            with self.assertRaises(ValueError): c.authorization(value)

    def test_private_component_cannot_claim_host_or_protected_acceptance(self):
        sources = {name: 'b'*40 for name in c.SOURCES}; run = 'a'*32
        value = c.fresh(run, sources)
        self.assertIs(c.validate(value, run, sources), value)
        for change in ({'bff_http_qualified': True}, {'int05_qualified': True},
                       {'production_authorized': True}, {'private_token': 'not-evidence'},
                       {'run_id': 'c'*32}, {'checks': []}):
            with self.assertRaises(ValueError): c.validate({**value, **change}, run, sources)
        bad = deepcopy(value); bad['checks']['native-next-iam-session'] = 'true'
        with self.assertRaises(ValueError): c.validate(bad, run, sources)

    def test_new_transport_is_opt_in_and_cannot_broaden_baseline_probe(self):
        state = {'run_id': 'a'*32, 'project': 'dev01-'+'a'*32, 'uid': 1000, 'gid': 1000,
                 'deadline': 1, 'secrets': {'cp_db': 'x', 'iam_db': 'x', 'hook': 'x',
                 'introspection': 'x', 'verifier': 'x'}, 'images': {'cp': 'sha256:'+'a'*64}}
        images = dev.load_lock()['images']; directory = Path('/private')
        base = adapter.composition(state, directory, images, 'test')
        self.assertNotIn('DEV07_BFF_HTTP_PROFILE', base['services']['probe']['environment'])
        with self.assertRaises(ValueError):
            adapter.composition({**state, 'buyer_bff_http_profile': True}, directory, images, 'test')
        current = adapter.composition({**state, 'buyer_identity_profile': True,
            'buyer_bff_http_profile': True}, directory, images, 'test')
        self.assertEqual(current['services']['probe']['environment']['DEV07_BFF_HTTP_PROFILE'], 'true')
        self.assertEqual(set(current['services']), set(base['services']))

    def test_host_cleanup_is_attempted_even_if_lease_or_provider_lookup_failed(self):
        with patch.object(dev, 'guarded', side_effect=lambda *_: nullcontext()), \
             patch.object(dev, 'current', side_effect=dev.Refused('LEASE_EXPIRED')), \
             patch.object(dev, 'down') as down:
            self.assertTrue(buyer_bff.cleanup('a'*32))
            down.assert_called_once_with('a'*32)

    def relay(self, body, *, name=c.BFF, secret='own-secret', enabled=True):
        spec = importlib.util.spec_from_file_location('_buyer_bff_native_test', Path(__file__).with_name('native_probe.py'))
        module = importlib.util.module_from_spec(spec)
        with patch('ssl.create_default_context', return_value=SimpleNamespace()):
            spec.loader.exec_module(module)
        handler = object.__new__(module.Hook)
        raw = urlencode({'token': 'private-synthetic-token'}).encode()
        handler.headers = {'Content-Length': str(len(raw)), 'Authorization': 'Basic ' + base64.b64encode((name+':'+secret).encode()).decode()}
        handler.rfile = io.BytesIO(raw); handler.wfile = io.BytesIO()
        handler.send_response = Mock(); handler.send_header = Mock(); handler.end_headers = Mock()
        native = {'clients': {c.BFF: {'secret': 'own-secret'}}}
        request = Mock(return_value=(200, body, None))
        with patch.dict(os.environ, {'DEV07_BFF_HTTP_PROFILE': 'true' if enabled else 'false', 'DEV05_PROFILE': ''}), \
             patch.object(module, 'read', side_effect=lambda path: native if path == 'native.json' else {'buyer_bff_http_profile': True}), \
             patch.object(module, 'request', request):
            handler.introspect()
        return handler.send_response.call_args.args[0], handler.wfile.getvalue(), request

    def test_introspection_is_actual_issuer_readback_for_own_client_only(self):
        original = {'active': True, 'client_id': c.BFF, 'iss': 'https://hydra.int03.test', 'sub': 'synthetic-human'}
        status, raw, request = self.relay(original)
        self.assertEqual(status, 200); self.assertEqual(json.loads(raw), original)
        self.assertEqual(request.call_args.args[:2], ('POST', 'http://hydra:4445/admin/oauth2/introspect'))
        status, raw, _ = self.relay({**original, 'client_id': 'foreign'})
        self.assertEqual(status, 401); self.assertNotIn(b'foreign', raw)
        status, raw, _ = self.relay({'active': False})
        self.assertEqual(status, 200); self.assertEqual(json.loads(raw), {'active': False})
        for change in ({'secret': 'wrong'}, {'enabled': False}, {'name': 'foreign'}):
            status, _, request = self.relay(original, **change)
            self.assertEqual(status, 401); request.assert_not_called()


if __name__ == '__main__': unittest.main()
