"""Execute the maintained Pulse authority adapters, emitting fixed diagnostics only."""
import asyncio
import json
from pathlib import Path
from uuid import UUID
from baobab_pulse.configuration.settings import Settings
from baobab_pulse.application.ports.authentication import AuthenticatedCaller
from baobab_pulse.infrastructure.control_plane.context_authority import ClientCredentialsTokenProvider, HttpControlPlaneContextAuthority

async def main():
    stage='TOKEN';reason='UNKNOWN'
    try:
        s=Settings();request=json.loads(Path('/run/l4/authority.json').read_text())
        provider=ClientCredentialsTokenProvider(token_url=s.iam_token_url,client_id=s.iam_client_id,
            client_secret=s.iam_client_secret.get_secret_value(),scope='context:validate')
        await provider.access_token()
        stage='CONTEXT'
        authority=HttpControlPlaneContextAuthority(validation_url=s.control_plane_context_validation_url,validator_tokens=provider)
        await authority.redeem(context_id=UUID(request['context_id']),caller=AuthenticatedCaller(subject=request['subject'],access_token=request['token']))
        stage='READY';reason='OBSERVED'
    except Exception as error:
        reasons={
          'validator token authority is unavailable':'TOKEN_TRANSPORT',
          'validator token response violates the canonical workload profile':'TOKEN_PROFILE',
          'validator authentication failed':'VALIDATOR_AUTHENTICATION',
          'Control Plane context validation is unavailable':'CONTEXT_UNAVAILABLE',
          'context validation was denied':'CONTEXT_DENIED',
          'context is unavailable':'CONTEXT_UNKNOWN',
          'Control Plane returned a mismatched context identity':'CONTEXT_IDENTITY',
          'Control Plane returned an invalid tenant identity':'CONTEXT_TENANT',
          'Control Plane returned an unbounded context':'CONTEXT_UNBOUNDED',
          'Control Plane returned an invalid context expiry':'CONTEXT_EXPIRY',
        }
        reason=reasons.get(str(error),'UNKNOWN')
    print(json.dumps({'stage':stage,'reason':reason}))

if __name__=='__main__':asyncio.run(main())
