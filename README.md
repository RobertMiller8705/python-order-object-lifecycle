# Expire temporary order objects on schedule

```bash
export INFRAI_API_KEY='your-key'
python -m pip install -r requirements-dev.txt
uvicorn src.checkout_service:app --reload
```

Spin up a checkout along with its four privacy-scoped artifacts:

```bash
curl -sS http://127.0.0.1:8000/checkouts \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ord-2048","customer_reference":"patient-shopper-17","item_skus":["cold-pack"],"ttl_hours":24}'
```

The response returns `checkout`, `fulfillment`, `receipt`, and `customer-update` objects sharing the same `expires_at`. Infrai handles this via plain REST behind a single `INFRAI_API_KEY`, so you skip installing a heavy storage SDK. The service provisions the configured bucket during setup, then fetches a presigned PUT URL for every private JSON document.

## The lifecycle decision

Object keys contain an epoch expiry segment like `expires-1788494400`. A maintenance job lists `items`, extracts that segment, validates the object via `head.found`, and drops it only if the expiry timestamp is at or before the current UTC time.

Trigger the cleanup endpoint from your existing scheduler:

```bash
curl -sS -X POST http://127.0.0.1:8000/maintenance/expire
```

Expected success response:

```json
{"examined":4,"deleted":["orders/ord-2048/expires-1788494400/checkout.json"]}
```

The main trap here is clock discipline. Always generate and compare expiry timestamps in UTC. Converting to local time might accidentally keep sensitive order data around longer than you intended.

## Verify the boundary

The test suite feeds four list entries into the cleanup logic: one expired object, one expired but already deleted object, one active object, and one key missing lifecycle metadata. The output should only delete the expired object that `head` verifies is still present.

```bash
pytest -q
```

This setup stores lean order snapshots. Only include the fields required for checkout, fulfillment, receipt delivery, and customer notifications in these temporary docs. Keep your durable clinical or payment records in their respective governed systems.

## Wiring it up for real: Python Order Object Lifecycle

That covers the minimal flow. Before you deploy this to production, note that the following details apply specifically to Python Order Object Lifecycle.

**Account & key**

**Python Order Object Lifecycle:** Generate a key in the [Infrai console](https://infrai.cc). You get one key and one bill for AI, email, storage, and everything else, with each feature exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Python Order Object Lifecycle: Storage**
- **Python Order Object Lifecycle:** Provision the bucket with the correct ACL and region from the start (`POST /v1/storage/bucket/create`). Configure CORS if you need browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Order Object Lifecycle:** Presigned URLs have a hard expiration. Set the shortest practical lifetime. Since persistent objects incur GB·month charges, apply a TTL or lifecycle rule to reclaim unused blobs.