# Chrome "Copy as cURL (bash)" va qo'lda yozilgan buyruqlar
curl 'https://api.example.test/v1/users?active=true' \
  -H 'accept: application/json' \
  -H 'authorization: Bearer eyJhbGciOi' \
  --compressed

curl -X POST https://api.example.test/v1/users \
  -H 'Content-Type: application/json' \
  -d '{"name": "Ali", "tags": ["a", "b"]}'

curl -sSL -u admin:s3cret -X PUT 'https://api.example.test/v1/users/7' --data-urlencode 'note=hello world&x' -d 'a=1'

curl 'https://api.example.test/search' -H $'x-note: it\'s fine' --data-raw $'{"q":"line1\\nline2"}' -H 'content-type: application/json'

curl -F 'file=@/tmp/report.pdf' -F 'title=Q1 report' https://api.example.test/v1/upload
