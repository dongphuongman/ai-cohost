# AI CO-HOST
## Trợ lý AI cho Livestream Bán hàng

**TÀI LIỆU THIẾT KẾ HỆ THỐNG**
*System Design Document — MVP v1.0*

Bao gồm:
- Thiết kế màn hình UI/UX
- Thiết kế cơ sở dữ liệu
- Thiết kế kiến trúc hệ thống

*Phiên bản 1.0 — Tháng 4, 2026*
*Tài liệu nội bộ*

---

## Mục lục

- [Phần 1: Tổng quan sản phẩm](#phần-1-tổng-quan-sản-phẩm)
- [Phần 2: Thiết kế màn hình UI/UX](#phần-2-thiết-kế-màn-hình-uiux)
- [Phần 3: Thiết kế cơ sở dữ liệu](#phần-3-thiết-kế-cơ-sở-dữ-liệu)
- [Phần 4: Thiết kế kiến trúc hệ thống](#phần-4-thiết-kế-kiến-trúc-hệ-thống)
- [Phụ lục](#phụ-lục)

---

# Phần 1: Tổng quan sản phẩm

## 1.1. Giới thiệu

AI Co-host là SaaS B2B giúp shop owner tại Việt Nam bán hàng hiệu quả hơn khi livestream trên các nền tảng TikTok Live, Shopee Live, Facebook Live và YouTube Live. Sản phẩm đóng vai trò trợ lý AI realtime, không thay thế người host thật.

Ba giá trị cốt lõi mà shop owner nhận được:

1. Đọc comment từ live và gợi ý câu trả lời trong dưới 3 giây — host không bỏ sót khách hàng
2. Sinh kịch bản live chuyên nghiệp từ thông tin sản phẩm trong vài phút
3. Sinh video digital human cho các đoạn giới thiệu sản phẩm (phase 2)

## 1.2. Đối tượng người dùng

Shop owner SMB Việt Nam, team 1-10 người, đang livestream bán hàng thường xuyên trên ít nhất một nền tảng. Các ngành hàng ưu tiên: mỹ phẩm, thời trang, đồ gia dụng, thực phẩm chức năng, mẹ và bé.

## 1.3. Nguyên tắc thiết kế cốt lõi

### AI là trợ lý, không phải bot thay thế

Mọi câu trả lời đều do host duyệt và gửi đi. AI chỉ gợi ý, không tự post lên platform. Điều này đảm bảo an toàn về mặt ToS của platform, pháp lý, và xây dựng niềm tin với shop owner.

### Quick Paste Mode thay vì Copy-Paste thủ công

Khi host click nút Gửi trong overlay, extension tự động paste text vào ô comment của platform, sau đó host chỉ cần nhấn Enter để gửi. Action cuối cùng vẫn là keystroke của con người, đảm bảo an toàn với anti-bot.

### Tiếng Việt là ngôn ngữ chính

Mọi label, error message, placeholder đều tiếng Việt tự nhiên. Tone thân thiện dùng "bạn" thay vì "quý khách".

### Disclose AI-generated content

Video digital human và voice clone đều có watermark hoặc disclosure rõ ràng. Tuân thủ Luật Quảng cáo Việt Nam và các quy định về AI disclosure.

## 1.4. Phạm vi MVP

Trong phạm vi tài liệu này, MVP bao gồm 10 feature được chia thành 2 tier:

### Tier 1 — Must Have (bắt buộc cho launch)

| Mã | Feature | Tuần |
|---|---|---|
| F1 | Shop Onboarding & Product Catalog | 1-4 |
| F2 | AI Comment Responder (Quick Paste Mode) | 3-6 |
| F3 | Script Generator | 5-8 |
| F4 | Multi-Platform Browser Extension | 3-7 |
| F5 | Dashboard Analytics | 7-10 |
| F6 | Authentication + Billing + Multi-tenancy | 1-10 |

### Tier 2 — Should Have (polish và upsell)

| Mã | Feature | Tuần |
|---|---|---|
| F7 | Digital Human Video Generator (async) | 11-12 |
| F8 | Voice Cloning with Consent Flow | 11-12 |
| F9 | Auto-Reply Mode (controlled, optional) | 13-14 |
| F10 | Comment Moderation & Spam Filter | 13-14 |

## 1.5. Không thuộc phạm vi MVP

Để kỷ luật scope, các tính năng sau được liệt kê rõ là KHÔNG làm trong 16 tuần MVP:

- Digital human livestream realtime 24/7
- Push stream lên platform từ server
- Fine-tune LLM riêng cho domain
- Self-host TTS và ASR
- Self-host vector database (dùng pgvector trong Postgres)
- Mobile native app đầy đủ
- Đa ngôn ngữ — chỉ tiếng Việt cho MVP
- White-label cho agency
- Public API cho developer

---

# Phần 2: Thiết kế màn hình UI/UX

## 2.1. Nguyên tắc thiết kế chung

### Typography

- Font chính: Inter hoặc Be Vietnam Pro (hỗ trợ tiếng Việt tốt)
- Heading 1: 32px, bold
- Heading 2: 24px, semibold
- Body text: 16px, regular
- Caption: 12px, regular

### Color Palette

| Vai trò | Màu | Mã Hex | Ghi chú |
|---|---|---|---|
| Primary | Purple | `#5B47E0` | Màu brand chính |
| Success | Green | `#10B981` | Trạng thái thành công |
| Warning | Orange | `#F59E0B` | Cảnh báo, quota sắp hết |
| Error | Red | `#EF4444` | Lỗi, destructive action |
| Live indicator | Red | `#EF4444` | Có animation pulse |
| Text primary | Gray 900 | `#111827` | Nội dung chính |
| Text secondary | Gray 500 | `#6B7280` | Meta info |
| Background | Gray 50 | `#F9FAFB` | Nền trang |

### Spacing & Layout

- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64 pixels
- Border radius: 8px cho cards, 6px cho inputs, 4px cho small elements
- Desktop-first, responsive breakpoint 768px và 1280px
- Dashboard tối ưu cho desktop 1280px+, mobile chỉ hỗ trợ view analytics

## 2.2. Danh sách màn hình

Tổng cộng 24 màn hình được chia thành 6 nhóm chức năng:

| Nhóm | Mô tả | Số màn hình |
|---|---|---|
| A. Landing & Public | Trang công khai, chưa login | 3 |
| B. Auth & Onboarding | Đăng ký, xác thực, khởi tạo shop | 5 |
| C. Dashboard Core | Các trang chính sau khi login | 6 |
| D. Live Session | Browser extension và overlay | 4 |
| E. Settings & Billing | Cài đặt tài khoản, thanh toán | 4 |
| F. Special States | Empty state, error state | 2 |

## 2.3. Nhóm A — Landing & Public

### A1. Landing Page

**Mục đích:** Convert visitor thành user đăng ký dùng thử 14 ngày.

**Cấu trúc:**

- Hero section: headline, sub-headline, CTA chính, demo video 60 giây
- Problem section: 3 vấn đề quen thuộc khi live bán hàng
- How it works: 3 bước sử dụng
- Pricing preview với 3 tier
- Testimonials (khi có)
- FAQ accordion — câu "Có bị ban account không?" để đầu tiên
- Footer: legal links, Zalo support

**Layout wireframe:**

```
┌──────────────────────────────────────────────────────┐
│ [Logo]  Features  Pricing  Blog  Login [Start Free] │
├──────────────────────────────────────────────────────┤
│                                                      │
│        AI Co-host giúp bạn bán hàng live             │
│              nhiều hơn, mệt ít hơn                   │
│                                                      │
│   Trợ lý AI đọc comment, gợi ý trả lời, sinh         │
│   kịch bản live — tất cả trong dưới 3 giây           │
│                                                      │
│         [Dùng thử 14 ngày miễn phí]                  │
│         Không cần thẻ tín dụng                       │
│                                                      │
│         ┌──────────────────────────────┐             │
│         │  [Demo video 60s autoplay]   │             │
│         └──────────────────────────────┘             │
├──────────────────────────────────────────────────────┤
│  3 vấn đề quen thuộc khi live bán hàng               │
│  [Bỏ sót comment] [Không kịp trả lời] [Kịch bản]     │
├──────────────────────────────────────────────────────┤
│  Cách hoạt động                                      │
│  1. Cài extension  2. Thêm sản phẩm  3. Bắt đầu live │
├──────────────────────────────────────────────────────┤
│  Pricing: [Starter $19] [Pro $49] [Agency $149]      │
├──────────────────────────────────────────────────────┤
│  FAQ  |  Footer                                      │
└──────────────────────────────────────────────────────┘
```

### A2. Pricing Page

**Mục đích:** Giúp user chọn đúng plan, tạo niềm tin bằng pricing minh bạch.

**Bảng so sánh 3 tier:**

| Tính năng | Starter $19 | Pro $49 | Agency $149 |
|---|---|---|---|
| Số sản phẩm | 20 | 100 | Không giới hạn |
| Số platform | 1 | 4 | Không giới hạn |
| Giờ live/tháng | 20h | 100h | Không giới hạn |
| Scripts/tháng | 20 | 100 | Không giới hạn |
| Digital Human | Không | 5h/tháng | 20h/tháng |
| Voice Clone | Không | 1 giọng | 5 giọng |
| Auto-Reply | Không | Có (limited) | Có (full) |
| Team seats | 1 | 3 | 10 |
| Analytics | Basic | Full + export | Full + API |

### A3. Public Docs / Help Center

Trang tài liệu công khai, chia thành 4 nhóm: Bắt đầu nhanh, Tính năng, Xử lý sự cố, Pháp lý. Có thanh search ở đầu trang.

## 2.4. Nhóm B — Auth & Onboarding

### B1. Sign Up

**Flow:**

1. User nhập email và password, hoặc click Google OAuth
2. Password strength check inline
3. Checkbox đồng ý Terms of Service bắt buộc
4. Submit → gửi mã OTP qua email
5. Redirect đến B2 Verify OTP

### B2. Verify Email OTP

Màn hình nhập mã 6 số. Có tính năng gửi lại sau 60 giây. Sau khi xác thực thành công, redirect đến onboarding wizard B3.

### B3. Onboarding Step 1 — Shop Info

**Thông tin thu thập:**

- Tên shop
- Ngành hàng chính (dropdown: Mỹ phẩm / Thời trang / Đồ gia dụng / Thực phẩm chức năng / Mẹ và bé / Điện tử / Khác)
- Platform đang live (multi-select checkboxes)
- Quy mô team (radio: 1 / 2-5 / 6-10 / hơn 10)

Dữ liệu này dùng để auto-suggest persona phù hợp và phân tích segment.

### B4. Onboarding Step 2 — Install Extension

Hướng dẫn user cài Chrome Extension. Có nút "Thêm vào Chrome" redirect Chrome Web Store. Extension sau khi cài sẽ ping về backend qua postMessage để verify installation thành công.

### B5. Onboarding Step 3 — Add First Product

**Hai cách thêm sản phẩm:**

- Paste link Shopee/TikTok Shop → AI tự extract thông tin (killer UX)
- Nhập thủ công: tên, mô tả, giá, ảnh, highlights

Khi đã có description, hiển thị nút "AI gợi ý highlights" để sinh tự động 5-10 điểm nổi bật.

### B6. Onboarding Step 4 — Choose Persona

Chọn persona cho host AI từ 4 preset:

- Thân thiện (default, gần gũi, xưng chị/em)
- Năng động (trẻ trung, nhiều năng lượng)
- Chuyên nghiệp (lịch sự, xưng quý khách)
- Hài hước (vui vẻ, nhiều câu đùa)

Mỗi persona có preview text để user cảm được tone. Sau khi hoàn thành → redirect Dashboard Home với welcome modal.

## 2.5. Nhóm C — Dashboard Core

### C1. Dashboard Home (Overview)

**Mục đích:** Trang đầu tiên sau khi login. Cung cấp quick actions, usage overview, và recent activity.

**Các component chính:**

- Welcome message với tên user
- 3 Quick Action cards: Bắt đầu live, Tạo script, Tạo digital human video
- Monthly stats: giờ live, comments xử lý, suggestion used rate, scripts created
- Usage meter của plan hiện tại (progress bar)
- Recent sessions list (5 session gần nhất)
- Daily tip section (educational content)

### C2. Products List

**Table view với các cột:**

- Checkbox (bulk actions)
- Ảnh thumbnail + tên sản phẩm
- Giá
- Trạng thái indexing: Sẵn sàng / Đang index / Lỗi
- Thời gian cập nhật cuối
- Menu actions (edit, delete, re-index)

**Features bổ sung:**

- Search bar, filter theo status, sort theo nhiều tiêu chí
- Bulk actions: delete, export, re-index
- Pagination (20 items/page)

### C3. Product Detail / Edit

**Layout: 2 columns**

Cột trái: ảnh sản phẩm (có thể upload nhiều). Cột phải: form nhập liệu.

**Các trường:**

- Tên sản phẩm (required)
- Mô tả ngắn (required)
- Giá (number input có format VND)
- Highlights list (có nút AI gợi ý thêm)
- FAQ accordion (có nút AI tạo FAQ tự động)
- Trạng thái index và nút Re-index

### C4. Scripts Library

Grid view các script đã tạo, mỗi card hiển thị: tên script, persona, số từ, thời gian đọc ước tính, preview 3 dòng đầu, thời gian tạo, và 3 action buttons (Mở / Sao chép / Xóa). Filter theo sản phẩm, persona, độ dài.

### C5. Script Generator / Editor

**Layout split view:**

Cột trái (30%): Configuration panel

- Chọn sản phẩm (multi-select 1-5 items)
- Chọn persona (radio)
- Chọn độ dài (5/10/20/30 phút)
- Chọn tone (chuyên nghiệp/thân thiện/vui vẻ)
- Text area: chú ý đặc biệt (free text prompt)
- Nút Sinh script

Cột phải (70%): Content editor

- Nội dung script inline editable
- Stats card: số từ, thời gian đọc, số CTA, số câu hỏi gợi ý
- Action buttons: Sinh lại / Copy / Export PDF

### C6. Session History & Detail

**C6a. Sessions List:**

Filter theo platform (Facebook/TikTok/YouTube/Shopee/Tất cả), filter theo ngày. Mỗi session card hiển thị: tên platform, thời gian bắt đầu, duration, số comments, số suggestions, used rate, sản phẩm được nhắc, persona được dùng.

**C6b. Session Detail:**

- Stat row: duration, comments, suggestions, used rate, avg latency
- Chart: biểu đồ area hiển thị comments per minute theo thời gian
- Products mentioned breakdown (pie chart hoặc bar chart)
- Top FAQ questions trong session
- Link xem full transcript
- Export CSV button

## 2.6. Nhóm D — Live Session (Extension UI)

Đây là phần quan trọng nhất về UX vì user sẽ nhìn overlay hàng giờ trong suốt live stream.

### D1. Extension Popup

Popup hiện khi click icon extension trên toolbar Chrome. Có 2 trạng thái:

**Trạng thái 1: Chưa phát hiện live**

- Hiển thị message hướng dẫn mở tab live
- Usage meter tháng hiện tại
- Links: Mở Dashboard, Trợ giúp

**Trạng thái 2: Đã phát hiện live**

- Badge "Phát hiện Facebook Live" (hoặc platform tương ứng)
- Checkbox list sản phẩm đang bán trong session này
- Chọn persona (có thể đổi)
- Nút Bắt đầu session

### D2. Overlay đang hoạt động

**Đặc điểm UI:**

- Fixed position top-right của browser window
- Kích thước 380px width, có thể drag để đổi vị trí
- Có thể collapse xuống còn 60px height chỉ hiện logo và stats
- Luôn nằm trên cùng (z-index cao)

**Các section:**

- Top bar: logo, active indicator (dot pulse), minimize, close
- Stats strip: session duration, comments count, suggestions count
- Current suggestion card: user info, comment text, suggested reply, action buttons
- History section: list các comment trước đó với status
- Bottom bar: pause, end session

**4 action buttons cho mỗi suggestion:**

| Nút | Hành động | Shortcut | Ghi chú |
|---|---|---|---|
| Gửi | Quick paste vào comment input của platform | `Ctrl+Enter` | Primary action, to nhất |
| Đọc | TTS đọc qua tai nghe | `Ctrl+Space` | Cho voice mode |
| Sửa | Edit text trước khi gửi | `Ctrl+E` | Mở inline editor |
| Bỏ | Dismiss suggestion | `Esc` | Mark as dismissed |

**Wireframe overlay D2:**

```
┌──────────────────────────────────────┐
│ [Logo] AI Co-host    Active  [-][×]  │
├──────────────────────────────────────┤
│ 12m • 87 comments • 76 suggestions   │
├──────────────────────────────────────┤
│ Nguyễn Thị Hương                     │
│ "Kem này có dùng được cho da         │
│  nhạy cảm không shop?"               │
│                                      │
│ Gợi ý trả lời:                       │
│ ┌──────────────────────────────────┐ │
│ │ "Dạ được ạ chị ơi, kem này được  │ │
│ │  kiểm nghiệm da nhạy cảm rồi,    │ │
│ │  không chứa cồn và hương liệu,   │ │
│ │  chị yên tâm nhé!"               │ │
│ └──────────────────────────────────┘ │
│                                      │
│ ┌────────────────────────────────┐   │
│ │   Gửi    (Ctrl+Enter)          │   │
│ └────────────────────────────────┘   │
│   [Đọc]   [Sửa]   [Bỏ]               │
│                                      │
│ Text sẽ điền vào ô comment.          │
│ Bạn nhấn Enter để gửi.               │
├──────────────────────────────────────┤
│ Comment trước đó (86)                │
│ 12:34 Trần Văn A                     │
│ "Giá bao nhiêu vậy?"                 │
│ Đã gửi — 12:34:08                    │
│                                      │
│ 12:33 Lê Thị B                       │
│ "Da dầu dùng ok không?"              │
│ Đã điền chưa gửi — 12:33:12          │
├──────────────────────────────────────┤
│ [Tạm dừng]  [Kết thúc session]       │
└──────────────────────────────────────┘
```

**4 trạng thái của suggestion trong history:**

- **Đã gửi**: user đã click Gửi và paste đã xuất hiện trong live chat
- **Đã điền chưa gửi**: text đã paste vào comment box nhưng user không nhấn Enter trong 30 giây
- **Đã đọc**: user dùng TTS mode để đọc qua tai nghe
- **Đã bỏ qua**: user dismiss suggestion

### D3. Overlay Edit Mode

Khi user click nút Sửa, suggestion chuyển sang edit mode với textarea có thể chỉnh sửa trực tiếp. Có checkbox "Lưu làm FAQ cho sản phẩm này" để tự động cải thiện AI cho lần sau tương tự.

### D4. Session End Summary

Hiện khi user kết thúc session. Tóm tắt: duration, comments count, suggestions count, used rate, top products mentioned, quota usage update. Có CTA xem báo cáo chi tiết.

## 2.7. Nhóm E — Settings & Billing

### E1. Account Settings

Thông tin cá nhân: avatar, họ tên, email (hiển thị verified badge), số điện thoại. Section bảo mật: đổi password, kích hoạt 2FA, xem phiên đăng nhập. Danger zone: xóa tài khoản.

### E2. Billing & Subscription

**Các section:**

- Gói hiện tại: tên plan, giá, ngày gia hạn
- Usage meters: giờ live, sản phẩm, scripts, DH video, voice clones
- Nút Upgrade/Downgrade/Cancel
- Payment method: hiển thị card với nút cập nhật
- Invoice history: danh sách hóa đơn với link download PDF
- VAT info cho doanh nghiệp Việt Nam

### E3. Team Management

Danh sách thành viên với avatar, tên, email, role. Nút Mời thành viên mới. 3 roles: Owner (toàn quyền, billing), Admin (toàn quyền trừ billing), Member (chỉ dùng feature). Hiển thị số seats đã dùng vs limit của plan.

### E4. Personas & Voices

Tab Personas: grid view các persona đã tạo, có nút tạo mới. Mỗi card hiển thị tên, tone, voice được gán.

Tab Voices: danh sách voice đã clone, mỗi voice có nút nghe thử, xem consent form, xóa. Warning rõ ràng về yêu cầu pháp lý.

## 2.8. Nhóm F — Special States

### F1. Empty States

Mọi list/table trong hệ thống đều có empty state được thiết kế riêng, gồm 3 yếu tố:

- Illustration minh họa phù hợp context
- Headline rõ ràng
- CTA hoặc hướng dẫn cụ thể (không phải text chung chung "không có dữ liệu")

Empty state là cơ hội onboarding, không phải báo lỗi.

### F2. Error States

**Các loại error state cần thiết kế:**

- Extension không kết nối được server: hướng dẫn check mạng, retry button, link Zalo support
- Platform đổi DOM (extension không đọc được comment): thừa nhận vấn đề, thông báo đang fix, gợi ý dùng feature khác tạm thời
- Quota hết: nâng cấp plan hoặc chờ kỳ reset
- LLM call fail: retry tự động với fallback provider
- Payment fail: hướng dẫn update card

Nguyên tắc error message: (a) thừa nhận vấn đề, (b) giải thích nguyên nhân nếu biết, (c) cho hành động thay thế, (d) không đổ lỗi cho user.

---

# Phần 3: Thiết kế cơ sở dữ liệu

## 3.1. Tổng quan

Cơ sở dữ liệu chính sử dụng PostgreSQL 15+ với extension pgvector để hỗ trợ semantic search cho RAG. Lựa chọn này thay vì Qdrant Cloud mang lại các lợi ích:

- Giảm một service cần vận hành
- Transactional consistency giữa metadata và vector
- Join trực tiếp giữa vector query và SQL filter
- Chi phí thấp hơn ở quy mô MVP
- Backup và migration đơn giản với pg_dump
- Multi-tenant isolation dễ hơn với Row-Level Security

## 3.2. Extensions cần enable

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

## 3.3. Entity Relationship Overview

Hệ thống có 16 bảng chính được chia thành 6 nhóm logic:

| Nhóm | Các bảng | Mục đích |
|---|---|---|
| Tenant | `shops`, `users`, `shop_members` | Multi-tenancy, auth, team |
| Content | `products`, `product_faqs`, `personas` | Data sản phẩm và cấu hình AI |
| Session | `live_sessions`, `comments`, `suggestions` | Hoạt động live stream |
| Scripts | `scripts`, `script_samples` | Script generation và library |
| Media | `dh_videos`, `voice_clones` | Digital human và voice |
| Billing | `subscriptions`, `invoices`, `usage_logs` | Thanh toán và tracking |

## 3.4. Schema chi tiết

### 3.4.1. Bảng shops

Bảng trung tâm của multi-tenancy. Mọi dữ liệu khác trong hệ thống đều phải có `shop_id` làm scope.

```sql
CREATE TABLE shops (
  id              BIGSERIAL PRIMARY KEY,
  uuid            UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  slug            TEXT UNIQUE NOT NULL,
  industry        TEXT,
  team_size       TEXT,
  owner_user_id   BIGINT NOT NULL,
  plan            TEXT NOT NULL DEFAULT 'trial',
  plan_status     TEXT NOT NULL DEFAULT 'active',
  trial_ends_at   TIMESTAMPTZ,
  timezone        TEXT DEFAULT 'Asia/Ho_Chi_Minh',
  settings        JSONB DEFAULT '{}',
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX shops_owner_idx ON shops (owner_user_id);
CREATE INDEX shops_plan_idx ON shops (plan, plan_status);
```

### 3.4.2. Bảng users

```sql
CREATE TABLE users (
  id              BIGSERIAL PRIMARY KEY,
  uuid            UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
  email           TEXT UNIQUE NOT NULL,
  email_verified  BOOLEAN DEFAULT false,
  password_hash   TEXT,
  full_name       TEXT,
  avatar_url      TEXT,
  phone           TEXT,
  oauth_provider  TEXT,
  oauth_id        TEXT,
  two_fa_enabled  BOOLEAN DEFAULT false,
  last_login_at   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX users_email_idx ON users (email);
CREATE INDEX users_oauth_idx ON users (oauth_provider, oauth_id);
```

### 3.4.3. Bảng shop_members

Junction table cho nhiều user thuộc nhiều shop với role khác nhau. Đây là cơ sở của team seats feature.

```sql
CREATE TABLE shop_members (
  id          BIGSERIAL PRIMARY KEY,
  shop_id     BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role        TEXT NOT NULL CHECK (role IN ('owner','admin','member')),
  invited_by  BIGINT REFERENCES users(id),
  invited_at  TIMESTAMPTZ DEFAULT now(),
  joined_at   TIMESTAMPTZ,
  status      TEXT DEFAULT 'active',
  UNIQUE (shop_id, user_id)
);

CREATE INDEX shop_members_user_idx ON shop_members (user_id);
CREATE INDEX shop_members_shop_idx ON shop_members (shop_id);
```

### 3.4.4. Bảng products

Bảng sản phẩm với embedding tích hợp trực tiếp (pgvector) để tối ưu query cho Comment Responder.

```sql
CREATE TABLE products (
  id                    BIGSERIAL PRIMARY KEY,
  shop_id               BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  name                  TEXT NOT NULL,
  description           TEXT,
  price                 NUMERIC(12, 2),
  currency              TEXT DEFAULT 'VND',
  highlights            TEXT[] DEFAULT '{}',
  images                JSONB DEFAULT '[]',
  external_url          TEXT,
  category              TEXT,
  is_active             BOOLEAN DEFAULT true,
  
  -- Embedding cho semantic search
  embedding             vector(768),
  embedding_model       TEXT,
  embedding_updated_at  TIMESTAMPTZ,
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now()
);

-- HNSW index cho ANN search
CREATE INDEX products_embedding_idx ON products
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX products_shop_active_idx ON products (shop_id, is_active);
CREATE INDEX products_shop_category_idx ON products (shop_id, category);

-- Full-text search tiếng Việt
CREATE INDEX products_name_trgm_idx ON products USING gin (name gin_trgm_ops);
```

### 3.4.5. Bảng product_faqs

```sql
CREATE TABLE product_faqs (
  id                    BIGSERIAL PRIMARY KEY,
  product_id            BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  shop_id               BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  question              TEXT NOT NULL,
  answer                TEXT NOT NULL,
  source                TEXT DEFAULT 'manual',
  order_index           INT DEFAULT 0,
  
  -- Embedding của question cho matching comment
  embedding             vector(768),
  embedding_model       TEXT,
  embedding_updated_at  TIMESTAMPTZ,
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX product_faqs_embedding_idx ON product_faqs
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX product_faqs_shop_product_idx ON product_faqs (shop_id, product_id);
```

Trường `source` có thể là: `manual` (user tạo), `ai_generated` (AI sinh), `learned` (tự học từ câu user edit trong Comment Responder).

### 3.4.6. Bảng personas

```sql
CREATE TABLE personas (
  id            BIGSERIAL PRIMARY KEY,
  shop_id       BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  description   TEXT,
  tone          TEXT,
  quirks        TEXT[],
  sample_phrases TEXT[],
  voice_clone_id BIGINT,
  is_default    BOOLEAN DEFAULT false,
  is_preset     BOOLEAN DEFAULT false,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX personas_shop_idx ON personas (shop_id);
CREATE UNIQUE INDEX personas_shop_default_idx ON personas (shop_id)
  WHERE is_default = true;
```

### 3.4.7. Bảng live_sessions

```sql
CREATE TABLE live_sessions (
  id                BIGSERIAL PRIMARY KEY,
  uuid              UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
  shop_id           BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  started_by        BIGINT NOT NULL REFERENCES users(id),
  platform          TEXT NOT NULL CHECK (platform IN 
                      ('facebook','tiktok','youtube','shopee','other')),
  platform_url      TEXT,
  persona_id        BIGINT REFERENCES personas(id),
  active_product_ids BIGINT[],
  
  -- Lifecycle
  started_at        TIMESTAMPTZ DEFAULT now(),
  ended_at          TIMESTAMPTZ,
  duration_seconds  INT,
  status            TEXT DEFAULT 'running',
  
  -- Aggregated metrics (denormalized cho performance)
  comments_count    INT DEFAULT 0,
  suggestions_count INT DEFAULT 0,
  sent_count        INT DEFAULT 0,
  pasted_not_sent_count INT DEFAULT 0,
  read_count        INT DEFAULT 0,
  dismissed_count   INT DEFAULT 0,
  avg_latency_ms    INT,
  
  metadata          JSONB DEFAULT '{}',
  created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX live_sessions_shop_started_idx ON live_sessions (shop_id, started_at DESC);
CREATE INDEX live_sessions_status_idx ON live_sessions (status) 
  WHERE status = 'running';
```

### 3.4.8. Bảng comments

Lưu các comment được extension đọc từ live stream. Có thể có volume cao, cần partition khi lên scale.

```sql
CREATE TABLE comments (
  id                BIGSERIAL PRIMARY KEY,
  session_id        BIGINT NOT NULL REFERENCES live_sessions(id) ON DELETE CASCADE,
  shop_id           BIGINT NOT NULL REFERENCES shops(id),
  
  external_user_id  TEXT,
  external_user_name TEXT,
  text              TEXT NOT NULL,
  
  received_at       TIMESTAMPTZ DEFAULT now(),
  language          TEXT DEFAULT 'vi',
  sentiment         TEXT,
  intent            TEXT,
  confidence        FLOAT,
  
  is_spam           BOOLEAN DEFAULT false,
  is_processed      BOOLEAN DEFAULT false,
  
  created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX comments_session_received_idx ON comments (session_id, received_at DESC);
CREATE INDEX comments_shop_idx ON comments (shop_id, received_at DESC);
CREATE INDEX comments_unprocessed_idx ON comments (session_id) 
  WHERE is_processed = false;
```

Trường `intent` có thể là: `question`, `complaint`, `praise`, `greeting`, `thanks`, `pricing`, `shipping`, `spam`, `other`.

### 3.4.9. Bảng suggestions

```sql
CREATE TABLE suggestions (
  id              BIGSERIAL PRIMARY KEY,
  comment_id      BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
  session_id      BIGINT NOT NULL REFERENCES live_sessions(id) ON DELETE CASCADE,
  shop_id         BIGINT NOT NULL REFERENCES shops(id),
  
  -- Generated content
  text            TEXT NOT NULL,
  edited_text     TEXT,
  
  -- LLM metadata
  llm_model       TEXT,
  llm_provider    TEXT,
  prompt_version  TEXT,
  input_tokens    INT,
  output_tokens   INT,
  latency_ms      INT,
  
  -- RAG context used
  rag_product_ids BIGINT[],
  rag_faq_ids     BIGINT[],
  
  -- User action
  status          TEXT NOT NULL DEFAULT 'suggested' 
                  CHECK (status IN ('suggested','sent','pasted_not_sent',
                                    'read','dismissed','edited')),
  action_at       TIMESTAMPTZ,
  
  -- Audio (nếu có TTS)
  audio_url       TEXT,
  
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX suggestions_comment_idx ON suggestions (comment_id);
CREATE INDEX suggestions_session_idx ON suggestions (session_id);
CREATE INDEX suggestions_shop_status_idx ON suggestions (shop_id, status);
```

### 3.4.10. Bảng scripts

```sql
CREATE TABLE scripts (
  id              BIGSERIAL PRIMARY KEY,
  shop_id         BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  created_by      BIGINT NOT NULL REFERENCES users(id),
  
  title           TEXT NOT NULL,
  content         TEXT NOT NULL,
  
  -- Config used
  product_ids     BIGINT[] NOT NULL,
  persona_id      BIGINT REFERENCES personas(id),
  duration_target INT,
  tone            TEXT,
  special_notes   TEXT,
  
  -- Stats
  word_count      INT,
  estimated_duration_seconds INT,
  cta_count       INT,
  
  -- Generation metadata
  llm_model       TEXT,
  llm_provider    TEXT,
  prompt_version  TEXT,
  generation_cost NUMERIC(10, 6),
  
  -- Version tracking
  parent_script_id BIGINT REFERENCES scripts(id),
  version         INT DEFAULT 1,
  
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX scripts_shop_created_idx ON scripts (shop_id, created_at DESC);
CREATE INDEX scripts_shop_products_idx ON scripts USING gin (product_ids);
```

### 3.4.11. Bảng script_samples

Library các script mẫu chất lượng cao dùng làm few-shot examples cho Script Generator. Đây là data global không thuộc shop.

```sql
CREATE TABLE script_samples (
  id              BIGSERIAL PRIMARY KEY,
  category        TEXT NOT NULL,
  persona_style   TEXT NOT NULL,
  title           TEXT,
  content         TEXT NOT NULL,
  quality_score   INT CHECK (quality_score BETWEEN 1 AND 5),
  tags            TEXT[],
  
  embedding       vector(768),
  
  created_by      TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX script_samples_embedding_idx ON script_samples
  USING hnsw (embedding vector_cosine_ops);

CREATE INDEX script_samples_category_style_idx ON script_samples 
  (category, persona_style, quality_score DESC);
```

### 3.4.12. Bảng dh_videos

Digital human videos được generate async.

```sql
CREATE TABLE dh_videos (
  id              BIGSERIAL PRIMARY KEY,
  shop_id         BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  created_by      BIGINT NOT NULL REFERENCES users(id),
  
  script_id       BIGINT REFERENCES scripts(id),
  source_text     TEXT NOT NULL,
  
  avatar_preset   TEXT,
  avatar_custom_url TEXT,
  voice_clone_id  BIGINT,
  background      TEXT,
  
  -- Provider integration
  provider        TEXT NOT NULL,
  provider_job_id TEXT,
  
  -- Output
  video_url       TEXT,
  video_duration_seconds INT,
  file_size_bytes BIGINT,
  has_watermark   BOOLEAN DEFAULT true,
  
  -- Status
  status          TEXT DEFAULT 'queued'
                  CHECK (status IN ('queued','processing','ready','failed','expired')),
  error_message   TEXT,
  
  -- Billing
  credits_used    NUMERIC(10, 4),
  
  created_at      TIMESTAMPTZ DEFAULT now(),
  completed_at    TIMESTAMPTZ,
  expires_at      TIMESTAMPTZ
);

CREATE INDEX dh_videos_shop_idx ON dh_videos (shop_id, created_at DESC);
CREATE INDEX dh_videos_status_idx ON dh_videos (status) 
  WHERE status IN ('queued','processing');
```

### 3.4.13. Bảng voice_clones

Voice clone với audit trail đầy đủ cho legal compliance.

```sql
CREATE TABLE voice_clones (
  id                  BIGSERIAL PRIMARY KEY,
  shop_id             BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  created_by          BIGINT NOT NULL REFERENCES users(id),
  
  name                TEXT NOT NULL,
  description         TEXT,
  
  -- Source audio
  source_audio_url    TEXT NOT NULL,
  source_duration_seconds INT,
  
  -- Legal
  consent_form_url    TEXT NOT NULL,
  consent_confirmed_at TIMESTAMPTZ NOT NULL,
  consent_confirmed_by BIGINT NOT NULL REFERENCES users(id),
  consent_person_name TEXT NOT NULL,
  
  -- Provider
  provider            TEXT NOT NULL,
  provider_voice_id   TEXT,
  
  -- Status
  status              TEXT DEFAULT 'processing'
                      CHECK (status IN ('processing','ready','failed','deleted')),
  
  created_at          TIMESTAMPTZ DEFAULT now(),
  deleted_at          TIMESTAMPTZ
);

CREATE INDEX voice_clones_shop_idx ON voice_clones (shop_id) 
  WHERE deleted_at IS NULL;
```

### 3.4.14. Bảng subscriptions

```sql
CREATE TABLE subscriptions (
  id                    BIGSERIAL PRIMARY KEY,
  shop_id               BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  
  plan                  TEXT NOT NULL,
  status                TEXT NOT NULL,
  
  -- Provider
  provider              TEXT NOT NULL,
  provider_customer_id  TEXT,
  provider_subscription_id TEXT,
  
  -- Billing cycle
  current_period_start  TIMESTAMPTZ,
  current_period_end    TIMESTAMPTZ,
  cancel_at_period_end  BOOLEAN DEFAULT false,
  cancelled_at          TIMESTAMPTZ,
  
  -- Trial
  trial_start           TIMESTAMPTZ,
  trial_end             TIMESTAMPTZ,
  
  -- Pricing
  amount                NUMERIC(10, 2),
  currency              TEXT DEFAULT 'USD',
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX subscriptions_shop_idx ON subscriptions (shop_id);
CREATE INDEX subscriptions_provider_idx ON subscriptions 
  (provider, provider_subscription_id);
```

### 3.4.15. Bảng invoices

```sql
CREATE TABLE invoices (
  id                BIGSERIAL PRIMARY KEY,
  shop_id           BIGINT NOT NULL REFERENCES shops(id),
  subscription_id   BIGINT REFERENCES subscriptions(id),
  
  invoice_number    TEXT UNIQUE NOT NULL,
  amount            NUMERIC(10, 2) NOT NULL,
  currency          TEXT DEFAULT 'USD',
  status            TEXT NOT NULL,
  
  provider          TEXT,
  provider_invoice_id TEXT,
  
  pdf_url           TEXT,
  
  issued_at         TIMESTAMPTZ DEFAULT now(),
  due_at            TIMESTAMPTZ,
  paid_at           TIMESTAMPTZ
);

CREATE INDEX invoices_shop_idx ON invoices (shop_id, issued_at DESC);
```

### 3.4.16. Bảng usage_logs

Track usage cho quota enforcement và billing analytics.

```sql
CREATE TABLE usage_logs (
  id              BIGSERIAL PRIMARY KEY,
  shop_id         BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  user_id         BIGINT REFERENCES users(id),
  
  resource_type   TEXT NOT NULL,
  resource_id     BIGINT,
  
  -- Measurement
  quantity        NUMERIC(12, 4) NOT NULL,
  unit            TEXT NOT NULL,
  
  -- Cost tracking (internal)
  cost_usd        NUMERIC(10, 6),
  
  -- Billing period
  billing_period  DATE NOT NULL,
  
  metadata        JSONB DEFAULT '{}',
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX usage_logs_shop_period_idx ON usage_logs 
  (shop_id, billing_period, resource_type);
CREATE INDEX usage_logs_resource_idx ON usage_logs 
  (resource_type, created_at DESC);
```

## 3.5. Row-Level Security (RLS)

PostgreSQL RLS được enable cho mọi bảng có `shop_id` để đảm bảo cross-tenant isolation ở mức database.

```sql
-- Enable RLS on all tenant tables
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_faqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE live_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE scripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dh_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_clones ENABLE ROW LEVEL SECURITY;

-- Policy: user chỉ thấy data của shop mình
CREATE POLICY shop_isolation ON products
  FOR ALL
  USING (shop_id = current_setting('app.current_shop_id')::BIGINT);

-- Tương tự cho các bảng khác
```

Application layer set variable session khi authenticate:

```sql
SET LOCAL app.current_shop_id = 123;
```

## 3.6. Query Patterns Quan Trọng

### 3.6.1. RAG query cho Comment Responder

Query này chạy mỗi lần có comment mới, yêu cầu latency thấp (<50ms).

```sql
WITH relevant_products AS (
  SELECT id, name, description, highlights,
         1 - (embedding <=> $1::vector) AS similarity
  FROM products
  WHERE shop_id = $2
    AND is_active = true
    AND id = ANY($3::bigint[])
  ORDER BY embedding <=> $1::vector
  LIMIT 2
),
relevant_faqs AS (
  SELECT f.question, f.answer, f.product_id,
         1 - (f.embedding <=> $1::vector) AS similarity
  FROM product_faqs f
  WHERE f.shop_id = $2
    AND f.product_id IN (SELECT id FROM relevant_products)
  ORDER BY f.embedding <=> $1::vector
  LIMIT 3
)
SELECT 
  (SELECT json_agg(row_to_json(p)) FROM relevant_products p) AS products,
  (SELECT json_agg(row_to_json(f)) FROM relevant_faqs f) AS faqs;
```

### 3.6.2. Few-shot examples cho Script Generator

```sql
SELECT content, category, persona_style, quality_score,
       1 - (embedding <=> $1::vector) AS similarity
FROM script_samples
WHERE category = $2
  AND persona_style = $3
  AND quality_score >= 4
ORDER BY embedding <=> $1::vector
LIMIT 3;
```

### 3.6.3. Monthly usage aggregation

```sql
SELECT 
  resource_type,
  SUM(quantity) as total,
  unit
FROM usage_logs
WHERE shop_id = $1
  AND billing_period >= date_trunc('month', CURRENT_DATE)
GROUP BY resource_type, unit;
```

## 3.7. Data Retention Policy

| Bảng | Retention | Lý do |
|---|---|---|
| `comments` | 90 ngày | GDPR-like, privacy của customer |
| `suggestions` | 90 ngày | Đủ cho analytics, không lưu lâu |
| `live_sessions` | Vĩnh viễn | Metrics phục vụ business |
| `dh_videos` | 30 ngày sau `expires_at` | Giảm storage cost |
| `voice_clones` | Đến khi user xóa | Legal audit trail |
| `usage_logs` | 2 năm | Billing dispute, tax audit |
| `scripts` | Vĩnh viễn | IP của user |

---

# Phần 4: Thiết kế kiến trúc hệ thống

## 4.1. Tổng quan kiến trúc

Hệ thống được thiết kế theo mô hình phân tầng với các nguyên tắc:

- Stateless application layer để dễ scale horizontal
- Async-first cho các operation nặng (LLM, TTS, DH video)
- Managed services tối đa để giảm DevOps burden
- Single region (ap-southeast-1 Singapore) cho MVP, multi-region phase 2

## 4.2. High-level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    USER'S BROWSER                            │
│  ┌──────────────────────┐    ┌──────────────────────┐        │
│  │  Chrome Extension    │    │  Next.js Dashboard   │        │
│  │  - Content script    │    │  - Product mgmt      │        │
│  │  - Comment reader    │    │  - Script library    │        │
│  │  - Overlay UI        │    │  - Analytics         │        │
│  │  - WebSocket client  │    │  - Billing           │        │
│  └──────────┬───────────┘    └──────────┬───────────┘        │
└─────────────┼────────────────────────────┼───────────────────┘
              │ WSS                        │ HTTPS
              ↓                            ↓
┌──────────────────────────────────────────────────────────────┐
│                    API GATEWAY (Caddy)                       │
│           - TLS termination, rate limiting                   │
└──────────────┬────────────────────────────┬──────────────────┘
               ↓                            ↓
┌──────────────────────────┐    ┌──────────────────────────┐
│   WebSocket Server       │    │   REST API (FastAPI)     │
│   (FastAPI + ws)         │    │   - Auth (JWT)           │
│   - Session management   │    │   - CRUD endpoints       │
│   - Comment ingestion    │    │   - Script generation    │
│   - Response streaming   │    │   - Billing webhooks     │
└──────────┬───────────────┘    └───────────┬──────────────┘
           └────────────┬───────────────────┘
                        ↓
           ┌────────────────────────┐
           │  Job Queue (Celery)    │
           │  - LLM async calls     │
           │  - TTS generation      │
           │  - Digital human gen   │
           │  - Embedding updates   │
           └──────┬─────────────────┘
                  ↓
      ┌───────────┼─────────────┬──────────────┐
      ↓           ↓             ↓              ↓
┌──────────────┐ ┌─────────┐ ┌──────────┐
│ Postgres +   │ │  Redis  │ │  S3-R2   │
│ pgvector     │ │(Upstash)│ │ Storage  │
│ (Supabase)   │ │         │ │          │
└──────────────┘ └─────────┘ └──────────┘

┌──────────────────────────────────────┐
│    External AI Services             │
│    - Gemini 2.0 Flash (primary)     │
│    - Claude Haiku (quality)         │
│    - DeepSeek V3 (fallback)         │
│    - Google Cloud TTS (Vietnamese)  │
│    - ElevenLabs (voice clone)       │
│    - HeyGen API (digital human)     │
└──────────────────────────────────────┘
```

## 4.3. Technology Stack

### 4.3.1. Frontend Dashboard

| Layer | Công nghệ | Lý do chọn |
|---|---|---|
| Framework | Next.js 15 | SSR, SEO tốt, Vercel deploy free |
| Language | TypeScript 5.3 | Type safety |
| UI Library | shadcn/ui + Radix | Composable, accessible |
| Styling | Tailwind CSS 3.4 | Utility-first, nhanh |
| State | Zustand | Nhẹ, đơn giản hơn Redux |
| Data fetching | TanStack Query | Cache, refetch tự động |
| Charts | Recharts | React native |
| Forms | React Hook Form + Zod | Validation tốt |

### 4.3.2. Browser Extension

| Layer | Công nghệ | Lý do |
|---|---|---|
| Manifest | MV3 | Bắt buộc bởi Chrome 2024+ |
| Language | TypeScript | Type safety với DOM API |
| Build | Vite + CRXJS | Hot reload, fast build |
| UI | Preact + Tailwind | Nhẹ hơn React cho extension |
| Communication | WebSocket native | Realtime với backend |
| Storage | chrome.storage.local | Persist session state |

### 4.3.3. Backend

| Layer | Công nghệ | Lý do |
|---|---|---|
| Runtime | Python 3.11 | AI ecosystem mạnh |
| Framework | FastAPI | Async, tự gen OpenAPI docs |
| WebSocket | websockets lib | Native async |
| ORM | SQLAlchemy 2.0 + Alembic | Mature, migrations tốt |
| Validation | Pydantic v2 | Tích hợp với FastAPI |
| Queue | Celery + Redis broker | Stable, Python-friendly |
| Auth | Supabase Auth + JWT | Managed, có OAuth sẵn |

### 4.3.4. Data & Storage

| Component | Service | Pricing MVP |
|---|---|---|
| Database | Supabase (Postgres + pgvector) | $25/tháng Pro |
| Cache | Upstash Redis | Pay-per-request, ~$5-10 |
| Object Storage | Cloudflare R2 | Free egress, ~$5 |
| CDN | Cloudflare | Free |
| Email | Resend | $20/tháng |

### 4.3.5. External AI Services

| Service | Provider | Dùng cho | Pricing estimate |
|---|---|---|---|
| LLM primary | Gemini 2.0 Flash | Comment Responder, Script Gen | $0.075/1M tokens |
| LLM quality | Claude Haiku | Script generation dài | $0.25/1M tokens |
| LLM fallback | DeepSeek V3 | Backup khi primary fail | $0.14/1M tokens |
| Embeddings | Gemini text-embedding-004 | RAG | Free tier rộng |
| TTS | Google Cloud TTS | Comment responder voice | $4/1M chars |
| Voice Clone | ElevenLabs | Persona voice | $5/tháng + usage |
| Digital Human | HeyGen API | Video generation | $29/tháng + minutes |

## 4.4. Service Decomposition

### 4.4.1. REST API Service

**Trách nhiệm:**

- Authentication và authorization (JWT)
- CRUD operations cho products, FAQs, personas, scripts
- Script generation (sync endpoint, timeout 60s)
- Billing webhook handlers (Lemon Squeezy)
- User management và team seats
- Analytics queries

**Scaling:**

- Stateless, horizontal scale dễ
- MVP: 1 instance trên Hetzner CX32
- Phase 2: 2-3 instances sau load balancer khi cần

### 4.4.2. WebSocket Service

**Trách nhiệm:**

- Maintain persistent connection với browser extension
- Ingest comment events từ extension
- Dispatch LLM jobs qua Celery
- Stream suggestions về extension
- Session state management (trong Redis)
- Push notifications về dashboard (product indexed, video ready)

**Protocol design:**

```javascript
// Client -> Server
{ "type": "session.start", "session_id": "uuid", "products": [1,2,3], "persona_id": 5 }
{ "type": "comment.new", "comment": {...} }
{ "type": "suggestion.action", "suggestion_id": 123, "action": "sent" }
{ "type": "session.end", "session_id": "uuid" }
{ "type": "ping" }

// Server -> Client
{ "type": "suggestion.new", "suggestion": {...} }
{ "type": "suggestion.stream", "suggestion_id": 123, "chunk": "..." }
{ "type": "suggestion.complete", "suggestion_id": 123 }
{ "type": "error", "code": "...", "message": "..." }
{ "type": "pong" }
```

### 4.4.3. Celery Workers

**Queue configuration:**

- `llm_queue`: gọi LLM API cho comment responder, priority cao nhất
- `script_queue`: script generation, priority trung bình
- `embed_queue`: tạo embeddings cho products/FAQs
- `media_queue`: TTS, digital human generation, voice clone
- `usage_queue`: ghi usage logs, low priority

**Worker scaling:**

- Mỗi queue có worker pool riêng
- Concurrency cao cho `llm_queue` (IO-bound)
- Concurrency thấp cho `media_queue` (memory intensive)

## 4.5. Critical Flows

### 4.5.1. Comment Responder Realtime Flow

Đây là critical path quan trọng nhất, target latency end-to-end dưới 3 giây.

1. Extension content script phát hiện comment mới trong DOM tab live
2. Extension gửi WebSocket message `comment.new` đến WS server
3. WS server validate shop_id, session_id, lưu comment vào Postgres
4. WS server enqueue Celery task với priority cao
5. Celery worker embed comment text bằng Gemini embedding API (~100ms)
6. Worker query pgvector: top 2 products + top 3 FAQs trong session (~20ms)
7. Worker build prompt với persona + RAG context + conversation history từ Redis
8. Worker gọi Gemini Flash với streaming enabled (~1-2s)
9. Khi có first token, worker publish lên Redis pub/sub channel của session
10. WS server subscribe channel, stream chunks về extension qua WebSocket
11. Extension hiển thị suggestion trong overlay realtime
12. Worker lưu final suggestion + metadata (tokens, latency, RAG IDs) vào DB
13. Update Redis cache với suggestion để F2 history lookup

### 4.5.2. Quick Paste Flow

1. User click nút Gửi trong overlay
2. Extension content script tìm comment input element của platform
3. Extension focus vào input, clear nếu có text cũ
4. Extension dùng `execCommand insertText` để paste (fallback: ClipboardEvent)
5. Extension hiện tooltip gần input: "Nhấn Enter để gửi"
6. Extension setup MutationObserver trên chat container
7. User nhấn Enter → platform tự xử lý gửi comment
8. MutationObserver detect message xuất hiện trong live chat
9. Extension gửi `suggestion.action` với status `sent` về backend
10. Nếu sau 30 giây không detect sent → mark là `pasted_not_sent`

### 4.5.3. Script Generation Flow

Async flow với progress update qua WebSocket.

1. User submit form script generation từ dashboard
2. REST API validate input, check quota
3. API enqueue Celery task, return `job_id` ngay lập tức
4. Frontend subscribe WebSocket channel cho `job_id`
5. Worker query pgvector: top 3 script samples relevant (few-shot)
6. Worker build long prompt với products, persona, samples, instructions
7. Worker gọi Claude Haiku với `max_tokens=4000` (~15-25s)
8. Worker stream chunks qua Redis pub/sub
9. Frontend nhận chunks, render realtime
10. Worker post-process: word count, CTA extraction, duration estimate
11. Worker save vào `scripts` table
12. Worker publish completion event
13. Frontend redirect đến script detail page

### 4.5.4. Product Embedding Flow

1. User save product mới hoặc update description
2. REST API INSERT/UPDATE products với `embedding = NULL`
3. API return 200 OK ngay (<100ms)
4. API enqueue `embed_queue` task
5. Dashboard hiện product với badge "Đang index"
6. Worker gọi Gemini text-embedding-004 API
7. Worker UPDATE products SET embedding, embedding_updated_at
8. Worker publish WebSocket event `product.indexed`
9. Dashboard update badge thành "Sẵn sàng"

## 4.6. Security Design

### 4.6.1. Authentication

- Supabase Auth quản lý user credentials (bcrypt hash)
- JWT access token (1 giờ) + refresh token (30 ngày)
- Refresh token rotation on use
- OAuth Google cho convenience
- Optional 2FA với TOTP

### 4.6.2. Authorization

- JWT contains `user_id` và array `shop_ids` user có access
- Middleware FastAPI extract `shop_id` từ request path hoặc header
- Verify `shop_id` có trong JWT claims
- Set PostgreSQL session variable cho RLS
- Role check cho admin-only endpoints

### 4.6.3. Multi-tenant Isolation

- Row-Level Security policies trên mọi bảng shop-scoped
- Application-level `shop_id` filter trong mọi query (defense in depth)
- Unit tests verify không có cross-tenant data leak
- Penetration testing trước launch

### 4.6.4. Data Protection

- TLS 1.3 cho mọi traffic (Caddy auto)
- Database encryption at rest (Supabase mặc định)
- Sensitive fields encrypted ở application level (voice consent forms)
- API keys rotate định kỳ, lưu trong secrets manager (Doppler)
- CORS strict policy chỉ allow origin dashboard và extension

### 4.6.5. Rate Limiting

| Endpoint | Limit | Scope |
|---|---|---|
| `POST /auth/login` | 5/phút | Per IP |
| `POST /auth/signup` | 3/giờ | Per IP |
| WS `comment.new` | 30/phút | Per shop |
| `POST /scripts/generate` | 5/giờ (Starter) | Per shop |
| `POST /products` (bulk) | 100/giờ | Per shop |
| Global fallback | 1000/giờ | Per shop |

## 4.7. Reliability & Observability

### 4.7.1. Monitoring Stack

- Sentry free tier: error tracking cho FE và BE
- Uptime Kuma self-hosted: uptime monitoring
- Supabase dashboard: database metrics
- Custom dashboard: business metrics từ Postgres
- Discord webhook: alert on critical errors

### 4.7.2. SLO Targets MVP

| Metric | Target | Measurement |
|---|---|---|
| Uptime REST API | 99.5% | Uptime Kuma ping every 1 min |
| Uptime WebSocket | 99% | Synthetic test session |
| p50 suggestion latency | <2s | Từ comment received to suggestion delivered |
| p95 suggestion latency | <5s | Same |
| Script generation success rate | >95% | Completed / attempted |
| Extension DOM compatibility | >95% | Successful comment reads |

### 4.7.3. Disaster Recovery

- Supabase auto daily backups (7 ngày retention)
- Weekly manual `pg_dump` lưu vào R2 bucket
- Backup restore test hàng tháng
- Infrastructure-as-code với Terraform (phase 2)
- Runbook cho các incident thường gặp

### 4.7.4. Graceful Degradation

Khi một component fail, hệ thống vẫn hoạt động một phần:

- LLM primary fail → tự động fallback DeepSeek V3
- TTS fail → hiện error nhưng vẫn cho copy text
- Digital Human provider fail → queue lại, retry 3 lần
- Redis fail → degraded mode không có cache, dùng DB trực tiếp
- Platform DOM change → thông báo user, suggest feature khác

## 4.8. Cost Optimization

### 4.8.1. LLM Cost Control

- Response cache: comment giống nhau trong 5 phút tái dùng response (40% saving)
- Prompt optimization: giảm tokens không cần thiết
- Model routing: Gemini Flash cho 80% cases, Claude Haiku chỉ khi cần quality
- Hard cap per shop per day để tránh runaway cost
- Track cost per customer để tính unit economics

### 4.8.2. Infrastructure Cost MVP

| Item | Service | Monthly cost |
|---|---|---|
| Compute | Hetzner CX32 VPS | $7 |
| Database | Supabase Pro | $25 |
| Cache | Upstash Redis | $5-10 |
| Object Storage | Cloudflare R2 | $5 |
| Email | Resend | $20 |
| Domain + CDN | Cloudflare | $0 |
| LLM API | Gemini + Claude | $50-200 (usage-based) |
| TTS API | Google Cloud TTS | $20-50 |
| Digital Human | HeyGen API | $29 |
| Voice Clone | ElevenLabs | $22 |
| Monitoring | Sentry free | $0 |
| **Total fixed** |  | **~$140-190/tháng** |

## 4.9. Deployment Strategy

### 4.9.1. Environments

- **Local**: Docker Compose cho development
- **Staging**: Hetzner CX22 với data sample, preview Vercel
- **Production**: Hetzner CX32 + Vercel + Supabase Pro

### 4.9.2. CI/CD Pipeline

1. Push code lên GitHub `main` branch
2. GitHub Actions run: lint, type check, unit tests
3. Run integration tests với Postgres container
4. Build Docker image, push lên registry
5. Deploy backend lên Hetzner qua SSH + `docker-compose pull`
6. Deploy frontend tự động qua Vercel
7. Run smoke tests post-deploy
8. Notify Discord nếu có failure

### 4.9.3. Database Migrations

- Alembic cho schema migrations
- Mọi migration phải reversible
- Backward-compatible trong 1 release
- Run migration trong CI trước deploy code
- Backup DB trước mỗi migration lớn

## 4.10. Roadmap Phase 2 (sau MVP)

Những gì sẽ làm sau khi MVP đạt $1K MRR và product-market fit:

- Self-host TTS (CosyVoice) khi API cost >$200/tháng
- Self-host digital human (LiveTalking) khi có volume đủ
- Fine-tune LLM nhỏ cho tiếng Việt (Qwen2.5 7B)
- Multi-region deployment (Singapore + Japan)
- Kubernetes migration khi team >5 người
- Dedicated ML pipeline cho training data từ usage logs
- Public API cho developer
- Mobile companion app

---

# Phụ lục

## A. Glossary

| Thuật ngữ | Giải thích |
|---|---|
| RAG | Retrieval Augmented Generation - kỹ thuật kết hợp search với LLM |
| HNSW | Hierarchical Navigable Small World - thuật toán index cho vector |
| pgvector | PostgreSQL extension hỗ trợ vector similarity search |
| MV3 | Manifest V3, chuẩn extension mới nhất của Chrome |
| WSS | WebSocket Secure (TLS) |
| RLS | Row-Level Security của PostgreSQL |
| SLO | Service Level Objective - mục tiêu chất lượng dịch vụ |
| MRR | Monthly Recurring Revenue |
| Quick Paste | Feature paste text vào comment box không tự submit |
| DH | Digital Human - nhân vật ảo sinh bằng AI |

## B. External References

- Supabase docs: https://supabase.com/docs
- pgvector: https://github.com/pgvector/pgvector
- FastAPI: https://fastapi.tiangolo.com
- Gemini API: https://ai.google.dev/gemini-api/docs
- Lemon Squeezy: https://docs.lemonsqueezy.com
- HeyGen API: https://docs.heygen.com
- Chrome Extension MV3: https://developer.chrome.com/docs/extensions/mv3

## C. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 0.1 | 04/2026 | Team | Initial draft |
| 1.0 | 04/2026 | Team | First complete version |

---

*— Hết tài liệu —*
