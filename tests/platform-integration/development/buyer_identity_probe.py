"""Private native code-packet producer. No credential/body leaves this driver."""
import sys
from datetime import datetime, timezone
import native_probe as p
from dev07_buyer_fixture import BFF, VALIDATOR, CALLBACK


def packet():
    native=p.read('native.json'); fixture=p.read('buyer-fixture.json'); state=p.read('state.json')
    p.require(state.get('buyer_identity_profile') is True and fixture['run_id']==state['run_id']
              and fixture['synthetic_only'] is True and fixture['protected_acceptance'] is False
              and fixture['status']=='ACTIVE','DEV07_OWNER_FIXTURE_REQUIRED')
    # Both codes follow actual Kratos login/WhoAmI + Hydra S256 PKCE/consent.
    # The negative has a separate, already registered CP human client; the
    # Trade-only BFF human profile is never broadened to manufacture a test.
    buyer=p.native_human('maker',native,client_id=BFF,scope='openid trade:buy',audience='baobab-trade',callback=CALLBACK,return_code=True)
    wrong=p.native_human('maker',native,return_code=True)
    wrong.update(client_id='baobab-dev-human',client_secret=native['clients']['baobab-dev-human']['secret'])
    value={'schema':'baobab-trade.dev07-code-packet.v1','deadline':datetime.fromtimestamp(state['deadline'],timezone.utc).isoformat(),
        'bff_client_id':BFF,'bff_client_secret':native['clients'][BFF]['secret'],
        'verifier_client_id':'baobab-int03c-issuer-verifier','verifier_client_secret':native['clients']['baobab-int03c-issuer-verifier']['secret'],
        'organisation_id':fixture['organisation_id'],'other_organisation_id':fixture['other_organisation_id'],
        'country_code':'UG','codes':{'buyer':buyer,'wrong_audience':wrong}}
    p.write('buyer-code-packet.json',value)
    print('DEV07_NATIVE_CODE_PACKET_PREPARED')



def issuer_preflight():
    """Independently test a fresh real BFF authorization code, never the qualifier's code.

    The single-use code here is exchanged and its bearer revoked before making
    the later code packet. Failures expose only a closed stage label, not the
    credential, bearer, issuer body or a private transport exception.
    """
    native=p.read('native.json')
    code=p.native_human('maker',native,client_id=BFF,scope='openid trade:buy',
                        audience='baobab-trade',callback=CALLBACK,return_code=True)
    credentials=(BFF,native['clients'][BFF]['secret'])
    verifier=('baobab-int03c-issuer-verifier',
              native['clients']['baobab-int03c-issuer-verifier']['secret'])
    token=None
    try:
        status,body,_=p.request('POST',p.ISSUER+'/oauth2/token',
            {'grant_type':'authorization_code','code':code['code'],
             'code_verifier':code['verifier'],'redirect_uri':code['redirect_uri']},
            form=True,basic=credentials)
        if status!=200 or not isinstance(body,dict) or not isinstance(body.get('access_token'),str):
            # OAuth error codes are protocol-defined, not provider response text.
            # Expose only a finite HTTP/error classification; never log details.
            error=body.get('error') if isinstance(body,dict) else None
            category=error if error in {
                'invalid_client','invalid_grant','invalid_request',
                'unauthorized_client','unsupported_grant_type','invalid_scope',
                'server_error','temporarily_unavailable'} else 'other'
            http=str(status) if status in (400,401,403,429,500,502,503,504) else 'other'
            print('DEV07_BFF_OAUTH_REFUSAL=HTTP_'+http+'_ERROR_'+category,flush=True)
            if status==403:
                marker=p.ROOT/'dev07-token-hook-refusal.json'
                if marker.is_file():
                    reason=p.read('dev07-token-hook-refusal.json').get('reason')
                    if reason in ('DEV07_GRANT_REFUSED','DEV07_ASSURANCE_ABSENT',
                                  'MISSING_SUBJECT','MISSING_ID_TOKEN','MISSING_ACR',
                                  'MISSING_GRANT_TYPES','OTHER'):
                        print('DEV07_BFF_HOOK_REFUSAL='+reason,flush=True)
            p.require(False,'DEV07_BFF_CODE_EXCHANGE_REFUSED')
        token=body['access_token']
        claims=p.claims(token)
        audience=claims.get('aud',[])
        if isinstance(audience,str):audience=[audience]
        p.require(claims.get('iss')==p.ISSUER and
                  claims.get('sub')==native['humans']['maker']['id'] and
                  claims.get('actor_type')=='human' and claims.get('azp')==BFF and
                  'baobab-trade' in audience and
                  'trade:buy' in claims.get('scope','').split(),
                  'DEV07_BFF_SIGNED_CLAIMS_REFUSED')
        status,actual,_=p.request('POST',p.ISSUER+'/oauth2/introspect',
            {'token':token},form=True,basic=verifier)
        p.require(status==200 and isinstance(actual,dict) and
                  actual.get('active') is True and
                  actual.get('client_id')==BFF and
                  actual.get('sub')==claims['sub'],
                  'DEV07_BFF_INTROSPECTION_REFUSED')
        # Independently check the real CP Principal endpoint before starting
        # the costly Trade build. No Principal or grant is manufactured here.
        import uuid
        validator=native['clients'][VALIDATOR]
        print('DEV07_CP_PRINCIPAL_STAGE=CALLER_REQUEST',flush=True)
        status,owned,_=p.request('POST',p.ISSUER+'/oauth2/token',
            {'grant_type':'client_credentials','client_id':VALIDATOR,
             'client_secret':validator['secret'],
             'scope':'identity:principal:resolve',
             'audience':'baobab-control-plane'},form=True)
        if status!=200 or not isinstance(owned,dict) or not owned.get('access_token'):
            category=owned.get('error') if isinstance(owned,dict) else None
            category=category if category in {'invalid_client','invalid_grant','invalid_request',
                    'unauthorized_client','invalid_scope','server_error'} else 'OTHER'
            http=str(status) if status in (400,401,403,429,500,503) else 'OTHER'
            print('DEV07_CP_CALLER_ISSUANCE=HTTP_'+http+'_CODE_'+category,flush=True)
            p.require(False,'DEV07_CP_CALLER_ISSUANCE_REFUSED')
        bearer=owned['access_token']
        print('DEV07_CP_PRINCIPAL_STAGE=CALLER_ISSUED',flush=True)
        try:
            correlation=str(uuid.uuid4())
            print('DEV07_CP_PRINCIPAL_STAGE=CP_REQUEST',flush=True)
            status,result,_=p.request('POST',p.CP+'/internal/identity/v1/principals/resolve',
                {'subject_token':token,
                 'subject_token_type':'urn:ietf:params:oauth:token-type:access_token',
                 'correlation_id':correlation},bearer,
                 headers={'X-Correlation-ID':correlation})
            print('DEV07_CP_PRINCIPAL_STAGE=CP_RESPONDED',flush=True)
            if status!=200:
                code=result.get('code') if isinstance(result,dict) else None
                allowed={'CALLER_NOT_PERMITTED','SUBJECT_TOKEN_INVALID',
                    'SUBJECT_TOKEN_NOT_CURRENT','SUBJECT_TOKEN_NOT_FOR_CALLER',
                    'IDENTITY_NOT_RESOLVED','PRINCIPAL_NOT_ACTIVE',
                    'RESOLUTION_UNAVAILABLE'}
                cause=code if code in allowed else 'OTHER'
                http=str(status) if status in (400,401,403,404,500,503) else 'OTHER'
                print('DEV07_CP_PRINCIPAL_REFUSAL=HTTP_'+http+'_CODE_'+cause,flush=True)
            p.require(status==200 and isinstance(result,dict) and
                result.get('outcome')=='RESOLVED' and
                result.get('actor_type')=='human' and
                result.get('status')=='ACTIVE',
                'DEV07_CP_PRINCIPAL_PREFLIGHT_REFUSED')
            print('DEV07_CP_PRINCIPAL_PREFLIGHT_OBSERVED',flush=True)
        finally:
            status,_,_=p.request('POST',p.ISSUER+'/oauth2/revoke',
                {'token':bearer,'token_type_hint':'access_token'},
                form=True,basic=(VALIDATOR,validator['secret']))
            p.require(status==200,'DEV07_CP_CALLER_REVOKE_REFUSED')

    finally:
        if token is not None:
            status,_,_=p.request('POST',p.ISSUER+'/oauth2/revoke',
                {'token':token,'token_type_hint':'access_token'},
                form=True,basic=credentials)
            p.require(status==200,'DEV07_BFF_PREFLIGHT_REVOKE_REFUSED')
            status,actual,_=p.request('POST',p.ISSUER+'/oauth2/introspect',
                {'token':token},form=True,basic=verifier)
            p.require(status==200 and actual.get('active') is False,
                      'DEV07_BFF_PREFLIGHT_REVOKE_READBACK_REFUSED')
    print('DEV07_REAL_BFF_ISSUANCE_AND_REVOCATION_PREFLIGHT_OBSERVED')



def binding_control(revoked=False):
    import time, uuid
    native=p.read('native.json'); fixture=p.read('buyer-fixture.json')
    if not revoked:
        control={}
        for name,scope,audience in ((BFF,'trade:buyer-handoff','baobab-trade'),(VALIDATOR,'estate:client-binding:resolve','baobab-control-plane')):
            fields={'grant_type':'client_credentials','scope':scope,'audience':audience}
            credential=native['clients'][name]
            if credential['config']['token_endpoint_auth_method']=='client_secret_post':
                fields.update(client_id=name,client_secret=credential['secret'])
                basic=None
            else:
                p.require(credential['config']['token_endpoint_auth_method']=='client_secret_basic',
                          'DEV07_UNSUPPORTED_CLIENT_AUTH')
                basic=(name,credential['secret'])
            code,body,_=p.request('POST',p.ISSUER+'/oauth2/token',fields,form=True,basic=basic)
            p.require(code==200 and body.get('access_token'),'DEV07_BINDING_CONTROL_ISSUANCE')
            control[name]=body['access_token']
        p.write('buyer-binding-control.json',control)
    control=p.read('buyer-binding-control.json')
    correlation=str(uuid.uuid4())
    body={'purpose':'BUYER_OPERATION','client_evidence':control[BFF],
        'client_evidence_type':'urn:ietf:params:oauth:token-type:access_token',
        'subject_authorised_party':BFF,'engine_instance_id':fixture['engine_instance_id'],
        'environment':'development','correlation_id':correlation}
    code,actual,_=p.request('POST',p.CP+'/internal/estate/v1/client-bindings/resolve',body,control[VALIDATOR],headers={'X-Correlation-ID':correlation})
    if revoked:
        p.require(code==403 and actual.get('code')=='BINDING_NOT_ACTIVE','DEV07_REVOKED_BINDING_NOT_DENIED')
    else:
        p.require(code==200 and actual.get('outcome')=='ATTESTED' and actual.get('binding_id')==fixture['binding_id']
            and actual.get('tenant_id')==fixture['tenant_id'] and actual.get('digital_estate_id')==fixture['digital_estate_id'],'DEV07_BINDING_CONTROL_FAILED')
    verifier=('baobab-int03c-issuer-verifier',native['clients']['baobab-int03c-issuer-verifier']['secret'])
    for token in control.values():
        status,current,_=p.request('POST',p.ISSUER+'/oauth2/introspect',{'token':token},form=True,basic=verifier)
        p.require(status==200 and current.get('active') is True and p.claims(token)['exp']>time.time(),'DEV07_BINDING_CONTROL_NOT_CURRENT')
    print('DEV07_CURRENT_BINDING_REVOCATION_OBSERVED' if revoked else 'DEV07_BINDING_CONTROL_OBSERVED')


def cleanup():
    native=p.read('native.json')
    # A fresh known validator token proves deletion invalidates a currently
    # active unexpired credential, rather than just closing future issuance.
    code,body,_=p.request('POST',p.ISSUER+'/oauth2/token',{'grant_type':'client_credentials',
        'client_id':VALIDATOR,'client_secret':native['clients'][VALIDATOR]['secret'],
        'scope':'context:resolve','audience':'baobab-control-plane'},form=True)
    p.require(code==200 and body.get('access_token'),'DEV07_CONTROL_ISSUANCE_REQUIRED')
    token=body['access_token']; verifier=('baobab-int03c-issuer-verifier',native['clients']['baobab-int03c-issuer-verifier']['secret'])
    def status():return p.request('POST',p.ISSUER+'/oauth2/introspect',{'token':token},form=True,basic=verifier)
    p.require(status()[1].get('active') is True,'DEV07_CONTROL_READBACK_REQUIRED')
    for name in (BFF,VALIDATOR):
        p.require(p.api('DELETE','/admin/clients/'+name)[0]==204,'DEV07_CLIENT_DELETE_FAILED')
        p.require(p.api('GET','/admin/clients/'+name)[0]==404,'DEV07_CLIENT_SURVIVED')
    p.require(status()[1].get('active') is False and p.claims(token)['exp']>__import__('time').time(),'DEV07_DELETION_NOT_CURRENT')
    print('DEV07_NATIVE_CLIENTS_DELETED_AND_CONTROL_INACTIVE')


if __name__=='__main__':
    try:
        if sys.argv[1]=='issuer-preflight':issuer_preflight()
        elif sys.argv[1]=='packet':packet()
        elif sys.argv[1]=='cleanup':cleanup()
        elif sys.argv[1]=='binding-control':binding_control()
        elif sys.argv[1]=='binding-revoked':binding_control(True)
        else:raise ValueError()
    except Exception as error:
        # A closed, reviewed error vocabulary is the only information exported
        # from this private probe into Actions logs. No token/provider body.
        codes={'DEV07_BFF_CODE_EXCHANGE_REFUSED','DEV07_BFF_SIGNED_CLAIMS_REFUSED',
               'DEV07_BFF_INTROSPECTION_REFUSED','DEV07_CP_CALLER_ISSUANCE_REFUSED',
               'DEV07_CP_PRINCIPAL_PREFLIGHT_REFUSED',
               'DEV07_CP_CALLER_REVOKE_REFUSED',
               'DEV07_BFF_PREFLIGHT_REVOKE_REFUSED',
               'DEV07_BFF_PREFLIGHT_REVOKE_READBACK_REFUSED','DEV07_UNSUPPORTED_CLIENT_AUTH'}
        if isinstance(error,ValueError) and str(error) in codes:
            print('DEV07_PRIVATE_FAILURE_CLASS='+str(error),flush=True)
        raise SystemExit('DEV07_PRIVATE_PROTOCOL_FAILED') from None
