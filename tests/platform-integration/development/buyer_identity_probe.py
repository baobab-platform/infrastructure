"""Private native code-packet producer. No credential/body leaves this driver."""
import os
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
    buyer=p.native_human('maker',native,client_id=BFF,scope='trade:buy',audience='baobab-trade',callback=CALLBACK,return_code=True)
    wrong=p.native_human('maker',native,return_code=True)
    wrong.update(client_id='baobab-dev-human',client_secret=native['clients']['baobab-dev-human']['secret'])
    value={'schema':'baobab-trade.dev07-code-packet.v1','deadline':datetime.fromtimestamp(state['deadline'],timezone.utc).isoformat(),
        'bff_client_id':BFF,'bff_client_secret':native['clients'][BFF]['secret'],
        'verifier_client_id':'baobab-int03c-issuer-verifier','verifier_client_secret':native['clients']['baobab-int03c-issuer-verifier']['secret'],
        'organisation_id':fixture['organisation_id'],'other_organisation_id':fixture['other_organisation_id'],
        'country_code':'UG','codes':{'buyer':buyer,'wrong_audience':wrong}}
    p.write('buyer-code-packet.json',value)
    print('DEV07_NATIVE_CODE_PACKET_PREPARED')


def binding_control(revoked=False):
    import time, uuid
    native=p.read('native.json'); fixture=p.read('buyer-fixture.json')
    if not revoked:
        control={}
        for name,scope,audience in ((BFF,'trade:buyer-handoff','baobab-trade'),(VALIDATOR,'estate:client-binding:resolve','baobab-control-plane')):
            fields={'grant_type':'client_credentials','client_id':name,'client_secret':native['clients'][name]['secret'],'scope':scope,'audience':audience}
            code,body,_=p.request('POST',p.ISSUER+'/oauth2/token',fields,form=True)
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
        if sys.argv[1]=='packet':packet()
        elif sys.argv[1]=='cleanup':cleanup()
        elif sys.argv[1]=='binding-control':binding_control()
        elif sys.argv[1]=='binding-revoked':binding_control(True)
        else:raise ValueError()
    except Exception:raise SystemExit('DEV07_PRIVATE_PROTOCOL_FAILED') from None
