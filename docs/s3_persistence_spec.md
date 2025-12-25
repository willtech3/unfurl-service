# Specification: S3 Asset Persistence for Unfurl Service

This specification details the work required to implement S3-based asset persistence for the Instagram Unfurl Service. This checks the "disappearing images" issue caused by ephemeral Instagram CDN URLs.

> [!IMPORTANT]
> **Technical Constraint Check**:
> - **Region**: S3 URLs must be region-specific (`s3.{region}.amazonaws.com`) to work reliably outside `us-east-1`.
> - **Public Access**: New buckets default to `ObjectOwnership.BUCKET_OWNER_ENFORCED`, which disables ACLs. We must use a Bucket Policy for public access, not ACLs.

---

## 📦 Infrastructure Changes (`cdk/stacks/unfurl_service_stack.py`)

### 1. Update Stack Implementation

- [x] **Import S3 Module**
    - [x] Ensure `aws_s3 as s3` is imported.

- [x] **Create Public Assets Bucket**
    - [x] Define a new `s3.Bucket` construct named `UnfurlAssets`.
    - [x] **Critical Configuration**:
        - [x] `bucket_name`: `f"unfurl-assets-{env_name}"`
        - [x] `public_read_access`: `True` (This automatically adds the `s3:GetObject` bucket policy).
        - [x] `block_public_access`: **MUST** explicit disable all blocks to allow public reads:
            ```python
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False
            )
            ```
        - [x] `removal_policy`: `RemovalPolicy.DESTROY` (for clean teardown).
        - [x] `auto_delete_objects`: `True`.
        - [x] `lifecycle_rules`: Add rule to expire objects after **30 days** (cost management).
        - [x] `cors`: **Not Required** (Slack fetches images server-side; browser CORS not needed).

- [x] **Grant Permissions**
    - [x] `assets_bucket.grant_write(unfurl_processor)`
    - [x] `assets_bucket.grant_read(unfurl_processor)`

- [x] **Update Lambda Environment**
    - [x] Add `ASSETS_BUCKET_NAME` = `assets_bucket.bucket_name`.
    - [x] **Verify**: `AWS_REGION` is available in Lambda env (standard default).

---

## 🐍 Application Code Changes

### 1. New Utility Module (`src/unfurl_processor/asset_manager.py`)

- [x] **Create `AssetManager` Class**
    - [x] **Imports**: `asyncio`, `hashlib`, `os`, `boto3`, `httpx`, `botocore.exceptions`.
    - [x] **Constructor**:
        - Initialize `self.s3_client` (sync `boto3.client("s3")`).
        - Read `self.bucket_name` from env `ASSETS_BUCKET_NAME`.
        - Read `self.region` from env `AWS_REGION` (default to `us-east-1` if missing).
        - Initialize `self.http_client` (or pass shared instance).

- [x] **Implement `_generate_key` Helper**
    - [x] **Signature**: `def _generate_key(self, post_id: str, url: str, content_type: str) -> str`
    - [x] **Logic**:
        1. Hash the source URL: `url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]`.
        2. Map Content-Type to extension:
           - `image/jpeg` -> `.jpg`
           - `image/png` -> `.png`
           - `image/webp` -> `.webp`
           - Default -> `.jpg`
        3. Return `f"instagram/{post_id}/{url_hash}.{ext}"`.

- [x] **Implement `upload_image` Method**
    - [x] **Signature**: `async def upload_image(self, url: str, post_id: str) -> Optional[str]`
    - [x] **Logic**:
        1. **Download**: `await self.http_client.get(url)`.
           - Timeout: 5 seconds.
           - Check status: `response.raise_for_status()`.
        2. **Detect Type**: `content_type = response.headers.get("Content-Type", "image/jpeg")`.
        3. **Generate Key**: Call `_generate_key`.
        4. **Upload (Async Wrapper)**:
           - Run sync `put_object` in `asyncio.to_thread` to avoid blocking event loop.
           - **Parameters**:
             - `Bucket`: `self.bucket_name`
             - `Key`: Key
             - `Body`: `response.content`
             - `ContentType`: `content_type`
             - `CacheControl`: `max-age=31536000` (1 year)
             - **Do NOT set ACL** (Legacy ACLs are disabled).
        5. **Return URL**: `f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"`.

    - [x] **Error Handling**:
        - Catch `httpx.HTTPError`: Log warning, return `None`.
        - Catch `botocore.exceptions.ClientError`: Log warning (include status code), return `None`.
        - Catch generic `Exception`: Log error, return `None`.

---

### 2. Update Handler (`src/unfurl_processor/handler_async.py`)

- [x] **Initialize AssetManager**
    - [x] Import `AssetManager`.
    - [x] In `__init__`: `self.asset_manager = None` (lazy init).
    - [x] Add `_get_asset_manager()` helper (singleton pattern).
          - Check if `os.environ.get("ASSETS_BUCKET_NAME")` exists. If not, return `None` (graceful degradation).

- [x] **Integrate into `_process_single_link`**
    - [x] **Location**: **Before** calling `_format_unfurl_data` (so Slack gets the persistent URL).
    - [x] **Logic**:
        ```python
        # Existing fetch logic...
        instagram_data = await self._fetch_instagram_data(url)

        if instagram_data:
            # START NEW LOGIC
            asset_manager = self._get_asset_manager()
            post_id = self._extract_instagram_id(url)

            # Check for image_url OR video poster
            target_url = instagram_data.get("image_url")

            if asset_manager and target_url and post_id:
                s3_url = await asset_manager.upload_image(target_url, post_id)
                if s3_url:
                    instagram_data["image_url"] = s3_url
                    logger.info(f"Persisted asset for {post_id} to {s3_url}")
            # END NEW LOGIC

        unfurl_data = self._format_unfurl_data(instagram_data)
        ```

---

## ✅ Verification & Testing

### 1. Unit Tests (`tests/unit/test_asset_manager.py`)
- [x] **Dependencies**: Use `pytest-mock` and `pytest-asyncio`.
- [x] **Test Cases**:
    1. `test_key_generation`: Verify unique hash from URL and extension mapping.
    2. `test_upload_success`: Mock `httpx.get` (200 OK) and `s3_client.put_object`. Verify returned URL format.
    3. `test_download_failure`: Mock `httpx.get` (404/500). Verify `None` return.
    4. `test_s3_upload_failure`: Mock `put_object` side_effect (`ClientError`). Verify `None` return.

### 2. Integration Verification
- [ ] **Deploy**: `just deploy dev`.
- [ ] **Verify Resources**:
    - Check Bucket exists.
    - Check "Block Public Access" settings are all **Off**.
    - Check Bucket Policy allows `Principal: *` for `s3:GetObject`.
- [ ] **Live Test**:
    - Post Instagram link in Slack.
    - Check CloudWatch logs: "Persisted asset for X to ..."
    - Curl the returned S3 URL from a terminal (without AWS creds) to verify public access.
