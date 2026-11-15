"""Public synthetic acceptance checks using the pinned external engine only."""
import copy
import itertools
import json
import tempfile
import unittest
from pathlib import Path

import quillgrain
from quillgrain.compose import compile_context, reference
from quillgrain.contracts import verify_context
from quillgrain.export import export
from quillgrain.io import QGError, canonical, digest, read_json, sha, write_json

ROOT = Path(__file__).resolve().parents[1]
REGISTERS = ('conversational', 'essay', 'fiction_narration', 'maker_announcement')
SOCIAL = ('telegram', 'x', 'longform')


class Composition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = read_json(ROOT / 'voice.json')
        cls.previous = read_json(ROOT / 'releases/0.5.0/voice.json')

    def build(self, **kw):
        return compile_context(ROOT, language='ru', register=kw.pop('register', 'essay'),
                               public=True, **kw)

    def ids(self, context):
        return {r['id'] for r in context['rules_applied']}

    def child(self, folder, rules=(), permissions=None):
        p = {k: copy.deepcopy(self.pack[k]) for k in
             ('schema_version', 'visibility', 'status', 'languages', 'registers', 'permissions', 'compatibility')}
        p.update(id='synthetic.acceptance', version='1.0.0', extends=[reference(self.pack)],
                 rules=list(rules), examples=[], provenance=[])
        if permissions is not None:
            p['permissions'] = permissions
        write_json(folder / 'voice.json', p)
        return folder

    def child_build(self, folder, **kw):
        return compile_context(folder, bindings={self.pack['id']: ROOT}, language='ru',
                               register=kw.pop('register', 'essay'), public=True, **kw)

    def expect_error(self, code, fn):
        with self.assertRaises(QGError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def test_pin_lock_and_historical_identities(self):
        self.assertEqual(quillgrain.__version__, '0.1.0rc4')
        for version, identity in {
            '0.3.0': '0358afa6fa49bf2256d868c9653fee3e9672c6116e4b80d2310715ead2b06b0a',
            '0.4.2': 'b162511b1e0d6b637ef363dfc72692ac127b888cef6b3fbb2368c204af3ef8e5',
            '0.5.0': '300120ea193d4988f3b2b142043199b5e0e0c78555f8e03a049ae89ca80a15d6',
        }.items():
            folder = ROOT / 'releases' / version
            p, lock = read_json(folder / 'voice.json'), read_json(folder / 'quillgrain.lock.json')
            self.assertEqual(p['version'], version)
            self.assertEqual(lock['packs'], [reference(p)])
            self.assertEqual(digest(p), identity)
            for language, register in itertools.product(('ru', 'en'), REGISTERS):
                with self.subTest(version=version, language=language, register=register):
                    ctx, _ = compile_context(folder, language=language, register=register, public=True)
                    verify_context(ctx)
        self.assertEqual(read_json(ROOT / 'quillgrain.lock.json')['packs'], [reference(self.pack)])

    def test_all_eight_modes_select_only_current_default(self):
        for language, register in itertools.product(('ru', 'en'), REGISTERS):
            with self.subTest(language=language, register=register):
                ctx, _ = compile_context(ROOT, language=language, register=register, public=True)
                expected = f'common.{language}.{register}' + ('.v6' if language == 'ru' else '')
                self.assertEqual([e['id'] for e in ctx['examples_selected']], [expected])
                self.assertFalse(ctx['rules_omitted'])
                self.assertFalse(any(r['scope'].get('tags') for r in ctx['rules_applied']))
                self.assertLessEqual(ctx['budget']['used_codepoints'], 8000)
                verify_context(ctx)

    def test_rules_only_and_retirement(self):
        for register in REGISTERS:
            full, _ = self.build(register=register)
            ctx, _ = self.build(register=register, examples_mode='none')
            self.assertFalse(ctx['examples_selected'])
            self.assertEqual(ctx['rules_applied'], full['rules_applied'])
            retired = {e['id'] for e in self.pack['examples'] if e['status'] == 'RETIRED'}
            self.assertFalse(retired & {e['id'] for e in full['examples_selected']})
        ctx, _ = self.build(tags=['delivery.vivid', 'examples.common'])
        self.assertEqual([e['id'] for e in ctx['examples_selected']], ['common.ru.essay.v6'])

    def test_optional_layers_are_independent(self):
        base, _ = self.build()
        vivid, _ = self.build(tags=['delivery.vivid'])
        self.assertEqual(self.ids(vivid) - self.ids(base), {'common.ru.vivid'})
        for destination in SOCIAL:
            ctx, _ = self.build(tags=[f'social.{destination}'])
            self.assertEqual(self.ids(ctx) - self.ids(base), {f'common.emoji.{destination}'})
            combined, _ = self.build(tags=['delivery.vivid', f'social.{destination}'])
            self.assertEqual(self.ids(combined), self.ids(ctx) | {'common.ru.vivid'})

    def test_social_conflicts_only_when_scopes_intersect(self):
        selections = list(itertools.combinations(SOCIAL, 2)) + [SOCIAL]
        for language, register, destinations in itertools.product(('ru', 'en'), REGISTERS, selections):
            tags = [f'social.{x}' for x in destinations]
            with self.subTest(language=language, register=register, tags=tags):
                build = lambda: compile_context(ROOT, language=language, register=register, tags=tags, public=True)
                if register == 'fiction_narration':
                    ctx, _ = build()
                    self.assertFalse(any(x.startswith('common.emoji.') for x in self.ids(ctx)))
                else:
                    self.expect_error('RULE_CONFLICT', build)

    def test_soft_override_and_retained_stricter_author_policy(self):
        base, _ = self.build()
        target = next(r for r in self.pack['rules'] if r['id'] == 'common.publishable-language')
        for strict in (False, True):
            with self.subTest(strict=strict), tempfile.TemporaryDirectory() as tmp:
                r = copy.deepcopy(target)
                r.update(id='synthetic.language', overrides=[target['id']],
                         instruction='Use the language policy explicitly supplied in this fictional task.' if not strict
                         else 'Keep this fictional author response free of profanity and targeted insults.')
                if strict:
                    r.update(kind='constraint', required=True)
                folder = self.child(Path(tmp), [r])
                ctx, _ = self.child_build(folder)
                self.assertEqual(self.ids(ctx), (self.ids(base) - {target['id']}) | {r['id']})
                self.assertEqual(ctx['rules_overridden'], [{'id':target['id'], 'by':r['id']}])
                applied = next(x for x in ctx['rules_applied'] if x['id'] == r['id'])
                self.assertEqual(applied, r)

    def test_mandatory_override_and_permission_expansion_are_denied(self):
        for target_id in ('common.ru.source-boundary', 'common.ru.task-priority'):
            with tempfile.TemporaryDirectory() as tmp:
                r = copy.deepcopy(next(r for r in self.pack['rules'] if r['id'] == target_id))
                r.update(id='synthetic.illegal', kind='preference', required=False, overrides=[target_id])
                folder = self.child(Path(tmp), [r])
                self.expect_error('MANDATORY_CONFLICT', lambda:self.child_build(folder))
        with tempfile.TemporaryDirectory() as tmp:
            permissions = copy.deepcopy(self.pack['permissions'])
            permissions['approved_model_hosts'].append('unauthorized-synthetic-host')
            folder = self.child(Path(tmp), permissions=permissions)
            self.expect_error('PERMISSION_ESCALATION', lambda:self.child_build(folder))
        self.expect_error('HOST_OR_RETRIEVAL_DENIED', lambda:self.build(model_host='unauthorized-synthetic-host'))

    def test_override_scope_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = copy.deepcopy(next(r for r in self.pack['rules'] if r['id'] == 'common.ru.rhythm'))
            r.update(id='synthetic.wrong-scope', overrides=[r['id']])
            r['scope']['channel'] = 'dialogue'
            folder = self.child(Path(tmp), [r])
            self.expect_error('OVERRIDE_SCOPE_MISMATCH', lambda:self.child_build(folder))

    def test_narrator_and_character_scopes_survive_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = copy.deepcopy(next(r for r in self.pack['rules'] if r['id'] == 'common.ru.scene'))
            r.update(id='synthetic.character', scope={'languages':['ru'], 'registers':['fiction_narration'],
                                                     'channel':'dialogue', 'characters':['SyntheticReader']})
            folder = self.child(Path(tmp), [r])
            ctx, lock = self.child_build(folder, register='fiction_narration')
            self.assertEqual(next(x for x in ctx['rules_applied'] if x['id'] == 'common.ru.scene')['scope']['channel'], 'narration')
            export(ctx, lock, Path(tmp) / 'export')
            saved = read_json(Path(tmp) / 'export/context.json')
            self.assertEqual(next(x for x in saved['rules_applied'] if x['id'] == r['id'])['scope'], r['scope'])

    def test_explicit_alternative_pool_does_not_replace_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.child(Path(tmp))
            p = read_json(folder / 'voice.json')
            e = copy.deepcopy(next(x for x in self.pack['examples'] if x['id'] == 'common.ru.essay.v6'))
            e.update(id='synthetic.alternative', work_id='synthetic.alternative', tags=['examples.alternative'],
                     source_id='synthetic.original', text='Original synthetic alternative demonstration.')
            p['examples'] = [e]
            p['provenance'] = [{'id':'synthetic.original', 'kind':'synthetic_ai_prepared', 'note':'Original synthetic test data.'}]
            write_json(folder / 'voice.json', p)
            ctx, _ = self.child_build(folder, tags=['examples.alternative'], example_pool='examples.alternative')
            base, _ = self.build()
            self.assertEqual([x['id'] for x in ctx['examples_selected']], [e['id']])
            self.assertEqual(ctx['rules_applied'], base['rules_applied'])
            self.assertIn({'id':'common.ru.essay.v6', 'reason':'example_pool'}, ctx['examples_omitted'])
            self.expect_error('EXAMPLE_POOL_TAG_REQUIRED', lambda:self.child_build(folder, example_pool='examples.alternative'))

    def test_negative_is_opt_in_and_visibly_labelled(self):
        ctx, lock = self.build(register='maker_announcement', tags=['include_negative'])
        self.assertIn('common.ru.negative', {e['id'] for e in ctx['examples_selected']})
        negative = next(e for e in ctx['examples_selected'] if e['id'] == 'common.ru.negative')
        self.assertEqual(negative['role'], 'negative')
        self.assertIn('EXAMPLE DATA (negative;', ctx['prompt_payload'])
        with tempfile.TemporaryDirectory() as tmp:
            export(ctx, lock, Path(tmp) / 'export')
            self.assertIn('EXAMPLE DATA (negative;', (Path(tmp) / 'export/VOICE_CONTEXT.md').read_text(encoding='utf-8'))

    def test_budget_omits_whole_elements_and_protects_mandatory(self):
        full, _ = self.build(max_chars=100000)
        example = full['examples_selected'][0]
        smaller, _ = self.build(max_chars=full['budget']['used_codepoints'] - 1)
        self.assertFalse(smaller['examples_selected'])
        self.assertIn({'id':example['id'], 'reason':'budget'}, smaller['examples_omitted'])
        for rule in smaller['rules_applied']:
            self.assertIn(rule['instruction'], smaller['prompt_payload'])
        self.expect_error('BUDGET_EXCEEDED', lambda:self.build(max_chars=1))
        for language, register in itertools.product(('ru','en'), REGISTERS):
            with self.subTest(language=language, register=register):
                if language == 'ru':
                    # Required RU source/task rules may exceed the legacy cap; never truncate them.
                    try:
                        ctx, _ = compile_context(ROOT, language=language, register=register, target='patchpitch-legacy', public=True)
                    except QGError as e:
                        self.assertEqual(e.code, 'BUDGET_EXCEEDED')
                        continue
                else:
                    ctx, _ = compile_context(ROOT, language=language, register=register, target='patchpitch-legacy', public=True)
                self.assertLessEqual(len(ctx['prompt_payload']), 1200)
                self.assertTrue(ctx['rules_omitted'] or ctx['examples_omitted'])

    def test_deterministic_context_lock_and_export(self):
        for target in ('chatgpt','codex','patchpitch','patchpitch-legacy'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                opts = dict(target=target, language='en' if target == 'patchpitch-legacy' else 'ru', register='essay', public=True)
                first, lock = compile_context(ROOT, **opts)
                second, second_lock = compile_context(ROOT, **opts)
                self.assertEqual(canonical(first), canonical(second))
                self.assertEqual(canonical(lock), canonical(second_lock))
                for name in ('one','two'):
                    export(first, lock, Path(tmp) / name)
                a = {str(p.relative_to(Path(tmp)/'one')):sha(p.read_bytes()) for p in (Path(tmp)/'one').rglob('*') if p.is_file()}
                b = {str(p.relative_to(Path(tmp)/'two')):sha(p.read_bytes()) for p in (Path(tmp)/'two').rglob('*') if p.is_file()}
                self.assertEqual(a,b)
                verify_context(read_json(Path(tmp)/'one/context.json'))

    def test_english_and_override_contracts_are_retained(self):
        old_rules = {r['id']:r for r in self.previous['rules']}
        self.assertEqual(set(old_rules), {r['id'] for r in self.pack['rules']})
        for rule in self.pack['rules']:
            old = old_rules[rule['id']]
            for field in ('scope','kind','required','priority','enforcement'):
                self.assertEqual(rule.get(field), old.get(field), (rule['id'],field))
            if 'en' in rule['scope'].get('languages', []):
                self.assertEqual(rule['instruction'], old['instruction'])
        self.assertEqual([e for e in self.pack['examples'] if e['language']=='en'],
                         [e for e in self.previous['examples'] if e['language']=='en'])
        for register in REGISTERS:
            before, _ = compile_context(ROOT/'releases/0.5.0', language='en', register=register, public=True)
            after, _ = compile_context(ROOT, language='en', register=register, public=True)
            self.assertEqual(before['prompt_payload'], after['prompt_payload'])

    def test_provenance_and_example_mirrors_agree(self):
        journal = [json.loads(line) for line in (ROOT/'provenance/examples.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(journal),len(self.pack['examples']))
        self.assertEqual(len({e['id'] for e in journal}),len(journal))
        for e in self.pack['examples']:
            entry = next(x for x in journal if x['id']==e['id'])
            for k in ('status','source_id','authorship'):
                self.assertEqual(entry[k],e[k])
            self.assertEqual(e['authorship'],'synthetic_ai_prepared')
            if e['id'].endswith('.v6'):
                mirror = (ROOT/f"examples/ru/{e['register']}-v6.md").read_text(encoding='utf-8')
                self.assertIn(e['before'],mirror)
                self.assertIn(e['text'],mirror)
                self.assertTrue(entry['scenario_is_fictional'])
        self.assertFalse(self.pack.get('corpus_dependencies'))
        self.assertFalse(self.pack.get('example_refs'))
        self.assertEqual(self.pack['extends'],[])

    def test_contrast_pairs_have_semantic_expectations_not_gold_sentences(self):
        data = read_json(ROOT/'tests/fixtures/contrasts-0.6.json')
        self.assertEqual(data['authorship'],'synthetic_ai_prepared')
        families = {case['family'] for case in data['cases']}
        self.assertEqual(len(families),9)
        self.assertEqual(len(data['cases']),24)
        self.assertEqual(len({c['id'] for c in data['cases']}),len(data['cases']))
        for family in families:
            cases = [c for c in data['cases'] if c['family']==family]
            self.assertEqual({c['action'] for c in cases},{'edit','preserve'})
            self.assertTrue(all(c['expected_properties'] and c['allowed_variation'] and c['brief'] for c in cases))
            self.assertTrue(all(c['register'] in REGISTERS for c in cases))
        reader = [c for c in data['cases'] if c['family']=='reader']
        self.assertEqual(len({c['fact_packet'] for c in reader}),1)


if __name__ == '__main__':
    unittest.main()
