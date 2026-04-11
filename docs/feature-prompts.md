# Prompt cho từng Feature F1-F6 — Claude Code

> **Cách dùng:** Copy prompt của feature bạn đang làm vào Claude Code. Mỗi prompt là một session riêng. Làm theo đúng thứ tự F6 → F1 → F4 → F2 → F3 → F5 (theo dependency).
>
> **Prerequisite:** Đã chạy xong Prompt khởi tạo dự án (bootstrap). Monorepo đã có skeleton, database migration đã chạy, seed data đã có.

---

## Thứ tự implement đề xuất

```
F6 (Auth/Billing)  ← nền tảng, phải có trước
    ↓
F1 (Products)      ← cần auth để scope theo shop
    ↓
F4 (Extension)     ← cần products để chọn khi start session
    ↓
F2 (Comment AI)    ← cần extension + products + RAG
    ↓
F3 (Scripts)       ← cần products + personas, độc lập với extension
    ↓
F5 (Analytics)     ← cần data từ sessions/suggestions để hiển thị
```

---

# F6: Authentication + Billing + Multi-tenancy

```markdown
# Task: Implement F6 — Authentication + Billing + Multi-tenancy

## Context

Đọc `docs/AI-Cohost-System-Design.md`:
- Phần 2.4 (Nhóm B — Auth & Onboarding): màn hình B1-B6
- Phần 2.7 (Nhóm E — Settings): màn hình E1-E3
- Phần 3.4.1-3.4.3: bảng shops, users, shop_members
- Phần 3.4.14-3.4.16: bảng subscriptions, invoices, usage_logs
- Phần 3.5: Row-Level Security
- Phần 4.6: Security Design (Auth, Authorization, Rate Limiting)

## Scope

F6 là nền tảng cho toàn bộ hệ thống. Không có F6, không feature nào khác hoạt động được.

## Backend — apps/api

### 1. Auth module

**File cần tạo:**
- `app/auth/router.py` — endpoints
- `app/auth/service.py` — business logic
- `app/auth/dependencies.py` — FastAPI dependencies (get_current_user, get_current_shop)
- `app/auth/schemas.py` — Pydantic models
- `app/auth/utils.py` — JWT helpers, password hashing

**Endpoints cần implement:**

```
POST   /api/auth/signup          — tạo user + shop mới
POST   /api/auth/login           — email/password → JWT pair
POST   /api/auth/refresh         — refresh token → new JWT pair
POST   /api/auth/verify-email    — verify OTP code
POST   /api/auth/resend-otp      — gửi lại OTP
POST   /api/auth/forgot-password — gửi reset link qua email
POST   /api/auth/reset-password  — đổi password bằng reset token
POST   /api/auth/google          — OAuth Google callback
GET    /api/auth/me              — thông tin user hiện tại
```

**Signup flow chi tiết:**
1. Validate email unique, password strength (min 8 chars)
2. Hash password bằng bcrypt (passlib)
3. INSERT vào `users` với `email_verified = false`
4. Sinh OTP 6 số, lưu vào Redis key `otp:{user_id}` TTL 10 phút
5. Gửi email qua Resend API
6. Return `{ user_id, message: "Vui lòng kiểm tra email" }`

**Verify email flow:**
1. Nhận OTP, so khớp với Redis key
2. UPDATE `users` SET `email_verified = true`
3. Xóa Redis key
4. Auto-login: sinh JWT pair, return tokens

**JWT implementation:**
- Access token: `{ user_id, email, shop_ids: [...], exp }` — 1 giờ
- Refresh token: `{ user_id, jti, exp }` — 30 ngày
- Lưu refresh token JTI vào Redis SET `refresh:{user_id}`
- Khi refresh: verify JTI exists → xóa JTI cũ → sinh token mới → lưu JTI mới (rotation)
- Khi logout: xóa JTI khỏi Redis

**FastAPI dependency `get_current_user`:**
```python
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_jwt(token)
    user = await user_repo.get_by_id(payload["user_id"])
    if not user:
        raise HTTPException(401, "User không tồn tại")
    return user
```

**FastAPI dependency `get_current_shop`:**
```python
async def get_current_shop(
    shop_id: int = Header(..., alias="X-Shop-Id"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Shop:
    # Verify user là member của shop
    member = await shop_member_repo.get(db, shop_id=shop_id, user_id=user.id)
    if not member or member.status != "active":
        raise HTTPException(403, "Bạn không có quyền truy cập shop này")
    # Set RLS context
    await db.execute(text(f"SET LOCAL app.current_shop_id = {shop_id}"))
    return await shop_repo.get_by_id(db, shop_id)
```

**Rate limiting:**
- `/api/auth/login`: 5 requests/phút per IP
- `/api/auth/signup`: 3 requests/giờ per IP
- `/api/auth/resend-otp`: 3 requests/10 phút per user
- Dùng Redis INCR + TTL hoặc thư viện `slowapi`

### 2. Shop & Team module

**Endpoints:**

```
POST   /api/shops                    — tạo shop (trong onboarding)
GET    /api/shops/:id                — thông tin shop
PATCH  /api/shops/:id                — update shop
GET    /api/shops/:id/members        — danh sách team
POST   /api/shops/:id/members/invite — mời thành viên
PATCH  /api/shops/:id/members/:mid   — đổi role
DELETE /api/shops/:id/members/:mid   — xóa thành viên
```

**Tạo shop flow (trong onboarding B3):**
1. INSERT `shops` với data từ form
2. Auto-generate `slug` từ name (slugify tiếng Việt, xử lý dấu)
3. INSERT `shop_members` với role='owner', user_id=current_user
4. Tạo 4 preset personas (Thân thiện, Năng động, Chuyên nghiệp, Hài hước) cho shop mới
5. Persona "Thân thiện" set `is_default = true`

**Invite member flow:**
1. Validate email, validate team seat limit theo plan
2. INSERT `shop_members` status='pending', invited_by=current_user
3. Gửi email mời
4. Khi user click link → verify → UPDATE status='active', joined_at=now()

**Quan trọng:** Check seat limit:
- Starter: 1 seat (owner only)
- Pro: 3 seats
- Agency: 10 seats

### 3. Billing module

**Endpoints:**

```
POST   /api/billing/checkout         — tạo Lemon Squeezy checkout URL
POST   /api/billing/webhook          — Lemon Squeezy webhook handler
GET    /api/billing/subscription      — thông tin subscription hiện tại
POST   /api/billing/portal           — redirect đến billing portal
GET    /api/billing/invoices          — list invoices
GET    /api/billing/usage             — usage summary tháng hiện tại
```

**Lemon Squeezy webhook events cần handle:**
- `subscription_created` → INSERT subscription, UPDATE shop.plan
- `subscription_updated` → UPDATE subscription
- `subscription_cancelled` → UPDATE subscription, schedule plan downgrade
- `subscription_payment_success` → INSERT invoice
- `subscription_payment_failed` → notify user, UPDATE plan_status

**Webhook security:**
- Verify Lemon Squeezy signature header
- Idempotency: lưu event_id, skip nếu đã xử lý

**Usage tracking service:**
```python
class UsageService:
    async def track(self, shop_id, resource_type, quantity, unit, cost_usd=None):
        """Ghi usage log. Gọi mỗi khi có consumption."""
        await usage_repo.insert(UsageLog(
            shop_id=shop_id,
            resource_type=resource_type,  # "live_hours", "scripts", "dh_minutes"
            quantity=quantity,
            unit=unit,
            cost_usd=cost_usd,
            billing_period=date.today().replace(day=1)
        ))

    async def check_quota(self, shop_id, resource_type) -> QuotaStatus:
        """Check còn quota không. Gọi trước mỗi operation."""
        plan = await self._get_plan(shop_id)
        used = await self._get_used_this_month(shop_id, resource_type)
        limit = PLAN_LIMITS[plan][resource_type]
        return QuotaStatus(used=used, limit=limit, remaining=limit - used)
```

**Plan limits constant:**
```python
PLAN_LIMITS = {
    "trial": {"products": 20, "live_hours": 5, "scripts": 5, "dh_minutes": 0, "voices": 0, "seats": 1},
    "starter": {"products": 20, "live_hours": 20, "scripts": 20, "dh_minutes": 0, "voices": 0, "seats": 1},
    "pro": {"products": 100, "live_hours": 100, "scripts": 100, "dh_minutes": 300, "voices": 1, "seats": 3},
    "agency": {"products": 99999, "live_hours": 99999, "scripts": 99999, "dh_minutes": 1200, "voices": 5, "seats": 10},
}
```

### 4. Middleware & RLS

Tạo middleware chain:

```python
@app.middleware("http")
async def tenant_context_middleware(request, call_next):
    # 1. Extract JWT, get user
    # 2. Extract X-Shop-Id header
    # 3. Verify membership
    # 4. SET LOCAL app.current_shop_id
    # 5. Proceed
```

RLS policies phải được tạo trong migration (đã có trong bootstrap).

## Frontend — apps/dashboard

### Màn hình cần implement

**B1. Sign Up page** (`/signup`)
- Form: email, password, confirm password
- Google OAuth button
- Link đến login
- Vietnamese validation messages: "Email không hợp lệ", "Mật khẩu ít nhất 8 ký tự"

**B2. Verify OTP** (`/verify`)
- 6 input boxes, auto-focus next on type
- Timer đếm ngược 60s cho resend
- Auto-submit khi nhập đủ 6 số

**Login** (`/login`)
- Email + password form
- Google OAuth
- Forgot password link
- "Chưa có tài khoản? Đăng ký"

**B3-B6. Onboarding Wizard** (`/onboarding`)
- 4 step wizard với progress bar
- Step 1: Shop info (name, industry dropdown, platforms checkboxes, team size radio)
- Step 2: Install extension (link Chrome Web Store, detect nếu đã cài)
- Step 3: Add first product (paste URL hoặc manual — chỉ UI skeleton, logic thêm ở F1)
- Step 4: Choose persona (4 preset cards với preview text)
- Mỗi step có Back/Next, step 2 và 3 có Skip

**E1. Account Settings** (`/settings`)
- Profile form: avatar upload, name, phone
- Security section: change password, 2FA toggle
- Danger zone: delete account (double confirm)

**E2. Billing** (`/settings/billing`)
- Current plan card với usage meters (progress bars)
- Upgrade/Downgrade buttons → redirect Lemon Squeezy checkout
- Payment method display
- Invoice history table

**E3. Team Management** (`/settings/team`)
- Members table: avatar, name, email, role badge, actions
- Invite modal: email input, role select
- Role descriptions tooltip

### State management

Zustand stores cần tạo:
```typescript
// stores/auth.ts
interface AuthStore {
  user: User | null;
  currentShop: Shop | null;
  shops: Shop[];
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  switchShop: (shopId: number) => void;
}

// stores/billing.ts
interface BillingStore {
  subscription: Subscription | null;
  usage: UsageSummary | null;
  fetchSubscription: () => Promise<void>;
  fetchUsage: () => Promise<void>;
}
```

### Auth guard

Tạo middleware Next.js protect routes:
- `/login`, `/signup`, `/verify` — chỉ cho guest
- `/dashboard/*` — yêu cầu auth
- `/onboarding` — yêu cầu auth nhưng chưa cần shop

### API client

Tạo `lib/api.ts` với:
- Axios instance pre-configured base URL, JWT header, X-Shop-Id header
- Auto refresh token khi nhận 401
- Error interceptor hiển thị toast tiếng Việt
- TypeScript types cho mọi request/response

## Tests bắt buộc

### Unit tests
- [ ] Password hash + verify works
- [ ] JWT sign + decode + expire works
- [ ] OTP generate + validate + expire works
- [ ] Slug generation từ tiếng Việt (ví dụ "Shop Mỹ Phẩm Linh" → "shop-my-pham-linh")
- [ ] Plan limits enforcement (quota check returns correct remaining)
- [ ] Webhook signature verification

### Integration tests
- [ ] Signup → verify email → login → access protected endpoint
- [ ] Signup → onboarding → shop created with 4 preset personas
- [ ] Login → access shop A data → không thể access shop B data (RLS test)
- [ ] Invite member → accept invite → verify role correct
- [ ] Usage tracking → quota exceeded → endpoint returns 429
- [ ] Lemon Squeezy webhook → subscription updated correctly

### Manual test checklist
- [ ] Google OAuth login works end-to-end
- [ ] OTP email arrives trong 30 giây
- [ ] Resend OTP timer 60s correct
- [ ] Onboarding wizard navigate back/forward works
- [ ] Skip button works trên step 2, 3
- [ ] Billing page hiển thị đúng plan và usage

## Acceptance criteria
- Signup → login → onboarding hoàn tất trong dưới 5 phút
- Zero cross-tenant data leak (verified bằng integration test)
- Tất cả text UI bằng tiếng Việt
- Rate limiting active cho auth endpoints
- Webhook handler idempotent
```

---

# F1: Shop Onboarding & Product Catalog

```markdown
# Task: Implement F1 — Shop Onboarding & Product Catalog

## Context

Đọc `docs/AI-Cohost-System-Design.md`:
- Phần 2.4 (B5 — Add First Product trong onboarding)
- Phần 2.5 (C2 — Products List, C3 — Product Detail/Edit)
- Phần 3.4.4: bảng products
- Phần 3.4.5: bảng product_faqs
- Phần 3.4.6: bảng personas
- Phần 3.6.1: RAG query pattern
- Phần 4.5.4: Product Embedding Flow

**Dependency:** F6 (Auth) phải xong trước.

## Scope

F1 gồm:
1. CRUD products (backend + frontend)
2. CRUD product FAQs
3. AI auto-generate highlights từ description
4. AI auto-generate FAQ từ description
5. Auto-extract product info từ Shopee/TikTok Shop URL
6. Embedding generation async (pgvector)
7. CRUD personas
8. Trang Products List (C2) và Product Detail (C3) trên dashboard

## Backend — apps/api

### Endpoints

```
# Products
GET    /api/products              — list products (shop scoped, paginated)
POST   /api/products              — tạo product
GET    /api/products/:id          — chi tiết product
PATCH  /api/products/:id          — update product
DELETE /api/products/:id          — xóa product
POST   /api/products/:id/reindex  — force re-embed
POST   /api/products/extract-url  — extract info từ URL

# Product FAQs
GET    /api/products/:id/faqs     — list FAQs của product
POST   /api/products/:id/faqs     — tạo FAQ
PATCH  /api/faqs/:faq_id          — update FAQ
DELETE /api/faqs/:faq_id          — xóa FAQ

# AI Generation
POST   /api/products/:id/ai/highlights  — AI sinh highlights
POST   /api/products/:id/ai/faqs        — AI sinh FAQs

# Personas
GET    /api/personas              — list personas (shop scoped)
POST   /api/personas              — tạo persona
PATCH  /api/personas/:id          — update persona
DELETE /api/personas/:id          — xóa persona (không xóa preset)
PATCH  /api/personas/:id/default  — set làm default
```

### Product CRUD service

```python
class ProductService:
    async def create(self, shop_id: int, data: ProductCreate) -> Product:
        # 1. Check quota: await usage_svc.check_quota(shop_id, "products")
        # 2. INSERT product với embedding = None
        # 3. Enqueue embed task: embed_product.delay(product.id)
        # 4. Track usage: await usage_svc.track(shop_id, "products", 1, "count")
        # 5. Return product

    async def update(self, product_id: int, data: ProductUpdate) -> Product:
        # 1. UPDATE fields
        # 2. Nếu name/description/highlights thay đổi:
        #    SET embedding = None, embedding_updated_at = None
        #    Enqueue embed task
        # 3. Return updated product
```

### URL extraction service

```python
class UrlExtractService:
    async def extract(self, url: str) -> ProductExtract:
        """
        Từ URL Shopee/TikTok Shop, extract:
        - name, description, price, images, category
        
        Implementation:
        1. Detect platform từ URL pattern
        2. Fetch page content (dùng httpx hoặc playwright cho JS-rendered)
        3. Parse HTML/JSON (Shopee có JSON-LD, TikTok có __INITIAL_STATE__)
        4. Return structured data
        
        Fallback nếu parse fail:
        - Gọi LLM với raw HTML text, yêu cầu extract structured info
        """
```

**Lưu ý:** Shopee và TikTok Shop có anti-scraping. Dùng:
- Shopee: try API endpoint `/api/v4/item/get` trước, fallback sang HTML parse
- TikTok: try `__INITIAL_STATE__` JSON trong HTML
- Nếu cả hai fail: return partial data + notify user "Không extract được, vui lòng nhập thủ công"
- KHÔNG dùng headless browser trong MVP (quá nặng)

### AI generation services

```python
class AIHighlightService:
    PROMPT = """Bạn là chuyên gia marketing sản phẩm Việt Nam.
    
Dựa trên thông tin sản phẩm sau, hãy sinh ra {count} điểm nổi bật ngắn gọn (mỗi điểm 5-15 từ).
Mỗi điểm phải hấp dẫn, cụ thể, và giúp khách hàng muốn mua.

Tên sản phẩm: {name}
Mô tả: {description}
Giá: {price}
Ngành hàng: {category}

Trả về JSON array of strings. Chỉ trả JSON, không có text khác.
Ví dụ: ["SPF50 PA++++ bảo vệ tối đa", "Kết cấu lỏng nhẹ thấm trong 30 giây"]"""

    async def generate(self, product: Product, count: int = 6) -> list[str]:
        # 1. Build prompt với product data
        # 2. Call Gemini Flash
        # 3. Parse JSON response
        # 4. Validate: mỗi highlight 5-15 từ
        # 5. Return list


class AIFaqService:
    PROMPT = """Bạn là chuyên viên CSKH cho shop bán hàng online Việt Nam.

Dựa trên thông tin sản phẩm, hãy sinh ra {count} cặp câu hỏi-trả lời mà khách hàng hay hỏi nhất khi xem live.

Tên sản phẩm: {name}
Mô tả: {description}
Điểm nổi bật: {highlights}
Giá: {price}

Trả về JSON array of objects: [{{"question": "...", "answer": "..."}}]
Câu trả lời phải thân thiện, xưng "em/mình" với khách, dưới 50 từ mỗi câu.
Chỉ trả JSON."""

    async def generate(self, product: Product, count: int = 5) -> list[FaqPair]:
        # 1. Build prompt
        # 2. Call Gemini Flash
        # 3. Parse JSON
        # 4. Return list of FaqPair
```

### Embedding service (Celery task)

```python
# apps/workers/tasks/embedding.py

@celery.task(queue="embed_queue", max_retries=3, default_retry_delay=10)
def embed_product(product_id: int):
    """
    1. Fetch product from DB
    2. Build text: f"{product.name}. {product.description}. {'. '.join(product.highlights)}"
    3. Call Gemini text-embedding-004 API
    4. UPDATE products SET embedding = vector, embedding_model = "gemini-004", 
       embedding_updated_at = now()
    5. Publish WebSocket event "product.indexed" cho shop
    """

@celery.task(queue="embed_queue", max_retries=3, default_retry_delay=10)
def embed_faq(faq_id: int):
    """
    1. Fetch FAQ from DB
    2. Call embedding API với faq.question
    3. UPDATE product_faqs SET embedding, embedding_model, embedding_updated_at
    """

@celery.task(queue="embed_queue")
def reindex_all_products(shop_id: int):
    """Bulk re-embed tất cả products và FAQs của shop. Dùng khi đổi model."""
```

**Gemini embedding client:**
```python
import google.generativeai as genai

class EmbeddingClient:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
    
    async def embed(self, text: str) -> list[float]:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="RETRIEVAL_DOCUMENT"  # hoặc RETRIEVAL_QUERY khi search
        )
        return result['embedding']  # 768 dimensions
```

**QUAN TRỌNG:** Khi embed cho search (query), dùng `task_type="RETRIEVAL_QUERY"`. Khi embed cho document (product, FAQ), dùng `task_type="RETRIEVAL_DOCUMENT"`. Hai cái khác nhau và ảnh hưởng quality.

## Frontend — apps/dashboard

### C2. Products List (`/products`)

**Components:**
- `ProductsPage` — page container
- `ProductsTable` — table với columns, sort, filter
- `ProductStatusBadge` — "Sẵn sàng" (green) / "Đang index" (yellow) / "Lỗi" (red)
- `AddProductModal` — modal với 2 tabs: "Paste URL" và "Nhập thủ công"
- `BulkActions` — delete, reindex selected
- `EmptyState` — khi chưa có product nào (thiết kế theo Phần 2.8 F1)

**Table columns:**
1. Checkbox
2. Ảnh thumbnail (40x40) + tên product
3. Giá (format VND: 350.000₫)
4. Status badge
5. Ngày cập nhật (relative: "2 giờ trước")
6. Actions dropdown (Sửa, Xóa, Re-index)

**Search + Filter:**
- Search bar: full-text search tên product (gọi API với query param)
- Filter: dropdown "Tất cả / Sẵn sàng / Đang index / Lỗi"
- Sort: "Mới nhất / Cũ nhất / Tên A-Z / Giá cao-thấp"

**Pagination:** 20 items/page, offset-based

**Real-time updates:** Subscribe WebSocket event "product.indexed" để auto-update status badge khi embedding hoàn thành.

### C3. Product Detail (`/products/:id`)

**Layout 2 columns:**

Cột trái (40%):
- Image gallery (upload drag-drop, multi image)
- Upload dùng R2 presigned URL
- Thumbnail previews

Cột phải (60%):
- Form fields: name, description (textarea), price (number input, VND format)
- Highlights section:
  - Ordered list hiện tại, mỗi item có nút xóa
  - Input + nút "Thêm"
  - Nút "✨ AI gợi ý thêm" → call `/ai/highlights` → hiện modal với suggestions, user chọn giữ cái nào
- FAQ section:
  - Accordion list, mỗi item expand/collapse
  - Nút "Thêm FAQ"
  - Nút "✨ AI tạo FAQ" → call `/ai/faqs` → hiện modal tương tự highlights
- Footer: status badge + "Cập nhật lần cuối: ..." + nút "Re-index" + nút "Lưu" (primary)

**Auto-save consideration:** KHÔNG auto-save. User phải click "Lưu" explicitly. Nhưng có warn khi navigate away nếu có unsaved changes (beforeunload).

### B5 trong Onboarding (đã có skeleton từ F6, giờ implement logic)

- Tab "Paste URL": input URL + nút "Trích xuất tự động" → gọi `/products/extract-url` → fill form
- Tab "Nhập thủ công": form giống C3 nhưng simplified (chỉ name, description, price)
- Sau khi save → auto navigate sang B6
- "Bỏ qua" → navigate B6 luôn

## Tests bắt buộc

### Unit tests
- [ ] Product CRUD: create, read, update, delete
- [ ] Quota check: tạo product khi hết quota → trả 429
- [ ] AI highlight generation: parse JSON response correctly
- [ ] AI FAQ generation: parse JSON response correctly
- [ ] URL extraction: Shopee URL pattern detection
- [ ] Embedding task: verify vector dimension = 768
- [ ] Slug/search: trigram search tìm được "kem chống nắng" khi query "chong nang"

### Integration tests
- [ ] Create product → embedding generated trong 10 giây → search tìm được
- [ ] Update product name → embedding re-generated → search tìm được tên mới
- [ ] Create product + 5 FAQs → tất cả embedded
- [ ] Delete product → FAQs cascade deleted → embeddings removed
- [ ] Product scoped by shop: shop A không thấy products shop B

### Manual test checklist
- [ ] Paste link Shopee → auto-fill ít nhất name + price
- [ ] AI highlights sinh 6 highlights hợp lý cho mỹ phẩm
- [ ] AI FAQ sinh 5 FAQ tiếng Việt tự nhiên
- [ ] Product status badge chuyển "Đang index" → "Sẵn sàng" tự động
- [ ] Empty state hiển thị hướng dẫn khi chưa có product
- [ ] Search tìm được product khi gõ partial name

## Acceptance criteria
- Thêm 10 products xong trong dưới 10 phút (với paste URL)
- Embedding sẵn sàng trong dưới 10 giây
- AI highlights/FAQ sinh kết quả tiếng Việt tự nhiên
- Mọi product query filter theo shop_id
```

---

# F4: Multi-Platform Browser Extension

```markdown
# Task: Implement F4 — Multi-Platform Browser Extension

## Context

Đọc `docs/AI-Cohost-System-Design.md`:
- Phần 2.6 (Nhóm D — Live Session): D1-D4
- Phần 4.3.2: Extension tech stack
- Phần 4.4.2: WebSocket protocol
- Phần 4.5.2: Quick Paste Flow

**Dependencies:** F6 (Auth) và F1 (Products) phải xong trước.

## Scope

F4 gồm:
1. Chrome Extension MV3 (Manifest, background, content scripts)
2. Platform adapters (Facebook, YouTube, TikTok, Shopee)
3. Extension popup (D1)
4. Live overlay (D2, D3, D4) — UI skeleton, chưa có AI response (đợi F2)
5. WebSocket connection với backend
6. Quick Paste mechanism
7. Session lifecycle management

**QUAN TRỌNG:** F4 chỉ build infrastructure. AI response logic là F2. Trong F4, overlay sẽ hiện mock suggestions để test UX.

## Extension Structure

```
apps/extension/
├── src/
│   ├── manifest.json
│   ├── background/
│   │   └── index.ts              # Service worker
│   ├── content/
│   │   ├── index.ts              # Content script entry
│   │   ├── adapters/
│   │   │   ├── types.ts          # PlatformAdapter interface
│   │   │   ├── facebook.ts
│   │   │   ├── youtube.ts
│   │   │   ├── tiktok.ts
│   │   │   └── shopee.ts
│   │   ├── comment-reader.ts     # DOM observer cho comments
│   │   ├── smart-paste.ts        # Quick Paste implementation
│   │   └── overlay/
│   │       ├── mount.ts          # Inject overlay vào page
│   │       ├── Overlay.tsx       # Main overlay component (Preact)
│   │       ├── SuggestionCard.tsx
│   │       ├── HistoryList.tsx
│   │       └── styles.css        # Tailwind compiled
│   ├── popup/
│   │   ├── index.html
│   │   ├── Popup.tsx
│   │   └── styles.css
│   ├── lib/
│   │   ├── ws-client.ts          # WebSocket client
│   │   ├── storage.ts            # chrome.storage helpers
│   │   ├── auth.ts               # JWT token management
│   │   └── constants.ts
│   └── types/
│       └── messages.ts           # Message types between scripts
├── vite.config.ts
├── tailwind.config.ts
└── package.json
```

## 1. Platform Adapter Interface

```typescript
// src/content/adapters/types.ts

export interface Comment {
  externalUserId?: string;
  externalUserName: string;
  text: string;
  receivedAt: Date;
  rawElement?: HTMLElement;  // reference để scroll-to nếu cần
}

export interface PlatformAdapter {
  /** Tên platform cho logging/analytics */
  readonly platform: 'facebook' | 'youtube' | 'tiktok' | 'shopee';
  
  /** Detect xem tab hiện tại có đang live không */
  detectLiveSession(): boolean;
  
  /** Lấy URL của live session hiện tại */
  getLiveUrl(): string | null;
  
  /** Đọc comments hiện có trên page (initial load) */
  readExistingComments(): Comment[];
  
  /** Attach MutationObserver để detect comment mới */
  attachCommentObserver(callback: (comment: Comment) => void): void;
  
  /** Detach observer */
  detachCommentObserver(): void;
  
  /** Tìm comment input element */
  findCommentInput(): HTMLElement | null;
  
  /** Inject overlay container vào page */
  getOverlayMountPoint(): HTMLElement;
  
  /** Execute quick paste vào comment input */
  smartPaste(text: string): Promise<SmartPasteResult>;
}

export interface SmartPasteResult {
  success: boolean;
  error?: string;   // "input_not_found" | "paste_failed" | "input_disabled"
}

export interface PlatformSelectors {
  /** CSS selectors — fetched from server, fallback to hardcoded */
  liveIndicator: string;
  chatContainer: string;
  commentItem: string;
  commentAuthor: string;
  commentText: string;
  commentInput: string;
  sendButton: string;  // CHỈ để detect vị trí, KHÔNG click
}
```

### Facebook Adapter (implement đầy đủ)

```typescript
// src/content/adapters/facebook.ts
// Đây là adapter đầu tiên, implement chi tiết nhất.
// Các adapter khác follow cùng pattern.

export class FacebookAdapter implements PlatformAdapter {
  readonly platform = 'facebook';
  private observer: MutationObserver | null = null;
  private selectors: PlatformSelectors;

  constructor(selectors?: PlatformSelectors) {
    // Default selectors, có thể override từ server
    this.selectors = selectors ?? {
      liveIndicator: '[data-testid="live_video_badge"], .x1cy8zhl',
      chatContainer: '[role="log"], [aria-label*="Comment"], [aria-label*="chat"]',
      commentItem: '[data-testid="UFI2Comment/root_depth_0"], div[class*="x1lliihq"]',
      commentAuthor: 'span.x3nfvp2 > a, span[dir="auto"] > a[role="link"]',
      commentText: 'div[dir="auto"][style]',
      commentInput: 'div[role="textbox"][contenteditable="true"]',
      sendButton: 'div[aria-label="Comment"], div[aria-label="Bình luận"]',
    };
  }

  detectLiveSession(): boolean {
    return !!document.querySelector(this.selectors.liveIndicator);
  }
  
  // ... implement all methods
}
```

**Thứ tự implement adapters:**
1. Facebook (tuần 3-4) — ưu tiên vì DOM ổn định nhất
2. YouTube (tuần 5) — YouTube Live chat có DOM tương đối standard
3. TikTok (tuần 6) — khó nhất, DOM thay đổi thường xuyên
4. Shopee (tuần 7) — ít user live trực tiếp qua web

**Với mỗi adapter, phải viết test riêng:** tạo mock HTML fixture của platform live page, test từng method.

## 2. Smart Paste Implementation

```typescript
// src/content/smart-paste.ts
// Đây là component CRITICAL nhất về mặt kỹ thuật.

export async function smartPaste(
  text: string, 
  adapter: PlatformAdapter
): Promise<SmartPasteResult> {
  // 1. Find input
  const input = adapter.findCommentInput();
  if (!input) {
    return { success: false, error: 'input_not_found' };
  }

  // 2. Focus input
  input.focus();
  await sleep(100);  // DOM needs time to process focus

  // 3. Select all existing content (to replace)
  if (input instanceof HTMLElement && input.isContentEditable) {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(input);
    selection?.removeAllRanges();
    selection?.addRange(range);
  } else if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {
    input.select();
  }

  // 4. Insert text — try multiple methods
  let inserted = false;
  
  // Method 1: execCommand (works best with React/Vue managed inputs)
  inserted = document.execCommand('insertText', false, text);
  
  if (!inserted) {
    // Method 2: ClipboardEvent
    const clipboardData = new DataTransfer();
    clipboardData.setData('text/plain', text);
    const pasteEvent = new ClipboardEvent('paste', {
      clipboardData,
      bubbles: true,
      cancelable: true,
    });
    input.dispatchEvent(pasteEvent);
    inserted = true;  // assume success, verify below
  }

  // 5. Verify text was inserted
  await sleep(200);
  const currentText = getInputText(input);
  if (!currentText.includes(text.substring(0, 20))) {
    // Method 3: Direct value set (last resort, may not trigger React state)
    if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype, 'value'
      )?.set;
      nativeInputValueSetter?.call(input, text);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  // 6. Final verify
  await sleep(100);
  const finalText = getInputText(input);
  if (!finalText.includes(text.substring(0, 20))) {
    return { success: false, error: 'paste_failed' };
  }

  // 7. Show tooltip near input
  showSendHint(input);

  return { success: true };
}

// ĐÂY LÀ RANH GIỚI KHÔNG ĐƯỢC VƯỢT:
// KHÔNG dispatch KeyboardEvent với key "Enter"
// KHÔNG trigger click vào send button
// KHÔNG simulate submit event
```

## 3. WebSocket Client

```typescript
// src/lib/ws-client.ts

export class WSClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnects = 10;
  private handlers: Map<string, Function[]> = new Map();
  private pingInterval: number | null = null;

  async connect(token: string): Promise<void> {
    const url = `${WS_URL}?token=${token}`;
    this.ws = new WebSocket(url);
    
    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startPing();
    };
    
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      this.emit(msg.type, msg);
    };
    
    this.ws.onclose = () => {
      this.stopPing();
      this.reconnect();
    };
  }

  send(type: string, data: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, ...data }));
    }
  }

  on(type: string, handler: Function): void {
    if (!this.handlers.has(type)) this.handlers.set(type, []);
    this.handlers.get(type)!.push(handler);
  }

  private reconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnects) return;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    setTimeout(() => {
      this.reconnectAttempts++;
      // re-connect...
    }, delay);
  }

  private startPing(): void {
    this.pingInterval = window.setInterval(() => {
      this.send('ping', {});
    }, 30000);
  }
}
```

## 4. Overlay UI (Preact)

Build overlay theo wireframe D2 trong tài liệu. Preact component hierarchy:

```
Overlay
├── OverlayHeader        — logo, active indicator, minimize, close, drag handle
├── StatsStrip           — duration, comments count, suggestions count
├── SuggestionCard       — current suggestion with 4 action buttons
│   ├── CommentDisplay   — user name + comment text
│   ├── ReplyPreview     — suggested reply text (editable when in edit mode)
│   └── ActionButtons    — Gửi (primary), Đọc, Sửa, Bỏ
├── HistoryList          — scrollable list of past suggestions with status
│   └── HistoryItem      — compact view with status badge
├── SessionControls      — Tạm dừng, Kết thúc session
└── OnboardingTooltip    — first-time use explanation (shown once)
```

**Keyboard shortcuts (trong overlay context):**
- `Ctrl+Enter` → trigger smart paste (nút Gửi)
- `Ctrl+Space` → TTS read (nút Đọc) — placeholder trong F4, implement logic ở F2
- `Ctrl+E` → edit mode
- `Esc` → dismiss current suggestion

**Draggable:** Overlay header là drag handle. Dùng native mousedown/mousemove, không external lib. Lưu position vào `chrome.storage.local`.

**Collapsible:** Click minimize → collapse xuống còn header + stats (60px height). Click lại → expand.

## 5. Session Lifecycle

```typescript
// Session start flow:
// 1. User click "Bắt đầu session" trong popup
// 2. Background script nhận message, verify auth
// 3. Send WS: session.start { session_id, products, persona_id }
// 4. Backend creates live_sessions row
// 5. Content script mounts overlay, attaches comment observer
// 6. Observer fires on new comment → send WS: comment.new

// Session end flow:
// 1. User click "Kết thúc session" trong overlay
// 2. Content script detaches observer
// 3. Send WS: session.end { session_id }
// 4. Backend updates live_sessions (ended_at, duration, metrics)
// 5. Show session summary (D4)
// 6. Unmount overlay
```

## Backend — WebSocket server

Implement WebSocket endpoint trong `apps/api`:

```python
# app/ws/handler.py

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    # 1. Verify JWT
    user = verify_ws_token(token)
    if not user:
        await ws.close(code=4001)
        return
    
    await ws.accept()
    
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
            
            elif msg_type == "session.start":
                session = await session_service.start(
                    shop_id=data["shop_id"],
                    user_id=user.id,
                    platform=data["platform"],
                    product_ids=data["products"],
                    persona_id=data["persona_id"]
                )
                await ws.send_json({
                    "type": "session.started",
                    "session_id": str(session.uuid)
                })
            
            elif msg_type == "comment.new":
                comment = await comment_service.ingest(data["comment"])
                # F2 sẽ thêm logic gọi LLM ở đây
                # Hiện tại chỉ lưu comment, không sinh suggestion
            
            elif msg_type == "suggestion.action":
                await suggestion_service.update_status(
                    data["suggestion_id"], data["action"]
                )
            
            elif msg_type == "session.end":
                await session_service.end(data["session_id"])
    
    except WebSocketDisconnect:
        # Cleanup: nếu session đang running, mark as interrupted
        pass
```

## Tests bắt buộc

### Unit tests
- [ ] Mỗi adapter: detectLiveSession() với mock HTML
- [ ] Mỗi adapter: readComments() với mock HTML chứa 5 comments
- [ ] Smart paste: execCommand path works
- [ ] Smart paste: ClipboardEvent fallback works
- [ ] Smart paste: input_not_found khi không có input
- [ ] WSClient: reconnect logic (exponential backoff)
- [ ] Session lifecycle: start → end → metrics calculated

### Integration tests
- [ ] Extension loads vào Chrome, popup hiển thị
- [ ] WebSocket connect → ping/pong → disconnect → reconnect
- [ ] session.start → DB row created → session.end → DB row updated

### Manual test matrix

| Platform | Detect live | Read comments | Paste works | Observer works |
|----------|------------|---------------|-------------|----------------|
| Facebook Live | [ ] | [ ] | [ ] | [ ] |
| YouTube Live | [ ] | [ ] | [ ] | [ ] |
| TikTok Live | [ ] | [ ] | [ ] | [ ] |
| Shopee Live | [ ] | [ ] | [ ] | [ ] |

## Acceptance criteria
- Extension load vào Chrome dev mode không lỗi
- Popup detect được live session trên ít nhất 2 platforms
- Overlay hiển thị đúng wireframe, draggable, collapsible
- Smart paste điền text vào comment box thành công trên ít nhất 2 platforms
- WebSocket kết nối stable, auto-reconnect khi mất mạng
```

---

# F2: AI Comment Responder

```markdown
# Task: Implement F2 — AI Comment Responder (Quick Paste Mode)

## Context

Đọc `docs/AI-Cohost-System-Design.md`:
- Phần 2.6 D2: Overlay đang hoạt động (4 action buttons, 4 trạng thái)
- Phần 3.4.7-3.4.9: bảng live_sessions, comments, suggestions
- Phần 3.6.1: RAG query cho Comment Responder
- Phần 4.5.1: Comment Responder Realtime Flow (13 bước)
- Phần 4.5.2: Quick Paste Flow (10 bước)

**Dependencies:** F6, F1, F4 phải xong trước. Đây là feature QUAN TRỌNG NHẤT — core value proposition.

## Scope

F2 gồm:
1. Comment ingestion pipeline (extension → WS → DB)
2. Intent classification (question/complaint/praise/spam/greeting)
3. RAG retrieval (pgvector query)
4. LLM suggestion generation (streaming)
5. Suggestion delivery (WS → extension overlay)
6. Suggestion status tracking (sent/pasted_not_sent/read/dismissed)
7. Response caching
8. TTS generation cho "Đọc" button
9. "Lưu làm FAQ" flow từ edit mode

## Critical Path — Target: dưới 3 giây end-to-end

```
Comment xuất hiện trên live  [T+0ms]
    ↓
Extension detect via MutationObserver  [T+100ms]
    ↓
WebSocket send comment.new  [T+150ms]
    ↓
Backend receive, save to DB  [T+200ms]
    ↓
Check cache (Redis) — HIT → return cached  [T+250ms → DONE]
    ↓ MISS
Classify intent (inline, no LLM call)  [T+300ms]
    ↓
Embed comment (Gemini embedding API)  [T+500ms]
    ↓
pgvector query: top 2 products + top 3 FAQs  [T+550ms]
    ↓
Build prompt with persona + RAG + history  [T+600ms]
    ↓
Call Gemini Flash (streaming)  [T+600ms → T+2500ms]
    ↓
First token arrives, stream to extension  [T+900ms]
    ↓
Full response complete  [T+2500ms]
    ↓
Save suggestion to DB  [T+2600ms]
    ↓
Extension renders suggestion  [T+2700ms]
```

## Backend Implementation

### 1. Comment ingestion (thêm vào WS handler đã có từ F4)

```python
# Trong ws handler, khi nhận comment.new:

elif msg_type == "comment.new":
    comment_data = data["comment"]
    session_id = data["session_id"]
    
    # 1. Save comment to DB
    comment = await comment_service.create(
        session_id=session_id,
        shop_id=current_shop_id,
        external_user_id=comment_data.get("externalUserId"),
        external_user_name=comment_data["externalUserName"],
        text=comment_data["text"]
    )
    
    # 2. Check cache
    cache_key = f"suggestion:{current_shop_id}:{hash(comment_data['text'][:100])}"
    cached = await redis.get(cache_key)
    if cached:
        suggestion = json.loads(cached)
        await ws.send_json({"type": "suggestion.new", "suggestion": suggestion})
        return
    
    # 3. Enqueue LLM task (high priority)
    generate_suggestion.apply_async(
        args=[comment.id, session_id, current_shop_id],
        queue="llm_queue",
        priority=0  # highest
    )
```

### 2. Intent classification (fast, no LLM)

```python
# Dùng keyword matching + simple heuristics, KHÔNG gọi LLM (quá chậm)

class IntentClassifier:
    GREETING_PATTERNS = ["chào", "hi", "hello", "shop ơi", "xin chào"]
    THANKS_PATTERNS = ["cảm ơn", "thanks", "tks", "cam on", "xinh quá", "đẹp quá"]
    PRICING_PATTERNS = ["giá", "bao nhiêu", "bn", "giảm giá", "khuyến mãi", "sale", "mã"]
    SHIPPING_PATTERNS = ["ship", "giao hàng", "vận chuyển", "cod", "freeship"]
    SPAM_PATTERNS = ["http://", "https://", "@@", "###"]
    
    def classify(self, text: str) -> tuple[str, float]:
        text_lower = text.lower().strip()
        
        # Check spam first
        if any(p in text_lower for p in self.SPAM_PATTERNS) or len(text_lower) > 500:
            return ("spam", 0.9)
        
        if len(text_lower) < 3 or text_lower.count("🎉") > 3:
            return ("praise", 0.7)  # emoji flood = praise/excitement
        
        if any(p in text_lower for p in self.GREETING_PATTERNS):
            return ("greeting", 0.8)
        
        if any(p in text_lower for p in self.THANKS_PATTERNS):
            return ("thanks", 0.8)
        
        if any(p in text_lower for p in self.PRICING_PATTERNS):
            return ("pricing", 0.8)
        
        if any(p in text_lower for p in self.SHIPPING_PATTERNS):
            return ("shipping", 0.8)
        
        if "?" in text or any(w in text_lower for w in ["không", "có", "sao", "thế nào", "bao lâu"]):
            return ("question", 0.7)
        
        return ("other", 0.5)
```

**Chỉ sinh suggestion cho:** question, pricing, shipping, complaint. KHÔNG sinh cho: greeting, thanks, praise, spam (lãng phí LLM tokens).

### 3. RAG retrieval

Implement đúng query trong Phần 3.6.1 của tài liệu:

```python
class RAGService:
    async def get_context(
        self, 
        comment_text: str, 
        shop_id: int, 
        active_product_ids: list[int]
    ) -> RAGContext:
        # 1. Embed comment text (dùng RETRIEVAL_QUERY task type)
        query_embedding = await self.embedding_client.embed(
            comment_text, task_type="RETRIEVAL_QUERY"
        )
        
        # 2. Execute pgvector CTE query (xem Phần 3.6.1)
        result = await self.db.execute(RAG_QUERY, {
            "embedding": query_embedding,
            "shop_id": shop_id,
            "product_ids": active_product_ids
        })
        
        products = result["products"] or []
        faqs = result["faqs"] or []
        
        return RAGContext(products=products, faqs=faqs)
```

### 4. LLM suggestion generation (Celery task, streaming)

```python
@celery.task(queue="llm_queue", max_retries=2, soft_time_limit=30)
def generate_suggestion(comment_id: int, session_id: int, shop_id: int):
    # 1. Fetch comment, session, persona from DB
    comment = sync_get(comment_id)
    session = sync_get_session(session_id)
    persona = sync_get_persona(session.persona_id)
    
    # 2. Classify intent
    intent, confidence = classifier.classify(comment.text)
    sync_update_comment(comment_id, intent=intent, confidence=confidence)
    
    # 3. Skip non-actionable intents
    if intent in ("greeting", "thanks", "praise", "spam"):
        return  # không sinh suggestion
    
    # 4. Get RAG context
    rag_context = sync_get_rag_context(comment.text, shop_id, session.active_product_ids)
    
    # 5. Get conversation history từ Redis (last 5 Q&A)
    history = sync_get_history(session_id, limit=5)
    
    # 6. Build prompt
    prompt = build_comment_prompt(
        persona=persona,
        comment=comment,
        rag_context=rag_context,
        history=history
    )
    
    # 7. Call LLM with streaming
    full_response = ""
    start_time = time.time()
    
    for chunk in llm_client.stream(prompt, model="gemini-2.0-flash"):
        full_response += chunk
        # Publish chunk to Redis pub/sub cho WS server
        redis.publish(f"suggestion_stream:{session_id}", json.dumps({
            "type": "suggestion.stream",
            "comment_id": comment_id,
            "chunk": chunk
        }))
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    # 8. Save suggestion to DB
    suggestion = sync_create_suggestion(
        comment_id=comment_id,
        session_id=session_id,
        shop_id=shop_id,
        text=full_response,
        llm_model="gemini-2.0-flash",
        latency_ms=latency_ms,
        rag_product_ids=[p["id"] for p in rag_context.products],
        rag_faq_ids=[f["id"] for f in rag_context.faqs]
    )
    
    # 9. Publish completion
    redis.publish(f"suggestion_stream:{session_id}", json.dumps({
        "type": "suggestion.complete",
        "suggestion_id": suggestion.id,
        "suggestion": suggestion.to_dict()
    }))
    
    # 10. Cache for similar comments
    cache_key = f"suggestion:{shop_id}:{hash(comment.text[:100])}"
    redis.setex(cache_key, 300, json.dumps(suggestion.to_dict()))  # 5 min TTL
    
    # 11. Update session metrics
    sync_increment_session_metrics(session_id, suggestions_count=1)
    
    # 12. Save to conversation history in Redis
    redis.lpush(f"history:{session_id}", json.dumps({
        "question": comment.text,
        "answer": full_response
    }))
    redis.ltrim(f"history:{session_id}", 0, 4)  # keep last 5
```

### 5. Prompt template

```python
COMMENT_RESPONDER_PROMPT = """Bạn là {persona_name}, trợ lý bán hàng livestream.

PHONG CÁCH:
{persona_tone}
{persona_quirks}

SẢN PHẨM ĐANG BÁN:
{product_context}

FAQ LIÊN QUAN:
{faq_context}

CUỘC TRÒ CHUYỆN GẦN ĐÂY:
{history_context}

KHÁCH VỪA HỎI: "{comment_text}"

QUY TẮC BẮT BUỘC:
1. Trả lời ngắn gọn, dưới 40 từ, bằng tiếng Việt
2. Thân thiện, dùng phong cách đã cho ở trên
3. KHÔNG bịa thông tin sản phẩm — chỉ dùng thông tin trong FAQ và mô tả
4. Nếu không biết câu trả lời, nói "Để em check rồi báo lại ạ"
5. KHÔNG đề cập giá cụ thể trừ khi giá có trong thông tin sản phẩm
6. KHÔNG hứa hẹn về khuyến mãi, giảm giá trừ khi được nêu rõ trong dữ liệu

CHỈ trả lời nội dung reply, không thêm prefix hay label."""
```

**QUAN TRỌNG:** Prompt phải có rule "KHÔNG bịa thông tin" và "KHÔNG đề cập giá nếu không có data". Đây là safety net quan trọng nhất.

### 6. WS server subscribe Redis pub/sub

```python
# Trong WS handler, sau khi session started:
# Subscribe Redis channel cho session_id

async def listen_suggestions(ws: WebSocket, session_id: str):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"suggestion_stream:{session_id}")
    
    async for message in pubsub.listen():
        if message["type"] == "message":
            await ws.send_text(message["data"])
```

Dùng `asyncio.create_task` để chạy listener song song với message handler.

## Frontend — Extension Updates

### Overlay nhận streaming suggestion

```typescript
// Trong overlay Preact component:

wsClient.on('suggestion.stream', (msg) => {
  // Append chunk to current suggestion text
  setSuggestionText(prev => prev + msg.chunk);
});

wsClient.on('suggestion.complete', (msg) => {
  // Finalize suggestion, enable action buttons
  setCurrentSuggestion(msg.suggestion);
  setIsStreaming(false);
});
```

### Action button handlers

```typescript
const handleSend = async () => {
  const result = await adapter.smartPaste(currentSuggestion.text);
  if (result.success) {
    // Start observing for comment sent
    observeCommentSent(currentSuggestion.id, currentSuggestion.text);
    wsClient.send('suggestion.action', { 
      suggestion_id: currentSuggestion.id, 
      action: 'sent' 
    });
  } else {
    // Fallback: copy to clipboard
    navigator.clipboard.writeText(currentSuggestion.text);
    showToast("Đã copy. Paste vào ô comment và nhấn Enter.");
  }
};

const handleRead = async () => {
  // Call TTS API, play audio
  const audioUrl = await api.generateTTS(currentSuggestion.text);
  const audio = new Audio(audioUrl);
  audio.play();
  wsClient.send('suggestion.action', {
    suggestion_id: currentSuggestion.id,
    action: 'read'
  });
};

const handleEdit = () => {
  setIsEditing(true);
  setEditText(currentSuggestion.text);
};

const handleDismiss = () => {
  wsClient.send('suggestion.action', {
    suggestion_id: currentSuggestion.id,
    action: 'dismissed'
  });
  moveToNextComment();
};
```

### "Lưu làm FAQ" flow

```typescript
// Trong edit mode, khi user check "Lưu làm FAQ cho sản phẩm này"
const handleSaveEdit = async () => {
  // 1. Update suggestion text
  wsClient.send('suggestion.action', {
    suggestion_id: currentSuggestion.id,
    action: 'edited',
    edited_text: editText
  });
  
  // 2. Nếu checkbox checked, tạo FAQ mới
  if (saveAsFaq && selectedProductId) {
    await api.createFaq(selectedProductId, {
      question: currentComment.text,
      answer: editText,
      source: 'learned'  // đánh dấu FAQ học từ user
    });
    showToast("Đã lưu FAQ. AI sẽ trả lời tốt hơn lần sau!");
  }
  
  // 3. Execute smart paste with edited text
  await adapter.smartPaste(editText);
};
```

## TTS Integration

```python
# Backend endpoint
@router.post("/api/tts/generate")
async def generate_tts(text: str = Body(...), shop: Shop = Depends(get_current_shop)):
    # 1. Check quota
    # 2. Call Google Cloud TTS
    from google.cloud import texttospeech
    
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="vi-VN",
        name="vi-VN-Neural2-A"  # Female voice
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    
    # 3. Upload to R2
    audio_url = await r2.upload(response.audio_content, "audio/mp3")
    
    # 4. Track usage
    await usage_svc.track(shop.id, "tts_chars", len(text), "chars")
    
    return {"audio_url": audio_url}
```

## Tests bắt buộc

### Unit tests
- [ ] Intent classifier: 20 test cases bao gồm edge cases tiếng Việt
- [ ] Prompt builder: verify đúng format, không miss context
- [ ] RAG query: verify return products + FAQs khi có data
- [ ] RAG query: verify empty result khi không match
- [ ] Cache: hit trên comment giống nhau trong 5 phút
- [ ] Cache: miss sau 5 phút hoặc khác comment
- [ ] Suggestion status update: all 4 statuses work

### Integration tests
- [ ] Full flow: comment → classify → RAG → LLM → suggestion saved
- [ ] Streaming: chunks arrive in order, complete event fires
- [ ] Fallback: Gemini fail → DeepSeek V3 picks up
- [ ] Rate limit: >30 comments/phút → reject gracefully
- [ ] "Lưu làm FAQ": FAQ created with source='learned', embedding generated

### Manual test checklist
- [ ] Hỏi "giá bao nhiêu" → AI trả lời có giá (nếu product có giá)
- [ ] Hỏi "ship cod được không" → AI trả lời về shipping
- [ ] Gửi emoji "🎉🎉🎉" → AI KHÔNG sinh suggestion (praise)
- [ ] Gửi "chào shop" → AI KHÔNG sinh suggestion (greeting)
- [ ] Edit suggestion + check "Lưu FAQ" → FAQ xuất hiện trong product detail
- [ ] TTS: click Đọc → audio phát qua speaker

## Acceptance criteria
- End-to-end latency dưới 3 giây (p50) cho suggestion delivery
- AI KHÔNG bịa thông tin sản phẩm (verified qua 50 test comments)
- Cache hit rate >30% trong session dài (>30 phút)
- Smart paste success rate >90% trên Facebook Live
- 4 trạng thái suggestion tracking correct
```

---

# F3: Script Generator

```markdown
# Task: Implement F3 — Script Generator

## Context

Đọc `docs/AI-Cohost-System-Design.md`:
- Phần 2.5 (C4 — Scripts Library, C5 — Script Generator/Editor)
- Phần 3.4.10: bảng scripts
- Phần 3.4.11: bảng script_samples
- Phần 3.6.2: Few-shot query
- Phần 4.5.3: Script Generation Flow (13 bước)

**Dependencies:** F6 (Auth), F1 (Products) phải xong. Không phụ thuộc F4 hay F2.

## Scope

F3 gồm:
1. Script generation backend (LLM + RAG few-shot)
2. Script CRUD
3. Script Generator UI (split view)
4. Scripts Library UI (grid view)
5. Export (PDF, Markdown, plain text)
6. Script version tracking

## Backend — apps/api

### Endpoints

```
GET    /api/scripts              — list scripts (paginated, filterable)
POST   /api/scripts/generate     — generate new script (async, returns job_id)
GET    /api/scripts/:id          — get script
PATCH  /api/scripts/:id          — update script (user edits)
DELETE /api/scripts/:id          — delete script
POST   /api/scripts/:id/regenerate  — regenerate keeping config
GET    /api/scripts/:id/export/:format  — export (pdf/md/txt)
```

### Script generation service

```python
class ScriptGenerationService:
    async def generate(self, shop_id: int, user_id: int, config: ScriptConfig) -> str:
        """Returns job_id. Actual generation happens in Celery."""
        
        # 1. Check quota
        quota = await usage_svc.check_quota(shop_id, "scripts")
        if quota.remaining <= 0:
            raise QuotaExceeded("Bạn đã hết lượt tạo script trong tháng")
        
        # 2. Fetch products
        products = await product_repo.get_by_ids(config.product_ids, shop_id=shop_id)
        if not products:
            raise ValueError("Chưa chọn sản phẩm nào")
        
        # 3. Fetch persona
        persona = await persona_repo.get(config.persona_id, shop_id=shop_id)
        
        # 4. Enqueue
        job = generate_script_task.apply_async(
            args=[shop_id, user_id, config.dict(), [p.dict() for p in products], persona.dict()],
            queue="script_queue"
        )
        
        return job.id
```

### Celery task

```python
@celery.task(queue="script_queue", soft_time_limit=120)
def generate_script_task(shop_id, user_id, config, products, persona):
    """
    Flow theo Phần 4.5.3 của tài liệu.
    """
    
    # 1. Get few-shot examples from script_samples (pgvector query Phần 3.6.2)
    # Build query embedding từ product names + category
    query_text = " ".join([p["name"] for p in products]) + " " + (products[0].get("category") or "")
    query_embedding = sync_embed(query_text, task_type="RETRIEVAL_QUERY")
    
    samples = sync_query_script_samples(
        embedding=query_embedding,
        category=products[0].get("category"),
        persona_style=persona.get("tone"),
        limit=3
    )
    
    # 2. Build long prompt
    prompt = build_script_prompt(
        persona=persona,
        products=products,
        samples=samples,
        duration_minutes=config["duration_target"],
        tone=config["tone"],
        special_notes=config.get("special_notes")
    )
    
    # 3. Call LLM (Claude Haiku cho quality, hoặc Gemini Flash cho speed)
    model = "claude-haiku" if config["duration_target"] >= 20 else "gemini-2.0-flash"
    
    full_response = ""
    for chunk in llm_client.stream(prompt, model=model, max_tokens=4000):
        full_response += chunk
        # Stream to frontend via Redis pub/sub
        redis.publish(f"script_gen:{shop_id}", json.dumps({
            "type": "script.chunk",
            "job_id": generate_script_task.request.id,
            "chunk": chunk
        }))
    
    # 4. Post-process
    word_count = len(full_response.split())
    estimated_duration = word_count / 150 * 60  # 150 words/min → seconds
    cta_count = count_ctas(full_response)
    
    # 5. Save
    script = sync_create_script(
        shop_id=shop_id,
        created_by=user_id,
        title=generate_title(products, config),
        content=full_response,
        product_ids=config["product_ids"],
        persona_id=config.get("persona_id"),
        duration_target=config["duration_target"],
        tone=config["tone"],
        special_notes=config.get("special_notes"),
        word_count=word_count,
        estimated_duration_seconds=int(estimated_duration),
        cta_count=cta_count,
        llm_model=model,
        prompt_version="v1"
    )
    
    # 6. Track usage
    sync_track_usage(shop_id, "scripts", 1, "count")
    
    # 7. Publish completion
    redis.publish(f"script_gen:{shop_id}", json.dumps({
        "type": "script.complete",
        "job_id": generate_script_task.request.id,
        "script_id": script.id
    }))
```

### Prompt template

```python
SCRIPT_GENERATION_PROMPT = """Bạn là {persona_name}, một host livestream bán hàng chuyên nghiệp tại Việt Nam.

PHONG CÁCH CỦA BẠN:
- Tone: {tone}
- Đặc điểm: {persona_quirks}
- Cách xưng hô: {persona_phrases}

SẢN PHẨM CẦN GIỚI THIỆU:
{products_detail}

CÁC SCRIPT MẪU THAM KHẢO (để học phong cách, KHÔNG copy nội dung):
---
{sample_1}
---
{sample_2}
---
{sample_3}
---

YÊU CẦU:
Viết kịch bản livestream bán hàng {duration} phút với cấu trúc:

# Mở đầu (30 giây)
- Chào đón người xem, tạo không khí
- Nhắc follow và like

# Giới thiệu sản phẩm (chiếm 60% thời lượng)
- Giới thiệu từng sản phẩm với highlights
- Kết hợp storytelling thực tế
- Nhấn mạnh lợi ích cho khách hàng

# Xử lý phản đối (10%)
- Trả lời trước các câu hỏi hay gặp
- So sánh giá trị (không so sánh với đối thủ)

# Call to Action (10%)
- Tạo urgency (giới hạn thời gian/số lượng)
- Hướng dẫn cách đặt hàng
- Nhắc lại ưu đãi

# Kết thúc (30 giây)
- Cảm ơn người xem
- Nhắc lịch live tiếp theo

{special_notes_section}

QUY TẮC:
1. Viết bằng tiếng Việt tự nhiên
2. KHÔNG bịa thông tin sản phẩm — chỉ dùng dữ liệu đã cho
3. KHÔNG so sánh với sản phẩm/brand đối thủ
4. KHÔNG hứa giảm giá/khuyến mãi trừ khi có trong dữ liệu
5. Giữ đúng phong cách persona
6. Dùng heading markdown (#) cho mỗi section"""
```

### PDF Export

```python
@router.get("/api/scripts/{script_id}/export/pdf")
async def export_pdf(script_id: int, shop: Shop = Depends(get_current_shop)):
    script = await script_repo.get(script_id, shop_id=shop.id)
    
    # Convert markdown to PDF using markdown2 + weasyprint
    html = markdown2.markdown(script.content)
    styled_html = f"""
    <html>
    <head><style>
        body {{ font-family: 'Be Vietnam Pro', sans-serif; padding: 40px; }}
        h1 {{ color: #5B47E0; }}
        h2 {{ color: #2E75B6; }}
    </style></head>
    <body>
        <h1>{script.title}</h1>
        <p style="color: #888;">Tạo bởi AI Co-host • {script.word_count} từ • ~{script.estimated_duration_seconds // 60} phút</p>
        <hr/>
        {html}
    </body>
    </html>
    """
    
    pdf_bytes = weasyprint.HTML(string=styled_html).write_pdf()
    return Response(content=pdf_bytes, media_type="application/pdf")
```

## Frontend — apps/dashboard

### C4. Scripts Library (`/scripts`)

- Grid layout 2 columns (desktop), 1 column (mobile)
- Each card: title, persona badge, word count, duration estimate, 3-line preview, created_at
- Actions: Mở, Sao chép, Xóa
- Filters: product, persona, duration range
- Search: full-text trong title
- Empty state: "Chưa có script nào. Tạo script đầu tiên để bắt đầu!"
- Nút "+ Tạo script mới" prominent ở top right

### C5. Script Generator (`/scripts/new` và `/scripts/:id`)

**Split view:**

Left panel (30%): `ScriptConfigPanel`
- Product selector: multi-select dropdown với search, max 5
- Persona selector: radio cards với preview text
- Duration: radio buttons (5/10/20/30 phút)
- Tone: radio buttons (chuyên nghiệp/thân thiện/vui vẻ)
- Special notes: textarea (optional)
- Nút "⚡ Sinh script" (disabled khi chưa chọn product)

Right panel (70%): `ScriptContentPanel`
- Khi chưa generate: empty state "Chọn sản phẩm và nhấn Sinh script"
- Khi đang generate: streaming text, typing animation cursor, "Đang tạo script..." indicator
- Khi xong: editable content area (rich text hoặc markdown editor)
- Stats card bottom: word count, duration, CTA count
- Action buttons: "Sinh lại" (keep config), "Copy" (clipboard), "PDF" (download)

**State management:**
```typescript
interface ScriptGenState {
  config: ScriptConfig;
  content: string;
  isGenerating: boolean;
  jobId: string | null;
  stats: { wordCount: number; duration: number; ctaCount: number } | null;
  isDirty: boolean;  // user edited content
}
```

**WebSocket subscription cho streaming:**
```typescript
useEffect(() => {
  if (!jobId) return;
  
  wsClient.on('script.chunk', (msg) => {
    if (msg.job_id === jobId) {
      setContent(prev => prev + msg.chunk);
    }
  });
  
  wsClient.on('script.complete', (msg) => {
    if (msg.job_id === jobId) {
      setIsGenerating(false);
      router.push(`/scripts/${msg.script_id}`);
    }
  });
}, [jobId]);
```

## Seed Data — Script Samples

Tạo 20 script samples chất lượng cao trong migration/seed:
- 4 per category × 5 categories (mỹ phẩm, thời trang, gia dụng, TPCN, mẹ bé)
- Mỗi sample: 800-1500 từ
- Mix persona styles: 2 thân thiện, 1 năng động, 1 chuyên nghiệp per category
- Quality score = 5 cho tất cả seed data
- Embed tất cả samples vào pgvector

**Viết nội dung samples bằng tiếng Việt tự nhiên**, giống thật với cách host VN live trên TikTok/Shopee. KHÔNG viết kiểu robot.

## Tests bắt buộc

### Unit tests
- [ ] Prompt builder: tất cả placeholders được fill
- [ ] Post-process: word count, duration estimate, CTA count accurate
- [ ] Title generation từ products + config
- [ ] PDF export: valid PDF output
- [ ] Quota check: exceed → reject

### Integration tests
- [ ] Generate script → DB row created → correct fields
- [ ] Streaming: chunks arrive, complete fires
- [ ] Few-shot query: returns relevant samples cho category
- [ ] Export PDF: downloadable, content matches

### Manual test checklist
- [ ] Generate script 10 phút cho mỹ phẩm → content hợp lý, tiếng Việt tự nhiên
- [ ] Edit script → save → reload → content preserved
- [ ] Export PDF → mở được, format đẹp
- [ ] Copy button → clipboard có content
- [ ] "Sinh lại" giữ config, content mới

## Acceptance criteria
- Generate xong trong dưới 30 giây
- Script 500-1500 từ tùy duration setting
- Tiếng Việt tự nhiên, không robotic
- PDF export đẹp, có branding
- Quota enforcement chính xác
```

---

# F5: Dashboard Analytics

```markdown
# Task: Implement F5 — Dashboard Analytics

## Context

Đọc `docs/AI-Cohost-System-Design.md`:
- Phần 2.5 (C1 — Dashboard Home, C6 — Session Detail)
- Phần 3.4.7: bảng live_sessions (aggregated metrics)
- Phần 3.4.9: bảng suggestions (status tracking)
- Phần 3.4.16: bảng usage_logs
- Phần 3.6.3: Monthly usage aggregation query

**Dependencies:** F6, F1, F4, F2 phải xong trước. F5 cần data thực từ sessions và suggestions.

## Scope

F5 gồm:
1. Dashboard Home (C1) — overview widgets, quick actions, recent sessions
2. Session Detail (C6b) — deep dive vào 1 session
3. Usage tracking dashboard (E2 billing page usage meters)
4. Backend analytics queries
5. Real-time stats update via WebSocket

## Backend — apps/api

### Endpoints

```
GET  /api/analytics/overview         — dashboard home stats
GET  /api/analytics/sessions         — sessions list (paginated)
GET  /api/analytics/sessions/:id     — session detail với stats
GET  /api/analytics/sessions/:id/comments  — all comments with suggestions
GET  /api/analytics/sessions/:id/chart     — comments per minute data
GET  /api/analytics/sessions/:id/products  — product mention breakdown
GET  /api/analytics/sessions/:id/top-questions — top FAQ from session
GET  /api/analytics/sessions/:id/export    — CSV export
GET  /api/analytics/usage            — monthly usage summary
```

### Overview query

```python
class AnalyticsService:
    async def get_overview(self, shop_id: int) -> OverviewStats:
        # Current month stats
        month_start = date.today().replace(day=1)
        
        # 1. Live hours this month
        live_hours = await db.scalar(
            select(func.sum(live_sessions.c.duration_seconds))
            .where(live_sessions.c.shop_id == shop_id)
            .where(live_sessions.c.started_at >= month_start)
        ) or 0
        live_hours = live_hours / 3600
        
        # 2. Comments handled
        comments_count = await db.scalar(
            select(func.count())
            .select_from(comments)
            .join(live_sessions)
            .where(live_sessions.c.shop_id == shop_id)
            .where(comments.c.created_at >= month_start)
        ) or 0
        
        # 3. Suggestion used rate
        suggestion_stats = await db.execute(
            select(
                func.count().label("total"),
                func.count().filter(suggestions.c.status == "sent").label("sent")
            )
            .where(suggestions.c.shop_id == shop_id)
            .where(suggestions.c.created_at >= month_start)
        )
        row = suggestion_stats.first()
        used_rate = (row.sent / row.total * 100) if row.total > 0 else 0
        
        # 4. Scripts created
        scripts_count = await db.scalar(
            select(func.count())
            .where(scripts.c.shop_id == shop_id)
            .where(scripts.c.created_at >= month_start)
        ) or 0
        
        # 5. Recent sessions (last 5)
        recent = await session_repo.list(
            shop_id=shop_id, limit=5, order_by="started_at desc"
        )
        
        # 6. Plan usage
        usage = await usage_service.get_monthly_summary(shop_id)
        
        return OverviewStats(
            live_hours=round(live_hours, 1),
            comments_count=comments_count,
            used_rate=round(used_rate, 1),
            scripts_count=scripts_count,
            recent_sessions=recent,
            usage=usage
        )
```

### Session detail query

```python
async def get_session_detail(self, session_id: int, shop_id: int) -> SessionDetail:
    session = await session_repo.get(session_id, shop_id=shop_id)
    
    # Comments per minute chart data
    chart_data = await db.execute(text("""
        SELECT 
            date_trunc('minute', received_at) AS minute,
            COUNT(*) AS comment_count
        FROM comments
        WHERE session_id = :session_id
        GROUP BY date_trunc('minute', received_at)
        ORDER BY minute
    """), {"session_id": session_id})
    
    # Product mentions (count comments mentioning each product by RAG match)
    product_mentions = await db.execute(text("""
        SELECT 
            p.name,
            COUNT(*) as mention_count
        FROM suggestions s
        CROSS JOIN LATERAL unnest(s.rag_product_ids) AS pid
        JOIN products p ON p.id = pid
        WHERE s.session_id = :session_id
        GROUP BY p.name
        ORDER BY mention_count DESC
    """), {"session_id": session_id})
    
    # Top questions (most common intents)
    top_questions = await db.execute(text("""
        SELECT text, intent, COUNT(*) OVER (PARTITION BY intent) as intent_count
        FROM comments
        WHERE session_id = :session_id
          AND intent IN ('question', 'pricing', 'shipping')
        ORDER BY received_at DESC
        LIMIT 10
    """), {"session_id": session_id})
    
    return SessionDetail(
        session=session,
        chart_data=chart_data.fetchall(),
        product_mentions=product_mentions.fetchall(),
        top_questions=top_questions.fetchall()
    )
```

### CSV Export

```python
@router.get("/api/analytics/sessions/{session_id}/export")
async def export_session_csv(session_id: int, shop: Shop = Depends(get_current_shop)):
    comments_with_suggestions = await db.execute(text("""
        SELECT 
            c.received_at,
            c.external_user_name,
            c.text AS comment_text,
            c.intent,
            s.text AS suggestion_text,
            s.status AS suggestion_status,
            s.latency_ms
        FROM comments c
        LEFT JOIN suggestions s ON s.comment_id = c.id
        WHERE c.session_id = :session_id
        ORDER BY c.received_at
    """), {"session_id": session_id})
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Thời gian", "Người hỏi", "Comment", "Loại", "Gợi ý AI", "Trạng thái", "Latency (ms)"])
    for row in comments_with_suggestions:
        writer.writerow(row)
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session-{session_id}.csv"}
    )
```

## Frontend — apps/dashboard

### C1. Dashboard Home (`/dashboard`)

**Components:**
- `WelcomeSection` — "Chào {name} 👋"
- `QuickActions` — 3 action cards (Bắt đầu live, Tạo script, Tạo DH video)
- `MonthlyStats` — 4 metric cards (live hours, comments, used rate, scripts)
- `UsageMeter` — plan name + progress bar "48/100 giờ"
- `RecentSessions` — list 5 sessions gần nhất
- `DailyTip` — educational content (hardcoded tạm, sau có CMS)

**Real-time:** Khi có session đang running (WebSocket event), hiện banner "🔴 Đang live trên Facebook" với link vào session.

### C6b. Session Detail (`/sessions/:id`)

**Components:**
- `SessionHeader` — platform icon, datetime, duration
- `StatCards` — 5 cards (duration, comments, suggestions, used rate, avg latency)
- `CommentsChart` — Recharts AreaChart, comments per minute
- `ProductMentions` — Recharts PieChart hoặc horizontal BarChart
- `TopQuestions` — numbered list top 10 câu hỏi
- `TranscriptLink` — "Xem toàn bộ transcript" → modal hoặc separate page
- `ExportButton` — CSV download

**Chart interaction:**
- Hover trên chart point → tooltip "20:15 — 45 comments"
- Click vào chart point → scroll transcript đến thời điểm đó

### C6a. Sessions List (`/sessions`)

- Platform filter tabs: Tất cả / Facebook / TikTok / YouTube / Shopee
- Date range filter
- Session cards (not table — cards work better for this data density)

## Tests bắt buộc

### Unit tests
- [ ] Overview stats calculation correct với test data
- [ ] Used rate calculation: 0 suggestions → 0%, all sent → 100%
- [ ] CSV export: valid CSV, correct headers, correct data
- [ ] Chart data: minutes properly bucketed

### Integration tests
- [ ] Create session + 100 comments + 80 suggestions → overview stats correct
- [ ] Session detail chart shows correct comment distribution
- [ ] Product mentions match actual RAG results
- [ ] CSV export matches DB data

### Manual test checklist
- [ ] Dashboard home loads dưới 2 giây
- [ ] Charts render mượt với >1000 data points
- [ ] CSV download works, mở được trong Excel
- [ ] Session list filter by platform works
- [ ] Empty state khi chưa có sessions
- [ ] Usage meter matches billing page numbers

## Acceptance criteria
- Dashboard home load dưới 2 giây
- Chart render mượt
- Stats accurate so với raw data
- CSV export mở được trong Excel/Google Sheets
- Tiếng Việt headers trong CSV
```

---

# Tóm tắt thứ tự và dependencies

```
Tuần 1-2:   F6 (Auth skeleton + login + signup + onboarding UI)
Tuần 2-3:   F6 (Billing + team) + F1 (Product CRUD backend)
Tuần 3-4:   F1 (Product UI + AI gen + embedding) + F4 (Extension skeleton + FB adapter)
Tuần 5:     F4 (YouTube + TikTok adapters + overlay UI)
Tuần 6:     F2 (Comment Responder backend + RAG + LLM integration)
Tuần 7:     F2 (Frontend integration + Quick Paste) + F4 (Shopee adapter)
Tuần 8:     F3 (Script Generator backend + frontend)
Tuần 9:     F3 (Polish + export) + F5 (Analytics backend)
Tuần 10:    F5 (Dashboard UI + charts) + F6 (Billing go-live)
```

Mỗi prompt ở trên là self-contained — copy vào Claude Code khi bắt đầu feature đó. Claude Code sẽ đọc tài liệu thiết kế, propose plan, chờ approve, rồi implement.
