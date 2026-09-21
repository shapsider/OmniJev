"""Contract tests for real model integration, not simulated success tests."""
import base64
import json
from unittest.mock import Mock

import httpx
import pytest
from embodied_jev.policies import DecisionPolicy
from omnijev.embodied_policy import final_choice


def response(letter='A', tokens=3, finish='stop', probs=None, reasoning=''):
    return httpx.Response(200, request=httpx.Request('POST','http://localhost/v1/chat/completions'), json={
        'model':'test-model','usage':{'prompt_tokens':100,'completion_tokens':tokens,'total_tokens':100+tokens},
        'choices':[{'finish_reason':finish,'message':{'content':letter,'reasoning_content':reasoning},
                    'logprobs':{'content':[{'token':'A','logprob':-.5,'top_logprobs':probs or []}]}}]})


def test_fast_direct_use_identical_evidence_and_budgets():
    payloads=[]
    for provider in ('omnijev','omni_direct'):
        policy=DecisionPolicy(provider)
        policy._post=Mock(return_value=response())
        answer=policy.choose({'tcp':[0,0,0]},'Choose',{'hold':'stay','move':'advance'},'move',[])
        assert answer['choice']=='hold'  # Never take the supplied rule default.
        payloads.append(policy._post.call_args.kwargs['json'])
        assert policy.calls==1 and policy.tokens==100 and policy.output_tokens==3
    assert payloads[0]['messages']==payloads[1]['messages']
    assert payloads[0]['max_tokens']==payloads[1]['max_tokens']==4
    assert payloads[0]['logprobs'] is True and 'logprobs' not in payloads[1]


def test_invalid_and_truncated_preserve_cost_without_rule_fallback():
    for result in (response('Z'),response('A',4096,'length')):
        policy=DecisionPolicy('omni_reasoning');policy._post=Mock(return_value=result)
        with pytest.raises(ValueError):policy.choose({},'Choose',{'hold':'stay','move':'advance'},'move',[])
        assert policy.calls==1 and policy.tokens==100
        assert policy.omni_records[0]['status']=='error' and len(policy.latencies)==1


def test_unexpected_thinking_is_rejected_in_fast_path():
    policy=DecisionPolicy('omnijev');policy._post=Mock(return_value=response(reasoning='unexpected thought'))
    with pytest.raises(ValueError):policy.choose({},'Choose',{'hold':'stay','move':'advance'},'move',[])


def test_21_actions_do_not_fabricate_candidate_probabilities():
    policy=DecisionPolicy('omnijev');policy._post=Mock(return_value=response())
    choices={f'motor{i}':f'action {i}' for i in range(21)}
    answer=policy.choose_plan({},'Choose',choices)
    assert answer['choice']=='motor0' and answer['probabilities']=={}
    assert answer['selected_probability'] is None and answer['score_status']=='incomplete_top_k'


def test_native_camera_bytes_and_provenance_are_preserved():
    policy=DecisionPolicy('omnijev');policy._post=Mock(return_value=response())
    png=b'\x89PNG\r\n\x1a\nactual-test-frame'
    answer=policy.choose_plan({'proprioception':[0,0,0]},'Choose',{'hold':'stay','move':'advance'},
        image=[{'rgb':png,'view':'external','capture_id':1},{'rgb':png,'view':'wrist','capture_id':1}])
    payload=policy._post.call_args.kwargs['json'];images=payload['messages'][1]['content'][:2]
    assert all(base64.b64decode(i['image_url']['url'].split(',')[1])==png for i in images)
    assert answer['image_count']==2 and len(policy.last_input['images'])==2
    assert 'data:image' not in json.dumps(policy.last_input)


def test_adaptive_counts_both_real_requests(monkeypatch):
    monkeypatch.setenv('OMNIJEV_MARGIN','.2')
    policy=DecisionPolicy('omni_adaptive');policy._post=Mock(side_effect=[response(),response('B',17,reasoning='thinking')])
    answer=policy.choose({},'Choose',{'hold':'stay','move':'advance'},'hold',[])
    assert answer['choice']=='move' and answer['route']=='fast_then_reasoning'
    assert policy.calls==2 and policy.tokens==200 and policy.output_tokens==20
    assert len(policy.omni_records)==2 and answer['selected_probability'] is None


def test_final_answer_parser_never_mines_explanatory_text():
    assert final_choice('Reasoning says A but maybe B', ['A','B']) is None
    assert final_choice('Explanation\nFinal answer: B', ['A','B'])=='B'


def test_dashboard_routes_and_artifact_path_boundary(monkeypatch,tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from omnijev import embodied_web
    monkeypatch.setattr(embodied_web,'ROOT',tmp_path)
    (tmp_path/'results').mkdir();(tmp_path/'secret.json').write_text('{"secret":true}')
    app=FastAPI();embodied_web.install_routes(app)
    with TestClient(app) as client:
        assert client.get('/benchmarks').status_code==200
        assert client.get('/api/omnijev/benchmarks').json()=={'public':{},'embodied':[]}
        assert client.get('/api/omnijev/artifact/%2E%2E%2Fsecret.json').status_code==404
