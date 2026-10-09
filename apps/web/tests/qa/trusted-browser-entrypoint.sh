#!/bin/sh
set -eu
test "${QA_PROJECT:-}" = chemistryaudit2
test "${QA_BASE_URL:-}" = https://localhost:18543
test "${QA_CA_CERT:-}" = /qa-ca/cert.pem
test -r "$QA_CA_CERT"
test "${QA_LOCAL_TLS:-false}" != true
openssl x509 -in "$QA_CA_CERT" -noout -checkend 60 >/dev/null
taskNssDir=/home/pwuser/.pki/nssdb
certutil -N -d "sql:$taskNssDir" --empty-password
certutil -A -d "sql:$taskNssDir" -n chemistry-local-qa -t 'C,,' -i "$QA_CA_CERT"
# Node/APIRequestContext validates TLS too, using only this additional CA.
export NODE_EXTRA_CA_CERTS="$QA_CA_CERT"
export NODE_OPTIONS='--require=/app/tests/qa/localhost-routing.cjs'
printf 'QA public certificate SHA-256: '
openssl x509 -in "$QA_CA_CERT" -outform DER | sha256sum
exec "$@"
