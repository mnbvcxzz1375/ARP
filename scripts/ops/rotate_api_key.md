# Rotate API Key Runbook

## Purpose

Rotate a user API key. The MVP supports creating new keys; revocation may require a database maintenance operation until a dedicated revoke endpoint is added.

## Steps

1. Create a new key using `/v1/auth/register` for the same username and a new `key_name`.
2. Update callers to use `Authorization: Bearer ak_NEW`.
3. Verify:

```powershell
curl.exe -s "$env:PUBLIC_BASE_URL/v1/agents" -H "Authorization: Bearer ak_NEW"
```

4. Revoke the old key by setting `api_keys.is_revoked=true` for the old key hash or by using the future revoke endpoint.
5. Verify old key returns 401.

## Audit

Record username, key prefix only, operator, affected systems, revoke time, and validation result.
