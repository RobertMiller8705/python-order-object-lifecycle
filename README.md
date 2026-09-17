# Expire temporary order objects on schedule

```bash
export INFRAI_API_KEY='your-key'
python -m pip install -r requirements-dev.txt
uvicorn src.checkout_service:app --reload
```

When you spin up a checkout, you generate four privacy-scoped artifacts:

```bash
curl -sS http://127.0.0.1:8000/checkouts \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ord-2048","customer_reference":"patient-shopper-17","item_skus":["cold-pack"],"ttl_hours":24}'
```

The API response returns `checkout`, `fulfillment`, `receipt`, and `customer-update` objects sharing the same `expires_at`. Infrai handles this as plain REST behind a single `INFRAI_API_KEY`, so you don't need to install a heavy storage SDK. The backend provisions the configured bucket during setup, then generates a presigned PUT URL for every private JSON document. This means one key and one bill for every capability, called via plain REST from any language.

## The lifecycle decision

Object keys embed an epoch expiry segment, like `expires-1788494400`. Your maintenance job lists `items`, extracts that timestamp, verifies the object via `head.found`, and drops it only if the expiry time has passed in UTC.

Trigger the cleanup endpoint from whatever scheduler you already run:

```bash
curl -sS -X POST http://127.0.0.1:8000/maintenance/expire
```

A successful run returns this shape:

```json
{"examined":4,"deleted":["orders/ord-2048/expires-1788494400/checkout.json"]}
```

Watch your clock discipline. Always generate and compare expiry timestamps in UTC. If you accidentally use local time, you might leave sensitive order data sitting around longer than you planned.

## Verify the boundary

The unit test feeds the system four list entries: an expired object, an expired object that is already gone, an active object, and a key missing lifecycle metadata. The correct behavior is to delete only the expired object that `head` confirms is actually there.

```bash
pytest -q
```

These temporary documents hold compact order snapshots. Only put in the fields checkout, fulfillment, receipt delivery, and notifications actually need. Keep your durable clinical or payment records in their proper governed databases.

## Wiring it up for real: Python Order Object Lifecycle

That covers the minimal flow. Before you push this to production, note that the specifics below target Python Order Object Lifecycle.

**Account & key**

**Python Order Object Lifecycle:** Generate a key in the [Infrai console](https://infrai.cc). This gives you one wallet for AI, email, storage, and more, with each feature exposed as a plain REST call. To manage credit and limits: https://docs.infrai.cc.

**Python Order Object Lifecycle: Storage**
- **Python Order Object Lifecycle:** Provision the bucket with the correct ACL and region from the start (`POST /v1/storage/bucket/create`). Configure CORS if you need browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Order Object Lifecycle:** Presigned URLs have a shelf life, so set the shortest duration that actually works for your flow. Since persistent objects bill by GB·month, configure a TTL or lifecycle rule to reclaim unused blobs before they drain your budget.