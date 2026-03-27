# Backend endpoints vs UI triggers

The mock API implementation and `docker-compose.yml` live in **`m2r2/mock-backend/`** (sibling of the `mystic-flame` app repo).

This document maps **user-visible actions** (and automatic loads) to **HTTP calls**, then to the **upstream API** (`NEXT_PUBLIC_API_BASE_URL`, e.g. `http://localhost:8080/api/v1`).

**Conventions**

| Client pattern | Meaning |
|----------------|---------|
| **Browser → Next** `GET/POST /api/...` | Next.js route handlers under `app/(store)/api/` (often proxy to backend with cookies + `X-Tenant-Domain`). |
| **Browser → API** `{BASE}/...` | Direct `fetch` / `axios` to `NEXT_PUBLIC_API_BASE_URL` (public routes, some auth pages). |
| **WebSocket** | `NEXT_PUBLIC_API_BASE` (no `/api/v1` path segment) + `/api/v1/ws-endpoint` — see Stomp section. |

**Not your Java API** (third-party): Google Places/Geolocation, `ipapi.co` — used for maps/autocomplete/country detection.

---

## 1. Page load & layout (SSR / first paint)

| Trigger | Where | Call | Upstream backend |
|--------|--------|------|------------------|
| Store layout / pages need hero | `app/(store)/layout.tsx`, `page.tsx`, `products/page.tsx`, `products/[id]/page.tsx`, `categories/*` | `fetch(\`${BASE}/public/customer-gateway/heroes/${domain}\`)` | `{BASE}/public/customer-gateway/heroes/:domain` |
| PWA manifest | `app/(store)/api/manifest/route.ts` | Server calls `fetchHeroDetails` → | `{BASE}/public/customer-gateway/heroes/:domain` |

---

## 2. Store bootstrap (client contexts)

| Trigger | Where | Call | Upstream backend |
|--------|--------|------|------------------|
| App loads store metadata | `utils/storeApi.tsx` / consumers | `GET {BASE}/public/storeWeb?domainName=...` | `{BASE}/public/storeWeb` |
| Branch list | `context/BranchContext.tsx` → `branchService` | `GET {BASE}/public/customer-gateway/branches/domain/:domain` | same |
| Nearest branch (geo) | `branchService.getNearestBranchesByDomain` | `GET {BASE}/public/customer-gateway/branches/v2/domain/:domain?latitude&longitude` | same |
| Store + footer | `storeService` | `GET {BASE}/public/customer-gateway/stores/:domain`, `GET {BASE}/public/customer-gateway/footer/:branchId` | same |
| Featured products (home) | `fetchFeaturedProducts` | `GET {BASE}/public/customer-gateway/featured-products/:domain` | same |
| Featured categories (home) | `fetchFeaturedCategories` | `GET {BASE}/public/customer-gateway/featured-categories/:domain` | same |
| Hero fetch (client) | `utils/fetchHeroDetails.ts` | `GET {BASE}/public/customer-gateway/heroes/:domain` | same |

---

## 3. Catalog: browse, search, filters

| Trigger | Where | Call | Upstream backend |
|--------|--------|------|------------------|
| Featured grid | `Products.tsx` / `ProductsWrapper` → `productService` | `GET {BASE}/public/customer-gateway/branches/:branchId/products/featured` | same |
| Product list + filters | `productService.getProductsByBranch` | `GET {BASE}/public/customer-gateway/branches/:branchId/products?search,categoryIds,sort,...` | same |
| Category sidebar / list | `categoryService` | `GET {BASE}/public/customer-gateway/branches/:branchId/categories?...` | same |
| Product detail | `productService.getProductDetails` | `GET {BASE}/public/customer-gateway/products/:productId` | same |
| Related products | `getRecommendedProducts` | `GET {BASE}/public/customer-gateway/products/related-products/:productId` | same |
| Domain search (chat flow) | `productService.getProductsByDomain` | `GET {BASE}/public/customer-gateway/domains/:domain/products?query=` | same |

---

## 4. Branch status & hours

| Trigger | Where | Call | Upstream backend |
|--------|--------|------|------------------|
| Opening status badge | `BranchOpeningStatus` → `branchService` | `GET {BASE}/public/customer-gateway/branches/:branchId/status` | same |
| Store hours (chat/footer) | `branchService.getBranchHours` | `GET {BASE}/public/customer-gateway/branches/:branchId/hours` | same |

---

## 5. Cart & checkout (logged-in flows use Next BFF)

| Trigger | Where | Browser call | Upstream (via Next proxy) |
|--------|--------|--------------|----------------------------|
| Load cart / merge | `CartContext` → `cartService` | `/api/carts`, `/api/carts/items`, `/api/carts/items/count` | `GET /customer/carts`, `POST/PUT/DELETE /customer/carts/items`, `GET /customer/carts/items/count` |
| Apply coupon | `CartDetails.tsx` | `POST /api/promotion/calculate` | `POST /customer/promotion/calculate` |
| Delivery cost | Selecting address / delivery | `GET /api/delivery/getDeliveryCost?latitude&longitude` | `GET /customer/delivery/cart/cost?...` |
| Start checkout | Submit cart checkout | `POST /api/checkout/initiate` | `POST /customer/checkout/initiate` |
| Stock validation | After initiate | `POST /api/order/validate` | `POST /customer/order/validateStocks/cart/:cartId` |
| Order summary (checkout page) | `cartService.getOrderSummary` | `GET /api/checkout/order-summary` | `GET /customer/checkout` |
| Payment session (Stripe/Razorpay) | `cartService.getPaymentDetails` | `POST /api/checkout/payment/initiate` | `POST /customer/checkout/payment/initiate` |
| Place order (COD / after online) | `orderService.placeOrder` / `CashPaymentForm` | `POST /api/order/place` | `POST /customer/order/place` |
| Razorpay verify | `RazorpayPaymentForm.tsx` | `POST /api/verify-payment` | `POST /customer/verify-payment` |
| Stripe publishable key | `useStripePromise` | `GET /api/stripe/config` | `GET /customer/stripe/config` |
| Pickup locations | `PaymentAndFulfillment` | `GET /api/fulfillment/pickup-locations?domain=` | `GET /customer/fulfillment/pickup-locations/:domain` |

**Public payment/fulfillment flags (no auth)**

| Trigger | Where | Call | Upstream |
|--------|--------|------|----------|
| Payment methods enabled | `paymentService` / cart UI | `GET {BASE}/public/customer-gateway/payment/payment-details/:domain` | same |
| Delivery/pickup flags | `fulfillmentService` | `GET {BASE}/public/customer-gateway/fulfillment/fulfillment-summary/:domain` | same |

---

## 6. Wishlist

| Trigger | Where | Browser call | Upstream |
|--------|--------|--------------|----------|
| Load / add / remove / clear | `WishlistContext` → `wishlistService` | `/api/wishlist`, `/api/wishlist/:productId`, `DELETE /api/wishlist/clear` | `GET/POST/DELETE /customer/wishlist...` |

---

## 7. Orders

| Trigger | Where | Browser call | Upstream |
|--------|--------|--------------|----------|
| Lists | `OrdersPage` | `GET /api/order/active`, `GET /api/order/completed` | `GET /customer/order/active`, `GET /customer/order/completed` |
| Cancel / refund / repeat | `OrderCard` | `POST /api/order/:id/requestCancellation` etc. | `POST /customer/order/:id/...` |
| Receipt / invoice PDF link | `OrderCard` | `GET /api/order/:id/receipt`, `GET /api/order/:id/invoice` | `GET /customer/order/:id/receipt`, `.../invoice` |
| Track (authenticated) | `orderService.trackOrder` | `GET /api/order/:id/track` | `GET /customer/order/:id/track` |
| Track (public / chat) | `chatService` / flows using public API | `GET {BASE}/public/customer-gateway/order/:orderNumber/track` | same |

---

## 8. Addresses

| Trigger | Where | Browser call | Upstream |
|--------|--------|--------------|----------|
| List / CRUD | `CustomerAddressSelector`, `addressService` | `/api/customer-address`, `/api/customer-address/primary`, `/api/customer-address/:id` | `GET/POST /customer/customer-address`, `GET .../primary`, `PUT/DELETE .../:id` |
| Create order with new address | `CartDetails` / order flow | `POST /api/order/create` | `POST /customer/order/create` |

---

## 9. Reviews

| Trigger | Where | Call | Upstream |
|--------|--------|------|----------|
| Public list / avg / distribution | `ProductReviewData` → `reviewService` | `GET {BASE}/public/customer-gateway/reviews/...` | product, average-rating, rating-distribution, recent, top-rated, by-rating |
| Single review by id | `fetchReviewById` | `GET {BASE}/public/customer-gateway/reviews/:id` | same |
| My reviews / has reviewed | `reviewService` | `/api/reviews/my`, `/api/reviews/product/:id/has-reviewed` | `GET /customer/reviews/my`, `GET /customer/reviews/product/:id/has-reviewed` |
| Recent / top (authed routes) | Next API | `/api/reviews/recent`, `/api/reviews/top-rated` | `GET /customer/reviews/recent`, `GET /customer/reviews/top-rated` |
| Create / update / delete | `ReviewDialog`, `ProductReviewData` | `POST/PUT/DELETE /api/reviews/:id` (multipart) | `POST/PUT/DELETE /customer/reviews/:id` |

---

## 10. Auth

| Trigger | Where | Browser call | Upstream |
|--------|--------|--------------|----------|
| Email login | `LoginPage` → `utils/auth.ts` | `POST /api/auth/email/login` | `POST {BASE}/auth-customer/email/login/:domain` |
| Email signup / verify | Signup flows | `POST /api/auth/email/signup/:domain`, `POST /api/auth/email/verify/:domain` | `POST {BASE}/auth-customer/email/...` |
| Email reset (Next route) | Forgot password using API route | `POST /api/auth/email/reset-password` | `POST {BASE}/auth/email/reset-password` |
| WhatsApp OTP / verify / signup | `LoginPage` etc. | `/api/auth/whatsapp/...` | `POST {BASE}/auth-customer/whatsapp/...` |
| User profile | `AuthContext` → `getUserInfo` | `GET /api/auth/user-info` | `GET {BASE}/customer/user-info` |
| Logout | `utils/auth.ts` | `POST /api/auth/logout` | `POST {BASE}/customer/logout` |

**Direct to `{BASE}` (no Next BFF)**

| Trigger | Where | Upstream |
|--------|--------|----------|
| Password reset **initiate** (email link flow) | `PasswordResetInitiate.tsx` | `POST {BASE}/auth-customer/password-reset/initiate` |
| Password reset **confirm** | `PasswordResetConfirm.tsx` | `POST {BASE}/auth/password-reset/confirm` |

**Declared but may be unused / no Next route found**

| Trigger | Where | Notes |
|--------|--------|------|
| Google login | `authService.loginWithGoogle` | `POST /api/auth/google/login` — **no matching `route.ts` in repo** |
| Email reset in `authService` | `resetPassword` | Uses `/api/auth/email/reset-password` (exists) |

---

## 11. Chat & support

| Trigger | Where | Call | Upstream |
|--------|--------|------|----------|
| Anonymous create / load / messages | `createAnonymousChat`, `getAnonymousMessages`, `sendAnonymousMessage` | `{BASE}/public/customer-gateway/chat/create`, `GET chat/:id`, message endpoints | same |
| Logged-in chat | `supportService` | `/api/chat/chats/create`, `/api/chat/chats`, `/api/chat/chats/:id`, `/api/chat/messages/*`, `/api/chat/participants/*` | `/customer/chats...`, `/customer/messages...`, `/customer/participants...` |

---

## 12. WebSocket / realtime

| Trigger | Where | Call | Backend |
|--------|--------|------|---------|
| Auth STOMP token | `StompContext.tsx` | `GET /api/ws-token` (Next; cookie `token`) | *(no upstream HTTP; token used client-side)* |
| Connect STOMP | `StompContext.tsx` | WebSocket to `ws(s)://{host from NEXT_PUBLIC_API_BASE}/api/v1/ws-endpoint` | Same path on API host; `Authorization: Bearer` for auth client |

---

## 13. Misc UI

| Trigger | Where | Call | Upstream |
|--------|--------|------|----------|
| Location search | `LocationSelector.tsx` | `GET /api/autocomplete?input=` / `?action=geolocate` | **Google APIs** (not Java backend) |
| PDF proxy | `app/api/proxy/pdf/route.ts` | Fetches arbitrary PDF URL | External URL passed in query |
| Order badge count | `ClientOrderIcon.tsx` | `GET /api/orders/getCount` | **No `app/.../api/orders/getCount/route.ts` in repo** — likely broken or missing |

---

## 14. Quick reference — all Next proxies → backend paths

These are the **upstream paths** used by `makeAuthenticatedRequest` / axios in `app/(store)/api/*/route.ts` (prefix `{BASE}`):

- `/customer/carts`, `/customer/carts/items`, `/customer/carts/items/count`
- `/customer/wishlist`, `/customer/wishlist/:productId`, `/customer/wishlist/clear`
- `/customer/checkout`, `/customer/checkout/initiate`, `/customer/checkout/payment/initiate`
- `/customer/order/*` (active, completed, place, create, validateStocks, track, receipt, invoice, repeat, requestCancellation, requestRefund)
- `/customer/customer-address`, `/customer/customer-address/primary`, `/customer/customer-address/:id`
- `/customer/delivery/cart/cost`
- `/customer/fulfillment/pickup-locations/:domain`
- `/customer/promotion/calculate`
- `/customer/stripe/config`
- `/customer/verify-payment`
- `/customer/reviews/*` (my, recent, top-rated, product/:id/has-reviewed, `:id` CRUD)
- `/customer/chats`, `/customer/chats/create`, `/customer/chats/:id`
- `/customer/messages/*`, `/customer/participants/me`, `/customer/participants/nickname`
- `/customer/logout`
- `/customer/user-info` (also called from `auth/user-info` route)

Auth routes that hit `{BASE}` directly (not under `/customer/`):

- `/auth-customer/email/login/:domain`, `/auth-customer/email/signup/:domain`, `/auth-customer/email/verify/:domain`
- `/auth-customer/whatsapp/login/otp/:domain`, `/auth-customer/whatsapp/login/verify/:domain`
- `/auth-customer/whatsapp/signup/:domain`, `/auth-customer/whatsapp/signup/complete/:domain`
- `/auth/email/reset-password`

---

*Generated from static analysis of the `mystic-flame` codebase. When you add new buttons or API routes, update this file alongside `m2r2/mock-backend/server.js`.*
